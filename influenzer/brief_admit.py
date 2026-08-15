"""Admit 0 or 1 pending brief into state.db.

One story at a time: a pending brief or unprocessed social draft is silence;
the same ship artifact is not retold.

Does not call gh. Does not survey GitHub. Does not score. Does not publish.
Never opens runtime.db.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from influenzer.config import load_config
from influenzer.domain import utc_now
from influenzer.envelope import noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom import HomError, brief_from_mapping, is_ship_artifact
from influenzer.playbook import StoryKind, is_social_arena, looks_like_empty_repo, looks_like_fork
from influenzer.storage import StateRepository, StorageError

SOURCE = "github-scan"


def host_silence(reason: str, *, project_id: str, repo_slug: str, **extra: Any) -> dict[str, Any]:
    return noop(
        reason,
        published=False,
        project_id=project_id,
        repo=repo_slug,
        brief_id=None,
        source=SOURCE,
        **extra,
    )


def open_story_reason(repo: StateRepository, project_id: str) -> str | None:
    if repo.get_project(project_id) is None:
        return "project not found"
    if any(brief.project_id == project_id for brief in repo.list_pending_briefs(project_id)):
        return "pending_brief"
    for draft in repo.list_operator_drafts(project_id):
        if is_social_arena(draft.arena):
            return "social_draft"
    return None


def already_told(repo: StateRepository, project_id: str, urls: Sequence[str], brief_id: str) -> bool:
    if repo.get_brief(project_id, brief_id) is not None:
        return True
    wanted = {url for url in urls if url}
    if not wanted:
        return False
    for brief in repo.list_briefs(project_id):
        for fact in brief.facts:
            if fact.artifact_url and fact.artifact_url in wanted:
                return True
    return False


def admit_pack(
    repo: StateRepository,
    payload: dict[str, Any],
    *,
    project_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    slug = str(payload.get("repo") or "")
    if payload.get("status") != "ok":
        return host_silence(str(payload.get("reason") or "scan_failed"), project_id=project_id, repo_slug=slug)
    blocked = open_story_reason(repo, project_id)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list) or not facts_raw:
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    brief_id = str(payload.get("brief_id") or "")
    artifact_urls = tuple(
        str(item.get("artifact_url"))
        for item in facts_raw
        if isinstance(item, dict) and item.get("artifact_url")
    )
    if already_told(repo, project_id, artifact_urls, brief_id):
        return host_silence("already_told", project_id=project_id, repo_slug=slug)
    created_at = now or payload.get("now") or utc_now()
    if not isinstance(created_at, str):
        created_at = utc_now()
    tryable = bool(payload.get("tryable"))
    if not tryable:
        return host_silence("not_tryable", project_id=project_id, repo_slug=slug)
    fact_blob = "\n".join(str(item.get("text") or "") for item in facts_raw if isinstance(item, dict))
    if bool(payload.get("isFork")) or looks_like_fork(fact_blob):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isEmpty")) or looks_like_empty_repo(fact_blob):
        return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
    try:
        brief = brief_from_mapping(
            {
                "project_id": project_id,
                "brief_id": brief_id,
                "facts": facts_raw,
                "story_kind": StoryKind.MAJOR.value,
                "claims_ship": True,
                "tryable": True,
                "source": SOURCE,
                "created_at": created_at,
            }
        )
    except (HomError, ValueError):
        return host_silence("scan_failed", project_id=project_id, repo_slug=slug)
    if not any(is_ship_artifact(fact.artifact_url) for fact in brief.facts):
        return host_silence("not_tryable", project_id=project_id, repo_slug=slug)
    try:
        repo.save_brief(brief, event_type="brief.scanned")
    except StorageError:
        return host_silence("already_told", project_id=project_id, repo_slug=slug)
    return ok(
        published=False,
        project_id=brief.project_id,
        brief_id=brief.brief_id,
        repo=slug,
        story_kind=brief.story_kind.value,
        source=brief.source,
        fact_count=len(brief.facts),
        claims_ship=True,
        tryable=True,
        pending=True,
    )


def main(argv: list[str] | None = None) -> int:
    import json
    import sys

    parser = argparse.ArgumentParser(prog="influenzer-brief-admit")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--config", help="path to config.json")
    args = parser.parse_args(argv)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        out = admit_pack(repo, payload, project_id=args.project_id)
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.brief")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
