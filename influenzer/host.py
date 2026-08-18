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
