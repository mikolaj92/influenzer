"""Admit public GitHub replies as at most one pending brief.

Host compose: github_feedback → 0 or 1 brief (`source=github-feedback`).
`--repo` and/or the declared watch. One story at a time.

Does not publish. Does not enable live social. Does not dress. Does not score.
Does not choose a social angle. Does not know Heimdall. Does not know my-auth.
Does not survey releases/PRs (that is github_survey). Does not grow github_survey.
Does not auto-post replies. Does not scrape X or LinkedIn. Does not call hop.
Does not enable Ads. Does not run every tick interval. Does not open runtime.db.
Does not embed a Fala host.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from github_feedback import collect_feedback
from github_survey import GhRunner, invalid_repo_reason

from influenzer.brief_admit import already_told, open_story_reason
from influenzer.config import load_config
from influenzer.domain import utc_now
from influenzer.envelope import noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom import HomError, brief_from_mapping
from influenzer.playbook import StoryKind
from influenzer.storage import StateRepository, StorageError

SOURCE = "github-feedback"


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


def resolve_target(
    repo: StateRepository,
    *,
    project_id: str | None,
    repo_slug: str | None,
) -> tuple[str, str] | dict[str, Any]:
    watch = repo.get_hom_watch()
    pid = (project_id or "").strip() or (watch["project_id"] if watch else "")
    slug = (repo_slug or "").strip() or (watch["repo"] if watch else "")
    if not pid or not slug:
        return host_silence("no_watch", project_id=pid, repo_slug=slug)
    bad = invalid_repo_reason(slug)
    if bad:
        return host_silence(bad, project_id=pid, repo_slug=slug)
    return pid, slug


def admit_feedback(
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
    if repo.list_operator_drafts(project_id):
        return host_silence("open_draft", project_id=project_id, repo_slug=slug)
    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list) or not facts_raw:
        return host_silence("comment_noise", project_id=project_id, repo_slug=slug)
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
    try:
        brief = brief_from_mapping(
            {
                "project_id": project_id,
                "brief_id": brief_id,
                "facts": facts_raw,
                "story_kind": str(payload.get("story_kind") or StoryKind.HARD_ISSUE.value),
                "claims_ship": False,
                "tryable": False,
                "source": SOURCE,
                "created_at": created_at,
            }
        )
    except (HomError, ValueError):
        return host_silence("scan_failed", project_id=project_id, repo_slug=slug)
    try:
        repo.save_brief(brief, event_type="brief.feedback")
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
        claims_ship=False,
        tryable=False,
        pending=True,
    )


def collect_and_admit(
    repo: StateRepository,
    *,
    project_id: str | None = None,
    repo_slug: str | None = None,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose collect → admit. At most one pending brief, or silence."""
    target = resolve_target(repo, project_id=project_id, repo_slug=repo_slug)
    if isinstance(target, dict):
        return target
    pid, slug = target
    blocked = open_story_reason(repo, pid)
    if blocked:
        return host_silence(blocked, project_id=pid, repo_slug=slug)
    if repo.list_operator_drafts(pid):
        return host_silence("open_draft", project_id=pid, repo_slug=slug)
    try:
        packed = collect_feedback(slug, gh=gh, now=now)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return host_silence("empty_feedback", project_id=pid, repo_slug=slug)
    return admit_feedback(repo, packed, project_id=pid, now=now or utc_now())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-hom-feedback")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo", help="owner/name of a public GitHub repo")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--now", help="ISO-8601 clock for the lookback window")
    args = parser.parse_args(argv)
    raw = sys.stdin.read()
    payload: dict[str, Any] | None = None
    if raw.strip():
        try:
            loaded = json.loads(raw)
        except json.JSONDecodeError:
            loaded = {}
        if isinstance(loaded, dict) and loaded:
            payload = loaded
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        if payload is not None:
            out = admit_feedback(repo, payload, project_id=args.project_id, now=args.now)
        else:
            out = collect_and_admit(
                repo,
                project_id=args.project_id,
                repo_slug=args.repo,
                now=args.now,
            )
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.brief")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "SOURCE",
    "admit_feedback",
    "collect_and_admit",
    "host_silence",
    "main",
    "resolve_target",
]
