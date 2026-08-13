"""Single scheduled mutator entrypoint."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from influenzer.config import load_config
from influenzer.scheduler import tick
from influenzer.storage import StateRepository


def run_tick(*, config_path: str | None = None, cli_live: bool = False) -> dict:
    """One dry-run-default mutator pass against state.db. Does not open runtime.db."""
    cfg = load_config(config_path)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        return tick(repo, cfg, due=(), cli_live=bool(cli_live))


def write_fala_result(payload: dict[str, object], *, env: dict[str, str] | None = None) -> Path | None:
    """Honor the Fala subprocess organ contract when the host injected an output dir.

    Does not import or embed a Fala host. Domain state stays in state.db.
    """
    source = os.environ if env is None else env
    output_dir = source.get("FALA_EFFECTOR_OUTPUT_DIR")
    if not output_dir:
        return None
    path = Path(output_dir) / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "values": payload,
        "associations": [],
        "reactions": [
            {
                "kind": "hom.decision",
                "media_type": "application/json",
                "value": payload.get("operator", payload),
            }
        ],
        "metadata": {"published": False, "mutated": bool(payload.get("mutated"))},
    }
    path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-tick-all")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument(
        "--live",
        action="store_true",
        help="ignored by tick-all; only scheduler.live_enabled can authorize live mutation",
    )
    args = parser.parse_args(argv)
    # Briefs are scored every tick. Due-plan selection for live publish lands with
    # a deeper scheduler; empty due set remains the safe default (no auto-spam).
    out = run_tick(config_path=args.config, cli_live=bool(args.live))
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
