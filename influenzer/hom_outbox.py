"""One wearable draft from state.db, or silence.

One job: emit at most one QA packet — the current wearable angle sitting
in operator_drafts. Kill, changelog-only, and no-draft are silence.
Several drafts still yield one packet: newest wearable by created_at,
then draft_id.

Does not survey GitHub. Does not call gh. Does not score. Does not dress.
Does not pick an arena. Does not publish. Does not enable live social.
Does not know Heimdall. Does not send mail. Does not mutate adapters.
Does not write state.db. Does not open runtime.db. Does not embed a Fala host.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from influenzer.config import WorkspacePermissionError, open_workspace, permission_exit
from influenzer.envelope import noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom import Draft
from influenzer.storage import StateRepository

# Bodies must look like the arena, not operator metadata.
_FORBIDDEN_IN_BODY = (
    "Costume:",
    "One arena:",
    "One angle:",
    "Wave checklist:",
)


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
    )


def is_wearable(draft: Draft) -> bool:
    body = (draft.body or "").strip()
    if not body:
        return False
    return not any(marker in body for marker in _FORBIDDEN_IN_BODY)


def choose_draft(drafts: list[Draft]) -> Draft | None:
    """Newest wearable by created_at, then draft_id. Never a list."""
    wearable = [draft for draft in drafts if is_wearable(draft)]
    if not wearable:
        return None
    return max(wearable, key=lambda draft: (draft.created_at, draft.draft_id))


def packet_for(draft: Draft) -> dict[str, Any]:
    return ok(
        empty=False,
        published=False,
        project_id=draft.project_id,
        brief_id=draft.brief_id,
        draft_id=draft.draft_id,
        arena=draft.arena.value,
        costume=draft.costume,
        angle=draft.angle,
        body=draft.body,
        content_hash=draft.content_hash,
        canon_url=draft.canon_url,
    )


def emit_angle(repo: StateRepository, *, project_id: str | None = None) -> dict[str, Any]:
    """Read operator_drafts; return one packet or silence. No writes."""
    if project_id is not None and repo.get_project(project_id) is None:
        return _silence("project not found", project_id=project_id)
    chosen = choose_draft(repo.list_operator_drafts(project_id))
    if chosen is None:
        return _silence("no_draft", project_id=project_id)
    return packet_for(chosen)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-hom-outbox")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--project-id", help="limit to one project")
    args = parser.parse_args(argv)
    try:
        cfg = open_workspace(args.config)
        with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
            out = emit_angle(repo, project_id=args.project_id)
    except WorkspacePermissionError:
        return permission_exit()
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.angle")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["choose_draft", "emit_angle", "is_wearable", "main", "packet_for"]
