"""Ship vs patch/typo/chore noise. Waitlist is not a ship. A merge log is not a ship.

Tryable is a README+URL heuristic. Look does not run the project.
Launching on watch is silence. Code in look is untrusted.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

_PATCH_ONLY_RE = re.compile(
    r"(?i)^\s*(?:docs|style|test|refactor|build)(?:\([^)]*\))?:\s|"
    r"^\s*(?:fix(?:es)?\s+)?(?:a\s+)?typo\b|"
    r"\btypo\b|"
    r"^\s*patch\b"
)
_COMMIT_NOISE_RE = re.compile(
    r"(?i)^\s*(?:chore|typo|lint|ci|wip|bump\s+(?:version|deps)|fix(?:es)?\s+tests|merge\s+branch)\b"
)
_SHIP_TITLE_RE = re.compile(
    r"(?i)(?:^feat(?:ure)?(?:\([^)]*\))?:\s|"
    r"\b(?:ship(?:ped)?|launch(?:ed)?|released?)\b|"
    r"^add(?:ed)?\s)"
)
_INSTALL_RE = re.compile(
    r"(?i)\b(?:pip(?:x)? install|uv add|uv pip install|uv run|npm (?:i|install)|"
    r"pnpm add|yarn add|cargo install|go install|brew install)\b"
)
_WAITLIST_RE = re.compile(
    r"(?i)(?:"
    r"\bwaitlists?\b"
    r"|\bcoming\s+soon\b"
    r"|\bjoin\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?|mailing\s+lists?)\b"
    r"|\bsign\s*[- ]?up\s+to\s+get\s+(?:early\s+)?access\b"
    r"|\bsign\s*[- ]?up\s+for\s+(?:(?:early\s+)?access|(?:the|our|my)\s+(?:beta|waitlists?|lists?))\b"
    r"|\bget\s+on\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?)\b"
    r"|\bget\s+early\s+access\b"
    r"|\brequest\s+(?:early\s+)?access\b"
    r"|\blanding\s+page\b"
    r"|\bno\s+demo\b"
    r")"
)
_EVENT_RE = re.compile(
    r"(?i)(?:"
    r"\bwebinars?\b"
    r"|\bmeet[- ]?ups?\b"
    r"|\bcalendars?\b(?!\s+year\b)"
    r"|\bkalendarz(?:e|a|u|owi|em|ach)?\b"
    r"|\bwydarzeni(?:e|a|u|em|om|ami|ach)\b"
    r"|\bjoin\s+us\s+(?:this\s+|next\s+)?"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)\b"
    r"|\bdo[lł][aą]cz(?:cie)?\s+(?:do\s+nas\s+)?(?:w\s+)?"
    r"(?:poniedzia[lł]ek|wtorek|[sś]rod[eę]|czwartek|pi[aą]tek)\b"
    r")"
)
_CALENDAR_FILLER_RE = re.compile(
    r"(?i)(?:"
    r"\bhappy\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|holidays?)\b"
    r"|\bhappy\s+new\s+year\b"
    r"|\bmerry\s+christmas\b"
    r"|\bseason['’]?s\s+greetings\b"
    r"|\b(?:repo(?:sitory)?|project)\s+(?:birthday|anniversary)\b"
    r"|\bbirthday\s+of\s+(?:the\s+)?(?:repo(?:sitory)?|project)\b"
    r"|\b(?:repo(?:sitory)?|project)\s+turns\s+\d+\b"
    r"|\burodzin(?:y|om|ach)?\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\brocznic[aeyę]\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\bweso[lł]ych\s+[sś]wi[aą]t\b"
    r"|\bz\s+okazji\s+[sś]wi[aą]t\b"
    r"|\bmi[lł]ego\s+(?:pi[aą]tku|weekendu)\b"
    r"|\btgif\b"
    r"|\b[sś]wi[eę]t(?:a|o)\b"
    r")"
)
_SHIP_ARTIFACT_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:pull/\d+|issues/\d+|releases(?:/tag/[A-Za-z0-9._~-]+|/\d+))$"
)
_MERGED_PR_FACT_RE = re.compile(r"(?i)^merged\s+pr\s+#\d+")
_TRYABLE_ARTIFACT_HOSTS = frozenset({"github.com"})
_UTM_QUERY_RE = re.compile(r"(?i)(?:^|[&])(?:utm_[a-z]+|fbclid|gclid|mc_cid|mc_eid)=")
_CLICK_HERE_RE = re.compile(r"(?i)(?:click[-_ ]here|kliknij[-_ ]tu(?:taj)?)")


def looks_like_patch_only(text: str) -> bool:
    stripped = text.strip()
    if _COMMIT_NOISE_RE.search(stripped):
        return True
    return bool(_PATCH_ONLY_RE.search(stripped))


def looks_like_ship_title(text: str) -> bool:
    if looks_like_patch_only(text):
        return False
    return bool(_SHIP_TITLE_RE.search(text.strip()))


def looks_like_waitlist(text: str) -> bool:
    return bool(_WAITLIST_RE.search(text))


def looks_like_event(text: str) -> bool:
    """True for webinar / meetup / calendar / join us Thursday. Not a ship."""
    if not text or not text.strip():
        return False
    return bool(_EVENT_RE.search(text))


def looks_like_calendar_filler(text: str) -> bool:
    """True for a holiday, repo birthday, or happy Friday. A calendar does not write."""
    if not text or not text.strip():
        return False
    return bool(_CALENDAR_FILLER_RE.search(text))


def is_ship_artifact(url: str | None) -> bool:
    if not url:
        return False
    return bool(_SHIP_ARTIFACT_RE.fullmatch(url.strip()))


def headline_prs(prs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in prs:
        title = str(item.get("title") or "")
        url = str(item.get("url") or "").strip()
        if looks_like_patch_only(title):
            continue
        if not looks_like_ship_title(title):
            continue
        if not is_ship_artifact(url):
            continue
        found.append(dict(item))
    return found


def readme_installable(text: str) -> bool:
    return bool(_INSTALL_RE.search(text))


def _normalized_host(host: str | None) -> str | None:
    value = (host or "").strip().rstrip(".").lower()
    if value.startswith("www."):
        value = value[4:]
    return value or None


def is_trusted_artifact_url(url: str | None) -> bool:
    """True only for https on github.com (or a host we add to the allowlist).

    Another origin, a shortener, a UTM-farm, or “kliknij tu” is silence.
    """
    if not url or not isinstance(url, str):
        return False
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    host = _normalized_host(parsed.hostname)
    if not host or not any(host == name or host.endswith("." + name) for name in _TRYABLE_ARTIFACT_HOSTS):
        return False
    if _UTM_QUERY_RE.search(parsed.query) or _CLICK_HERE_RE.search(raw):
        return False
    return True


def _https_url(value: object) -> bool:
    return is_trusted_artifact_url(value if isinstance(value, str) else None)


def readme_tryable_url(survey: Mapping[str, Any]) -> str | None:
    """README+URL only. Do not run the project. Code in look is untrusted."""
    if not readme_installable(str(survey.get("readme_text") or "")):
        return None
    url = survey.get("readme_url")
    if _https_url(url):
        return str(url)
    meta = survey.get("meta")
    if isinstance(meta, Mapping):
        for key in ("url", "homepageUrl"):
            candidate = meta.get(key)
            if _https_url(candidate):
                return str(candidate)
    return None


def looks_like_merged_pr_fact(text: str) -> bool:
    return bool(_MERGED_PR_FACT_RE.match(text.strip()))


def facts_are_merge_log(facts: Sequence[Mapping[str, Any]]) -> bool:
    """A stack of 'Merged PR #N: …' is changelog, not a tryable ship."""
    meat = [str(item.get("text") or "").strip() for item in facts if str(item.get("text") or "").strip()]
    if not meat:
        return False
    merge = [text for text in meat if looks_like_merged_pr_fact(text)]
    if not merge:
        return False
    return looks_like_merged_pr_fact(meat[0]) or len(merge) == len(meat)


def is_tryable(survey: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> bool:
    """README+URL heuristic. A release is not a run. Launching is silence."""
    if facts_are_merge_log(facts) and not survey.get("releases"):
        return False
    return readme_tryable_url(survey) is not None
