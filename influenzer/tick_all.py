"""Single scheduled mutator entrypoint."""

from __future__ import annotations

import argparse
import json

from influenzer.config import load_config
from influenzer.scheduler import tick
from influenzer.storage import StateRepository


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-tick-all")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument(
        "--live",
        action="store_true",
        help="ignored by tick-all; only scheduler.live_enabled can authorize live mutation",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        # Due-work selection lands with deeper scheduler; empty set is the safe default.
        out = tick(repo, cfg, due=(), cli_live=bool(args.live))
    print(json.dumps(out, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
