"""Hold or pass the current wearable angle.

One job: record a gate decision (pass|hold) on the current wearable draft.
Hold archives that draft so the one-story lock releases. Pass stamps fit.
Neither publishes.

Does not survey GitHub. Does not call gh. Does not score. Does not dress.
Does not scan. Does not pick an arena. Does not publish. Does not enable live social.
Does not know Heimdall. Does not send mail. Does not mutate adapters.
Does not set scheduler.live_enabled. Does not open runtime.db.
Does not embed a Fala host. Does not delete draft history.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from influenzer.config import WorkspacePermissionError, open_workspace, permission_exit
from influenzer.envelope import noop
from influenzer.fala_result import write_fala_result
from influenzer.hom import Draft
from influenzer.hom_outbox import choose_draft, packet_for
from influenzer.storage import StateRepository

_VERDICTS = frozenset({"hold", "pass"})


def _silence(reason: str, *, project_id: str | None = None) -> dict[str, Any]:
    return noop(
        reason,
        empty=True,
        published=False,
        project_id=project_id,
        brief_id=None,
        draft_id=None,
        arena=None,
        costume=None,
        angle=None,
        body=None,
        content_hash=None,
        canon_url=None,
        verdict=None,
    )


def pick_current_draft(
    drafts: list[Draft],
    *,
    draft_id: str | None = None,
) -> Draft | None:
    """Same wearable pick as the outbox. --draft-id only disambiguates."""
    if draft_id is not None:
        drafts = [draft for draft in drafts if draft.draft_id == draft_id]
    return choose_draft(drafts)


def apply_verdict(
    repo: StateRepository,
    verdict: str,
    *,
    project_id: str | None = None,
    draft_id: str | None = None,
) -> dict[str, Any]:
    """Stamp pass|hold on the current angle, or silence. Hold dismisses; pass does not post."""
    if verdict not in _VERDICTS:
        return _silence("no_draft", project_id=project_id)
    if project_id is not None and repo.get_project(project_id) is None:
        return _silence("project not found", project_id=project_id)
    chosen = pick_current_draft(repo.list_operator_drafts(project_id), draft_id=draft_id)
    if chosen is None:
        return _silence("no_draft", project_id=project_id)
    repo.record_draft_verdict(chosen, verdict)
    out = packet_for(chosen)
    out["verdict"] = verdict
    out["published"] = False
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-hom-verdict")
    parser.add_argument("verdict", choices=("hold", "pass"))
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--project-id", help="limit to one project")
    parser.add_argument("--draft-id", help="disambiguate when more than one draft exists")
    args = parser.parse_args(argv)
    try:
        cfg = open_workspace(args.config)
        with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
            out = apply_verdict(
                repo,
                args.verdict,
                project_id=args.project_id,
                draft_id=args.draft_id,
            )
    except WorkspacePermissionError:
        return permission_exit()
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["apply_verdict", "main", "pick_current_draft"]
