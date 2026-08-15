"""Always-on HoM tick loop for a Mac mini / always-on host.

Pending briefs → score / one-arena draft or kill. The interval loop still
scores every time. If a declared watch exists and scan-due would consider
it due, it also runs hom_pass once. `--once` stays score-only (same
mutator as influenzer-tick-all) unless `--pass-if-due`.

Stdout is status only: cisza / admitted / scored. Angle body stays on
explicit `angle` / pass. Journald recap of copy is a leak.

Does not publish. Does not enable live social. Not a laptop LaunchAgent.
Not a hosted service. A human starts this process on the always-on box;
the repo does not SSH or deploy. Fala may conduct the score-only one-shot
as a subprocess organ (`influenzer-tick-all`). Watch set is host CLI only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from typing import Any

from influenzer.hom_watch import loop_status, run_watched_tick
from influenzer.host import HostPower, HostUnsuitable, require_always_on_host

DEFAULT_INTERVAL_SECONDS = 300


def guarded_tick(
    tick_once: Callable[[], dict[str, Any]],
    *,
    supervise: bool,
) -> Callable[[], dict[str, Any]]:
    """Keep the interval loop up if one tick raises. ``--once`` still fails closed."""

    def inner() -> dict[str, Any]:
        try:
            return tick_once()
        except Exception as exc:
            if not supervise:
                raise
            failed = {
                "status": "failed",
                "reason": str(exc),
                "mutated": False,
                "published": False,
            }
            print(json.dumps(loop_status(failed), sort_keys=True), file=sys.stderr)
            return failed

    return inner


def loop_ticks(
    tick_once: Callable[[], dict[str, Any]],
    *,
    interval: float,
    once: bool = False,
    max_ticks: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Repeat one tick on this host. No plist, no launchd, no network host."""
    if not once and interval <= 0:
        raise ValueError("interval must be > 0 unless --once")
    if max_ticks is not None and max_ticks < 1:
        raise ValueError("max_ticks must be >= 1")
    results: list[dict[str, Any]] = []
    while True:
        results.append(tick_once())
        if once:
            return results
        if max_ticks is not None and len(results) >= max_ticks:
            return results
        if should_stop is not None and should_stop():
            return results
        sleep(interval)


def main(
    argv: list[str] | None = None,
    *,
    inspect_host: Callable[[], HostPower] | None = None,
) -> int:
    parser = argparse.ArgumentParser(
        prog="influenzer-tick",
        description=(
            "Always-on HoM tick loop for a Mac mini / always-on host: score pending "
            "briefs into drafts or kills. Interval loop may run hom_pass when a "
            "declared watch is due. --once is score-only unless --pass-if-due. "
            "Stdout is cisza/admitted/scored, never angle copy. Dry-run default. "
            "Not a laptop LaunchAgent. No live social publish. Battery laptops "
            "fail closed for the interval loop."
        ),
    )
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"seconds between ticks (default {DEFAULT_INTERVAL_SECONDS}; ignored with --once)",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help=(
            "run a single tick then exit (score-only like influenzer-tick-all; "
            "does not scan unless --pass-if-due; allowed on any machine)"
        ),
    )
    parser.add_argument(
        "--pass-if-due",
        action="store_true",
        help=(
            "with --once, run hom_pass if a declared watch is due "
            "(interval loop already does this when a watch exists and scan-due would look)"
        ),
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="stop after N ticks (local loop on the always-on host; not a hosted daemon)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="ignored; only scheduler.live_enabled can authorize live mutation",
    )
    args = parser.parse_args(argv)

    try:
        require_always_on_host(once=bool(args.once), inspect=inspect_host)
    except HostUnsuitable as exc:
        print(
            json.dumps(
                {"status": "failed", "reason": str(exc), "mutated": False, "published": False},
                sort_keys=True,
            )
        )
        return 2

    def tick_once() -> dict[str, Any]:
        return run_watched_tick(
            config_path=args.config,
            cli_live=bool(args.live),
            allow_hom_pass=not bool(args.once) or bool(args.pass_if_due),
        )

    def emit_status() -> dict[str, Any]:
        out = guarded_tick(tick_once, supervise=not bool(args.once))()
        print(json.dumps(loop_status(out), sort_keys=True))
        return out

    try:
        loop_ticks(
            emit_status,
            interval=args.interval,
            once=bool(args.once),
            max_ticks=args.max_ticks,
        )
    except KeyboardInterrupt:
        return 0
    except ValueError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True))
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
