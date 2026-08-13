"""Always-on host fitness for the interval tick.

The 24/7 loop is for a Mac mini (or similar always-on box). Battery laptops
fail closed. One-shot ticks stay allowed anywhere. This is not a LaunchAgent.
"""

from __future__ import annotations

import platform
import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BATTERY_LAPTOP_REASON = (
    "interval tick refuses battery laptops; run on an always-on host (Mac mini)"
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
