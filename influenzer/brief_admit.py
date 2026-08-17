"""Admit 0 or 1 pending brief into state.db.

One story at a time for the whole machine (this state.db), not one
project_id: a pending brief, unprocessed social draft, or living 48h
github/hn stack on any project is silence for every watch. Changelog on
GitHub may wait. The factory does not launch two products in parallel.
The same ship artifact is not retold. Two watches on the same repo are one
look: a second brief from the same git is silence, even with another project_id.
Crash mid-look resumes; it does not start from zero. Look already done and
look in progress are two states. A second gh on a half-open look is an error.
Pending brief after a crash is score+angle only, no second survey/gh.
Two ticks the same Monday are one look. A race on admit is CAS silence,
not a second brief.

Does not call gh. Does not survey GitHub. Does not score. Does not publish.
Never opens runtime.db.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
Watch only on our repo. Owner must be the project maintainer (same
GitHub login). A ship angle on a foreign repo is silence. Helping them
is cisza here or contribute, not our launch.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from typing import Any

from github_pack.pack import sanitize_inbound_facts
from github_survey.survey import look_bytes_over_limit, state_bytes_over_limit

from influenzer.config import load_config
from influenzer.domain import foreign_owner_reason, utc_now
from influenzer.envelope import fail, noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom import HomError, brief_from_mapping, is_ship_artifact
from influenzer.playbook import (
    EVENT_NOT_A_SHIP,
    CALENDAR_FILLER_REASON,
    COUNTER_THANKS_REASON,
    FOG_REASON,
    FOUNDER_JOURNAL_REASON,
    LEAD_MAGNET_REASON,
    LIVING_STACK_REASON,
    SECRET_REASON,
    StoryKind,
    is_social_arena,
    looks_like_archived_repo,
    looks_like_empty_repo,
    looks_like_event,
    looks_like_calendar_filler,
    looks_like_counter_thanks,
    looks_like_fog,
    looks_like_founder_journal,
    looks_like_lead_magnet,
    looks_like_failed_ci,
    looks_like_fork,
    looks_like_pending_ci,
    looks_like_private_repo,
    looks_like_secret,
)
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


def host_error(reason: str, *, project_id: str, repo_slug: str, **extra: Any) -> dict[str, Any]:
    """Second gh on a half-open look is an error, not a new survey."""
    return fail(
        reason,
        published=False,
        project_id=project_id,
        repo=repo_slug,
        brief_id=None,
        source=SOURCE,
        **extra,
    )


def open_story_reason(
    repo: StateRepository,
    project_id: str,
    now: str | None = None,
) -> str | None:
    """Lock is state.db, not one project_id. One story on the machine."""
    if repo.get_project(project_id) is None:
        return "project not found"
    if repo.list_pending_briefs():
        return "pending_brief"
    for draft in repo.list_operator_drafts():
        if is_social_arena(draft.arena):
            return "social_draft"
    _owner, arena = repo.living_stack(now)
    if arena is not None:
        return LIVING_STACK_REASON
    return None


def already_told(repo: StateRepository, project_id: str, urls: Sequence[str], brief_id: str) -> bool:
    if repo.get_brief(project_id, brief_id) is not None:
        return True
    wanted = {url for url in urls if url}
    if not wanted:
        return False
    for brief in repo.list_briefs():
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
    if look_bytes_over_limit(payload) or state_bytes_over_limit(payload):
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    if payload.get("status") != "ok":
        return host_silence(str(payload.get("reason") or "scan_failed"), project_id=project_id, repo_slug=slug)
    project = repo.get_project(project_id)
    maintainer = project.brand.maintainer if project is not None else None
    foreign = foreign_owner_reason(slug, maintainer)
    if foreign:
        return host_silence(foreign, project_id=project_id, repo_slug=slug)
    clock = now if isinstance(now, str) and now else None
    if clock is None:
        payload_now = payload.get("now")
        clock = payload_now if isinstance(payload_now, str) else None
    blocked = open_story_reason(repo, project_id, clock)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list) or not facts_raw:
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    facts_raw = sanitize_inbound_facts(facts_raw)
    if not facts_raw:
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    brief_id = str(payload.get("brief_id") or "")
    artifact_urls = tuple(
        str(item.get("artifact_url"))
        for item in facts_raw
        if isinstance(item, dict) and item.get("artifact_url")
    )
    if already_told(repo, project_id, artifact_urls, brief_id):
        return host_silence("already_told", project_id=project_id, repo_slug=slug)
    created_at = clock or utc_now()
    tryable = bool(payload.get("tryable"))
    if not tryable:
        return host_silence("not_tryable", project_id=project_id, repo_slug=slug)
    fact_blob = "\n".join(str(item.get("text") or "") for item in facts_raw if isinstance(item, dict))
    if bool(payload.get("isFork")) or looks_like_fork(fact_blob):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isEmpty")) or looks_like_empty_repo(fact_blob):
        return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isPrivate")) or looks_like_private_repo(fact_blob):
        return host_silence("private_repo", project_id=project_id, repo_slug=slug)
    if (
        bool(payload.get("isArchived"))
        or bool(payload.get("isDisabled"))
        or looks_like_archived_repo(fact_blob)
    ):
        return host_silence("archived_repo", project_id=project_id, repo_slug=slug)
    if looks_like_pending_ci(fact_blob):
        return host_silence("pending_ci_unknown", project_id=project_id, repo_slug=slug)
    if looks_like_failed_ci(fact_blob):
        return host_silence("failed_ci_not_tryable", project_id=project_id, repo_slug=slug)
    if looks_like_secret(fact_blob):
        return host_silence(SECRET_REASON, project_id=project_id, repo_slug=slug)
    if looks_like_event(fact_blob):
        return host_silence(EVENT_NOT_A_SHIP, project_id=project_id, repo_slug=slug)
    if looks_like_calendar_filler(fact_blob):
        return host_silence(CALENDAR_FILLER_REASON, project_id=project_id, repo_slug=slug)
    if looks_like_counter_thanks(fact_blob):
        return host_silence(COUNTER_THANKS_REASON, project_id=project_id, repo_slug=slug)
    if looks_like_fog(fact_blob):
        return host_silence(FOG_REASON, project_id=project_id, repo_slug=slug)
    if looks_like_founder_journal(fact_blob):
        return host_silence(FOUNDER_JOURNAL_REASON, project_id=project_id, repo_slug=slug)
    if looks_like_lead_magnet(fact_blob):
        return host_silence(LEAD_MAGNET_REASON, project_id=project_id, repo_slug=slug)
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
        raced = repo.admit_brief(brief, event_type="brief.scanned")
    except StorageError:
        return host_silence("already_told", project_id=project_id, repo_slug=slug)
    if raced:
        return host_silence(raced, project_id=project_id, repo_slug=slug)
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
