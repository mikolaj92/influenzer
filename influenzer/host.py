"""Always-on host fitness for the interval tick, plus public-host tryable.

The 24/7 loop is for a Mac mini (or similar always-on box). Battery laptops
fail closed. One-shot ticks stay allowed anywhere. This is not a LaunchAgent.

A loopback / .local / preview deploy without a public host is not tryable.
Neighbor of #76 (trusted host) and #77 (https only): here it is the host,
not the scheme. A stranger must click and run.
"""

from __future__ import annotations

import ipaddress
import platform
import re
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

BATTERY_LAPTOP_REASON = (
    "interval tick refuses battery laptops; run on an always-on host (Mac mini)"
)
PRIVATE_HOST_NOT_TRYABLE = "private_host_not_tryable"
ARTIFACT_5XX_NOT_TRYABLE = "artifact_5xx_not_tryable"
CAPTCHA_NOT_TRYABLE = "captcha_not_tryable"
AGE_GATE_NOT_TRYABLE = "age_gate_not_tryable"
GEO_BLOCK_NOT_TRYABLE = "geo_block_not_tryable"

# A server error is not a public, working artifact. Require a status context so
# an unrelated number such as an audience count does not silence a real demo.
_ARTIFACT_5XX_RE = re.compile(
    r"(?ix)(?:"
    r"\b(?:http(?:/\d+(?:\.\d+)?)?|status(?:[ _-]code)?|response(?:[ _-]status)?|"
    r"error|code|kod|b[łl][aą]d)\b[^\d]{0,12}\b5\d\d\b"
    r"|\b(?:artifact|demo|site|url|server|look|probe|health)\b[^\d]{0,36}"
    r"\b(?:returns?|returned|got|received|zwraca|dosta[łl])\b[^\d]{0,12}\b5\d\d\b"
    r"|\b5\d\d\s+(?:internal(?:\s+server)?\s+error|bad\s+gateway|"
    r"service\s+unavailable)\b"
    r")"
)

# A CAPTCHA / bot challenge is a gate, not a demo. Keep generic product copy
# such as "CAPTCHA support" usable; require challenge language or a bare gate.
_CAPTCHA_CHALLENGE_RE = re.compile(
    r"(?ix)(?:"
    r"^\s*(?:an?\s+)?(?:re-?captcha|hcaptcha|cloudflare\s+turnstile|captcha|"
    r"bot\s+wall|anti[- ]?bot\s+(?:wall|challenge)|human\s+verification|"
    r"challenge\s+page)\s*[.!]?\s*$"
    r"|\b(?:re-?captcha|hcaptcha|cloudflare\s+turnstile|captcha)\s+"
    r"(?:challenge|wall|gate|check|page|prompt|required|verification|protected|blocks?|blocked)\b"
    r"|\b(?:behind|blocked\s+by|stopped\s+by)\s+(?:an?\s+)?"
    r"(?:re-?captcha|hcaptcha|cloudflare\s+turnstile|captcha|bot\s+wall|"
    r"anti[- ]?bot\s+challenge|human\s+verification|challenge\s+page)\b"
    r"|\b(?:bot|anti[- ]?bot)\s+(?:wall|challenge|gate|check)\b"
    r"|\b(?:cloudflare|browser|security)\s+challenge(?:\s+page)?\b"
    r"|\b(?:captcha|challenge|bot\s+wall|human\s+verification)\s+(?:on|at)\s+"
    r"(?:the\s+)?(?:artifact|demo|site|url|page)\b"
    r"|\b(?:artifact|demo|site|url|page)\b[^\n]{0,36}\b"
    r"(?:returns?|returned|shows?|showed|presents?|presented|serves?|served)\s+"
    r"(?:an?\s+|the\s+)?(?:re-?captcha|hcaptcha|captcha|bot\s+wall|challenge\s+page)\b"
    r"|\b(?:verify|confirm|prove)\s+(?:that\s+)?(?:"
    r"you(?:['’]re|\s+are)\s+(?:a\s+)?human|"
    r"you(?:['’]re|\s+are)\s+not\s+(?:a\s+)?(?:robot|bot))\b"
    r"|\bare\s+you\s+(?:a\s+)?(?:human|robot|bot)\b"
    r"|\bi(?:['’]m|\s+am)\s+not\s+(?:a\s+)?robot\b"
    r"|\b(?:complete|solve|pass)\s+(?:an?\s+|the\s+)?"
    r"(?:re-?captcha|hcaptcha|captcha|human\s+verification|security\s+challenge)\s+"
    r"(?:to|before)\s+(?:continue|view|access|see|try|run|use)\b"
    r"|\b(?:requires?|must)\s+(?:you\s+to\s+)?(?:complete|solve|pass)\s+"
    r"(?:an?\s+|the\s+)?(?:re-?captcha|hcaptcha|captcha|human\s+verification|"
    r"security\s+challenge)\b"
    r"|\bchecking\s+(?:your\s+)?browser\s+before\s+(?:accessing|continuing)\b"
    r"|\bchecking\s+if\s+(?:the\s+)?site\s+connection\s+is\s+secure\b"
    r"|\battention\s+required\s*!?\s*(?:\||[-—])\s*cloudflare\b"
    r"|\b(?:zweryfikuj|potwierd[zź]|udowodnij)(?:,\s*)?(?:[zż]e\s+)?(?:"
    r"jeste[sś]\s+cz[lł]owiekiem|nie\s+jeste[sś]\s+robotem)\b"
    r"|\bnie\s+jestem\s+robotem\b"
    r"|\bweryfikacj[aeęi]\s+cz[lł]owieka\b"
    r"|\bbramk[aąeęi]\s+anty[- ]?botow\w*\b"
    r"|\b(?:captcha|challenge|bot\s+wall|weryfikacja\s+cz[lł]owieka)\s+na\s+"
    r"(?:artefakcie|demo|stronie)\b"
    r")"
)

# An age declaration is a gate, not a demo. Keep product copy such as
# "age-gate support" or "Node.js 18+" usable; require access-gate language.
_AGE_GATE_RE = re.compile(
    r"(?imx)(?:"
    r"^\s*(?:an?\s+)?(?:age[- ]?(?:gate|wall|check|verification)|"
    r"age\s+(?:verification|declaration|confirmation)|18\+(?:\s+only)?|"
    r"adults?[- ]?only|adults?\s+only)\s*[.!?]?\s*$"
    r"|\b(?:age[- ]?(?:gate|wall|check|verification)|"
    r"age\s+(?:verification|declaration|confirmation))\s+(?:on|at)\s+"
    r"(?:the\s+)?(?:artifact|demo|site|url|page)\b"
    r"|\b(?:artifact|demo|site|url|page)\b[^\n]{0,36}\b"
    r"(?:has|shows?|showed|presents?|presented|serves?|served)\s+"
    r"(?:an?\s+|the\s+)?(?:age[- ]?(?:gate|wall|check)|age\s+verification|"
    r"18\+(?:\s+only)?|adults?[- ]?only|adults?\s+only)\b"
    r"|\b(?:behind|blocked\s+by|stopped\s+by)\s+(?:an?\s+)?"
    r"(?:age[- ]?(?:gate|wall|check)|age\s+verification)\b"
    r"|\bage[- ]?gated\s+(?:artifact|demo|site|url|page)\b"
    r"|\b(?:18\+(?:\s+only)?|adults?[- ]?only|adults?\s+only)\s+"
    r"(?:on|at)\s+(?:the\s+)?(?:artifact|demo|site|url|page)\b"
    r"|\b(?:artifact|demo|site|url|page)\b[^\n]{0,24}\b"
    r"(?:is|shows?|returns?|serves?)\s+(?:an?\s+|the\s+)?(?:"
    r"18\+(?:\s+only)?(?!\w)|adults?[- ]?only\b|adults?\s+only\b)"
    r"|\bare\s+you\s+(?:(?:at\s+least|over)\s+)?18"
    r"(?:\+|\s+years?\s+old|\s+or\s+older)?\b"
    r"|\bare\s+you\s+(?:of\s+legal\s+age|an?\s+adult)\b"
    r"|\b(?:confirm|verify|declare|certify|acknowledge)\s+(?:that\s+)?"
    r"you(?:['’]re|\s+are)\s+(?:(?:at\s+least|over)\s+)?18"
    r"(?:\+|\s+years?\s+old|\s+or\s+older)?\b"
    r"|\b(?:confirm|verify|declare|certify|acknowledge)\s+(?:that\s+)?"
    r"you(?:['’]re|\s+are)\s+(?:of\s+legal\s+age|an?\s+adult)\b"
    r"|\b(?:confirm|verify)\s+(?:your\s+)?age\s+(?:to|before)\s+"
    r"(?:continue|view|access|see|try|run|use|enter)\b"
    r"|\b(?:enter|provide)\s+(?:your\s+)?(?:date\s+of\s+birth|birth\s+date|birthday)\s+"
    r"(?:to|before)\s+(?:continue|view|access|see|try|run|use|enter)\b"
    r"|\byou\s+(?:must|need\s+to)\s+be\s+(?:(?:at\s+least|over)\s+)?18"
    r"(?:\+|\s+years?\s+old|\s+or\s+older)?\s+"
    r"(?:to|before)\s+(?:continue|view|access|see|try|run|use|enter)\b"
    r"|\bbramk[aąeęi]\s+wieku\b"
    r"|\b(?:weryfikacj[aeęi]|o[sś]wiadczeni[aeęu]|potwierdzeni[aeęu])\s+wieku\b"
    r"|\bczy\s+masz\s+(?:uko[nń]czone\s+)?18\s+lat\b"
    r"|\bpotwierd[zź](?:,?\s+[zż]e)?\s+(?:masz\s+(?:uko[nń]czone\s+)?18\s+lat|"
    r"jeste[sś]\s+pe[lł]noletni[am]?)\b"
    r"|\b(?:musisz|trzeba)\s+mie[cć]\s+(?:uko[nń]czone\s+)?18\s+lat\s+"
    r"(?:aby|[zż]eby)\s+(?:kontynuowa[cć]|wej[sś][cć]|zobaczy[cć]|skorzysta[cć])\b"
    r"|\btylko\s+dla\s+(?:os[oó]b\s+)?pe[lł]noletnich\b"
    r")"
)

# A geo-block is a region gate, not a demo. Show HN is global.
# Keep generic product copy such as "available in 40 countries" or
# "geo-block support" usable; require a 451 / country wall / region denial.
_GEO_BLOCK_RE = re.compile(
    r"(?ix)(?:"
    r"^\s*(?:an?\s+)?(?:geo[- ]?block(?:ed|ing)?|geoblock(?:ed|ing)?|"
    r"country\s+wall|geo[- ]restrict(?:ed|ion)?|region[- ]lock(?:ed|ing)?)\s*[.!]?\s*$"
    r"|^\s*451\s*[.!]?\s*$"
    r"|^\s*(?:not|n['’]t|isn['’]t)\s+available\s+in\s+(?:your|this)\s+"
    r"(?:region|country)\s*[.!]?\s*$"
    r"|\b(?:geo[- ]?block|geoblock|country\s+wall|geo[- ]restrict(?:ion)?|"
    r"region[- ]lock)\s+(?:challenge|wall|gate|check|page|required|protected|blocks?|blocked)\b"
    r"|\b(?:geo[- ]?blocked|geoblocked|geo[- ]restricted|region[- ]locked)\s+"
    r"(?:artifact|demo|site|url|page)\b"
    r"|\b(?:behind|blocked\s+by|stopped\s+by)\s+(?:an?\s+)?"
    r"(?:geo[- ]?block|geoblock|country\s+wall|geo[- ]restriction|region[- ]lock)\b"
    r"|\b(?:country\s+wall|geo[- ]?block|geoblock|geo[- ]restriction|region[- ]lock)\s+"
    r"(?:on|at)\s+(?:the\s+)?(?:artifact|demo|site|url|page)\b"
    r"|\b(?:artifact|demo|site|url|page)\b[^\n]{0,36}\b(?:is\s+)?"
    r"(?:geo[- ]?blocked|geoblocked|geo[- ]restricted|region[- ]locked)\b"
    r"|\b(?:not|n['’]t|isn['’]t)\s+available\s+in\s+(?:your|this|the)\s+"
    r"(?:region|country|territory|jurisdiction)\b"
    r"|\bunavailable\s+in\s+(?:your|this|the)\s+(?:region|country|territory|jurisdiction)\b"
    r"|\b(?:not|n['’]t|isn['’]t)\s+(?:available|accessible)\s+from\s+"
    r"(?:your|this|the)\s+(?:region|country)\b"
    r"|\bthis\s+(?:content|service|site|demo|product|page|artifact)\s+"
    r"(?:is\s+)?(?:not|n['’]t|isn['’]t)\s+available\s+in\s+(?:your|this)\s+"
    r"(?:region|country)\b"
    r"|\b(?:http(?:/\d+(?:\.\d+)?)?|status(?:[ _-]code)?|response(?:[ _-]status)?|"
    r"error|code|kod|b[łl][aą]d)\b[^\d]{0,12}\b451\b"
    r"|\b(?:head|get)(?:\s*/\s*get)?\s+(?:returned\s+)?451\b"
    r"|\b451\s+unavailable(?:\s+for\s+legal\s+reasons)?\b"
    r"|\bunavailable\s+for\s+legal\s+reasons\b"
    r"|\b(?:artifact|demo|site|url|server|look|probe)\b[^\d]{0,36}"
    r"\b(?:returns?|returned|got|received|zwraca|dosta[łl])\b[^\d]{0,12}\b451\b"
    r"|\bniedost[eę]pn[aey]\s+w\s+(?:twoim|tym)\s+(?:regionie|kraju)\b"
    r"|\bnie\s+jest\s+dost[eę]pn[aey]\s+w\s+(?:twoim|tym)\s+(?:regionie|kraju)\b"
    r"|\bgeo[- ]?blokad[aąeęy]\b"
    r"|\bblokad[aąeęy]\s+geo\b"
    r"|\b[sś]cian[aąeę]\s+krajow\w*\b"
    r")"
)

_LOOPBACK_NAMES = frozenset(
    {
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
        "::1",
        "[::1]",
    }
)
_URL_IN_TEXT_RE = re.compile(r"https?://\S+", re.I)
# Loopback / .local / preview-or-staging without a public host.
# "local tick" and "stays local" stay; localhost / 127.0.0.1 / .local do not.
PRIVATE_HOST_RE = re.compile(
    r"(?i)(?:"
    r"\blocalhost\b"
    r"|127\.\d{1,3}\.\d{1,3}\.\d{1,3}"
    r"|\[::1\]"
    r"|(?<![:\w])::1(?![:\w])"
    r"|\b0\.0\.0\.0\b"
    r"|(?:https?://)?(?:[a-z0-9-]+\.)+local(?:[:/\s]|$)"
    r"|\bhost\s+\.local\b"
    r"|\.local(?:[:/\s]|$)"
    r"|\badres\s+p[eę]tli\b"
    r"|\bpreview\s+deploys?\b"
    r"|\bpreview\s+deployments?\b"
    r"|\bstaging\s+(?:deploys?|deployments?|hosts?|urls?|env(?:ironment)?s?)\b"
    r"|\bon\s+staging\b"
    r"|\bw\s+stagingu\b"
    r"|\bpreview\s+bez\s+publicznego\s+hosta\b"
    r")"
)


class HostUnsuitable(ValueError):
    """Interval loop refused this machine."""


@dataclass(frozen=True)
class HostPower:
    has_battery: bool
    source: str


def _read_pmset() -> str:
    try:
        completed = subprocess.run(
            ["pmset", "-g", "batt"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return f"{completed.stdout or ''}{completed.stderr or ''}"


def inspect_power(
    *,
    platform_name: str | None = None,
    sysfs_root: Path | None = None,
    pmset_text: str | None = None,
) -> HostPower:
    """Detect an internal battery. Unknown hosts are allowed (not guessed as laptops)."""
    system = platform_name or platform.system()
    if system == "Darwin":
        text = _read_pmset() if pmset_text is None else pmset_text
        return HostPower(has_battery="InternalBattery" in text, source="pmset")
    if system == "Linux":
        root = Path("/sys/class/power_supply") if sysfs_root is None else sysfs_root
        if not root.is_dir():
            return HostPower(has_battery=False, source="sysfs")
        has_battery = any(path.name.startswith("BAT") for path in root.iterdir())
        return HostPower(has_battery=has_battery, source="sysfs")
    return HostPower(has_battery=False, source="unknown")


def require_always_on_host(
    *,
    once: bool,
    inspect: Callable[[], HostPower] | None = None,
) -> HostPower:
    """Refuse the interval loop on a battery laptop. ``--once`` is always allowed."""
    power = inspect() if inspect is not None else inspect_power()
    if once:
        return power
    if power.has_battery:
        raise HostUnsuitable(BATTERY_LAPTOP_REASON)
    return power


def _normalized_host(host: str | None) -> str | None:
    value = (host or "").strip().rstrip(".").lower()
    if value.startswith("[") and value.endswith("]"):
        value = value[1:-1]
    if value.startswith("www."):
        value = value[4:]
    return value or None


def is_non_public_tryable_host(host: str | None) -> bool:
    """True for loopback, .local, or a private/link-local address. Not click-and-run."""
    value = _normalized_host(host)
    if not value:
        return True
    if value in _LOOPBACK_NAMES or value.endswith(".local"):
        return True
    try:
        parsed = ipaddress.ip_address(value)
    except ValueError:
        return False
    return (
        parsed.is_private
        or parsed.is_loopback
        or parsed.is_link_local
        or parsed.is_unspecified
        or parsed.is_multicast
        or parsed.is_reserved
    )


def is_artifact_5xx_status(status: int | str | None) -> bool:
    """True when an artifact response is an HTTP server error."""
    if isinstance(status, bool):
        return False
    if isinstance(status, int):
        return 500 <= status <= 599
    if not isinstance(status, str):
        return False
    try:
        return 500 <= int(status.strip()) <= 599
    except ValueError:
        return False


def is_geo_block_status(status: int | str | None) -> bool:
    """True when an artifact response is HTTP 451 Unavailable For Legal Reasons."""
    if isinstance(status, bool):
        return False
    if isinstance(status, int):
        return status == 451
    if not isinstance(status, str):
        return False
    try:
        return int(status.strip()) == 451
    except ValueError:
        return False


def looks_like_artifact_5xx(evidence: str | None) -> bool:
    """True for reported HTTP 5xx evidence; a stranger cannot use it now."""
    return bool(evidence and _ARTIFACT_5XX_RE.search(evidence))


def looks_like_captcha_challenge(evidence: str | None) -> bool:
    """True for a CAPTCHA, bot wall, or human-verification gate."""
    return bool(evidence and _CAPTCHA_CHALLENGE_RE.search(evidence))


def looks_like_age_gate(evidence: str | None) -> bool:
    """True for an age declaration a stranger would have to accept."""
    return bool(evidence and _AGE_GATE_RE.search(evidence))


def looks_like_geo_block(evidence: str | None) -> bool:
    """True for a 451 / country wall / not-available-in-your-region gate."""
    return bool(evidence and _GEO_BLOCK_RE.search(evidence))


def artifact_tryable_reason(
    *, status: int | str | None = None, evidence: str | None = None
) -> str | None:
    """Return the fail-closed reason when an artifact cannot be offered."""
    if is_artifact_5xx_status(status) or looks_like_artifact_5xx(evidence):
        return ARTIFACT_5XX_NOT_TRYABLE
    if is_geo_block_status(status) or looks_like_geo_block(evidence):
        return GEO_BLOCK_NOT_TRYABLE
    if looks_like_captcha_challenge(evidence):
        return CAPTCHA_NOT_TRYABLE
    if looks_like_age_gate(evidence):
        return AGE_GATE_NOT_TRYABLE
    return None


def is_tryable_artifact(
    *, status: int | str | None = None, evidence: str | None = None
) -> bool:
    """Whether an artifact is currently safe to offer to a stranger."""
    return artifact_tryable_reason(status=status, evidence=evidence) is None


def is_private_host_url(url: str | None) -> bool:
    """True for an http(s) URL whose host is loopback / .local / private."""
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False
    return is_non_public_tryable_host(parsed.hostname)


def looks_like_private_host(text: str) -> bool:
    """True for a loopback / .local / preview-or-staging host. A stranger cannot run it."""
    if not text or not text.strip():
        return False
    if PRIVATE_HOST_RE.search(text):
        return True
    for match in _URL_IN_TEXT_RE.finditer(text):
        raw = match.group(0).rstrip(").,;")
        if is_private_host_url(raw):
            return True
    return False
