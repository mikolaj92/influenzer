"""Local tick loop. Not a LaunchAgent. Not a hosted service. Not a Mac mini deploy.

The operator runs this on the machine that already has `state.db`. Fala may
conduct the same one-shot as a subprocess organ (`influenzer-tick-all`); this
module is the interval loop for when no LaunchAgent (and no Fala host) is present.
"""

from __future__ import annotations

import argparse
import json
import time
from collections.abc import Callable
from typing import Any

from influenzer.tick_all import run_tick

DEFAULT_INTERVAL_SECONDS = 300


def loop_ticks(
    tick_once: Callable[[], dict[str, Any]],
    *,
    interval: float,
    once: bool = False,
    max_ticks: int | None = None,
    sleep: Callable[[float], None] = time.sleep,
    should_stop: Callable[[], bool] | None = None,
) -> list[dict[str, Any]]:
    """Repeat one tick. Interval loop is local; no plist, no launchd, no network host."""
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="influenzer-tick",
        description=(
            "Local HoM tick loop: score pending briefs into drafts or kills. "
            "Dry-run default. No LaunchAgent. No live social publish."
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
        help="run a single tick then exit (same mutator as influenzer-tick-all)",
    )
    parser.add_argument(
        "--max-ticks",
        type=int,
        default=None,
        help="stop after N ticks (local loop; not a hosted daemon)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="ignored; only scheduler.live_enabled can authorize live mutation",
    )
    args = parser.parse_args(argv)

    def tick_once() -> dict[str, Any]:
        return run_tick(config_path=args.config, cli_live=bool(args.live))

    try:
        results = loop_ticks(
            tick_once,
            interval=args.interval,
            once=bool(args.once),
            max_ticks=args.max_ticks,
        )
    except KeyboardInterrupt:
        return 0
    except ValueError as exc:
        print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True))
        return 2
    # Last envelope on stdout (same shape as tick-all). Loop traces stay in state.db.
    print(json.dumps(results[-1], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
