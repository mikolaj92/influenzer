"""One CMO look: scan-due, score pending briefs, one angle.

One job: run the weekly-ish cycle once. Compose existing scan_due, tick,
and outbox in that order. Do not copy survey, pack, admit, score, dress,
or outbox.

`--project-id` and `--repo` are required; this block does not invent a
repo inventory.

Does not publish. Does not enable live social. Does not call gh
(github_survey owns gh). Does not know Heimdall. Does not know my-auth.
Does not invoke hold or pass. Does not run every tick interval.
Does not merge scan_due, tick, and outbox into one file.
Does not open runtime.db. Does not embed a Fala host.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not launch or run the project from watch. Tryable is a README+URL
heuristic, not a process we spawned. Foreign and our code in look is untrusted.
Reply and code are not this path.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from influenzer.config import Config, load_config
from influenzer.domain import utc_now
from influenzer.envelope import noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom_outbox import emit_angle
from influenzer.scan_due import DEFAULT_WINDOW_DAYS, scan_github_if_due
from influenzer.scheduler import tick
from influenzer.storage import StateRepository


def _scan_effect(scan: dict[str, Any]) -> dict[str, Any]:
    brief_id = scan.get("brief_id")
    if scan.get("status") == "ok" and isinstance(brief_id, str) and brief_id:
        return {"status": "admitted", "brief_id": brief_id}
    reason = scan.get("reason")
    return {"status": "silence", "reason": str(reason) if reason else "silence"}


def _tick_summary(tick_out: dict[str, Any]) -> dict[str, Any]:
    operator = tick_out.get("operator")
    processed = 0
    if isinstance(operator, dict):
        raw = operator.get("processed") or 0
        processed = int(raw) if isinstance(raw, int) else 0
    return {"scored": processed}


def run_pass(
    repo: StateRepository,
    cfg: Config,
    *,
    project_id: str,
    repo_slug: str,
    gh: Any = None,
    now: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Scan if due, score pending briefs, emit one angle. Dry-run. No live."""
    clock = now or utc_now()
    slug = repo_slug.strip()
    scan = scan_github_if_due(
        repo,
        project_id=project_id,
        repo_slug=slug,
        gh=gh,
        now=clock,
        window_days=window_days,
    )
    tick_out = tick(repo, cfg, due=(), cli_live=False, now=clock)
    angle = emit_angle(repo, project_id=project_id)
    scan_effect = _scan_effect(scan)
    tick_summary = _tick_summary(tick_out)
    admitted = scan_effect["status"] == "admitted"
    scored = tick_summary["scored"]
    has_angle = angle.get("status") == "ok" and not angle.get("empty")
    extra = {
        "published": False,
        "project_id": project_id,
        "repo": slug,
        "scan": scan_effect,
        "tick": tick_summary,
        "angle": angle,
    }
    if admitted or scored or has_angle:
        return ok(**extra)
    reason = str(scan_effect.get("reason") or angle.get("reason") or "silence")
    return noop(reason, **extra)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-hom-pass")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo", required=True, help="owner/name of a public GitHub repo")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--now", help="ISO-8601 clock for the due window and tick")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="coarse cadence in days (default 7)",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        out = run_pass(
            repo,
            cfg,
            project_id=args.project_id,
            repo_slug=args.repo,
            now=args.now,
            window_days=args.window_days,
        )
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "run_pass"]
