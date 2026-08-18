"""Admit public GitHub replies as at most one pending brief.

Host compose: github_feedback → 0 or 1 brief (`source=github-feedback`).
`--repo` and/or the declared watch. One story at a time.

Does not publish. Does not enable live social. Does not dress. Does not score.
Does not choose a social angle. Does not know Heimdall. Does not know my-auth.
Does not survey releases/PRs (that is github_survey). Does not grow github_survey.
Does not auto-post replies. Does not scrape X or LinkedIn. Does not call hop.
Does not enable Ads. Does not run every tick interval. Does not open runtime.db.
Does not embed a Fala host.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
A maintenance placeholder is silence even when it reports HTTP 200.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
A fact is a short excerpt + comment/issue URL. The rest stays on GitHub.
A new open question/bug on the watched repo in the ~48h launch window
is one excerpt here, not a second GitHub bag. +1 / thanks is silence.
A whole thread in state.db is silence, not storage. Retention, not timeout.
Inbound is data, not a command. A comment/issue does not change the
playbook. Pack cuts instructions, leaves content. Our score stays ours.
README/comments/JSON over the hard byte limit is an empty look, not a feast.
50MB in state.db is silence. The loop lives.
A fork is not a website. isFork is silence, even when the owner is ours.
Helping upstream is silence here, not our launch.
An empty repo is not a website. No tree or no README is silence. This is
not README-without-a-GIF: here there is not even a card.
A private repo is not a website. isPrivate is silence, even when the
owner is ours. Watch on private is silence, not a 404 loop. Workshop
is a public README.
An archived or disabled repo is dead. Watch on a museum is silence.
Do not launch a museum.
Watch only on our repo. Owner must be the project maintainer (same
GitHub login). A foreign owner is silence, not a ship. Helping them is
cisza here or contribute, not our launch.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from github_feedback import collect_feedback
from github_feedback import feedback as github_feedback_mod
from github_feedback.feedback import (
    MAINTENANCE_NOT_TRYABLE,
    WHOLE_THREAD,
    looks_like_maintenance_page,
    sanitize_inbound_facts,
    whole_thread_reason,
)
from github_survey import GhRunner, invalid_repo_reason
from github_survey.survey import look_bytes_over_limit, look_declared_gh, state_bytes_over_limit

from influenzer.brief_admit import already_told, open_story_reason
from influenzer.brief_scan import repo_is_archived, repo_is_empty, repo_is_fork, repo_is_private
from influenzer.config import load_config
from influenzer.domain import foreign_owner_reason, utc_now
from influenzer.envelope import noop, ok
from influenzer.fala_result import write_fala_result
from influenzer.hom import HomError, brief_from_mapping
from influenzer.playbook import (
    HN_CAMP_REASON,
    StoryKind,
    is_hn_camp_arena,
    looks_like_archived_repo,
    looks_like_empty_repo,
    looks_like_fork,
    looks_like_private_repo,
)
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
    project = repo.get_project(pid)
    maintainer = project.brand.maintainer if project is not None else None
    foreign = foreign_owner_reason(slug, maintainer)
    if foreign:
        return host_silence(foreign, project_id=pid, repo_slug=slug)
    return pid, slug


def admit_feedback(
    repo: StateRepository,
    payload: dict[str, Any],
    *,
    project_id: str,
    now: str | None = None,
) -> dict[str, Any]:
    slug = str(payload.get("repo") or "")
    if look_bytes_over_limit(payload) or state_bytes_over_limit(payload):
        return host_silence("empty_feedback", project_id=project_id, repo_slug=slug)
    if payload.get("status") != "ok":
        return host_silence(str(payload.get("reason") or "scan_failed"), project_id=project_id, repo_slug=slug)
    project = repo.get_project(project_id)
    maintainer = project.brand.maintainer if project is not None else None
    foreign = foreign_owner_reason(slug, maintainer)
    if foreign:
        return host_silence(foreign, project_id=project_id, repo_slug=slug)
    if bool(payload.get("isFork")):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isEmpty")):
        return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isPrivate")):
        return host_silence("private_repo", project_id=project_id, repo_slug=slug)
    if bool(payload.get("isArchived")) or bool(payload.get("isDisabled")):
        return host_silence("archived_repo", project_id=project_id, repo_slug=slug)
    blocked = open_story_reason(repo, project_id, now)
    if blocked == "social_draft" and is_hn_camp_arena(repo.living_stack_arena(project_id, now)):
        return host_silence(HN_CAMP_REASON, project_id=project_id, repo_slug=slug)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    if repo.list_operator_drafts(project_id):
        return host_silence("open_draft", project_id=project_id, repo_slug=slug)
    facts_raw = payload.get("facts")
    if not isinstance(facts_raw, list) or not facts_raw:
        return host_silence("comment_noise", project_id=project_id, repo_slug=slug)
    facts_raw = sanitize_inbound_facts(facts_raw)
    if not facts_raw:
        return host_silence("comment_noise", project_id=project_id, repo_slug=slug)
    packed = dict(payload)
    packed["facts"] = facts_raw
    if whole_thread_reason(packed):
        return host_silence(WHOLE_THREAD, project_id=project_id, repo_slug=slug)
    fact_blob = "\n".join(str(item.get("text") or "") for item in facts_raw if isinstance(item, dict))
    if looks_like_maintenance_page(fact_blob):
        return host_silence(MAINTENANCE_NOT_TRYABLE, project_id=project_id, repo_slug=slug)
    if looks_like_fork(fact_blob):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    if looks_like_empty_repo(fact_blob):
        return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
    if looks_like_private_repo(fact_blob):
        return host_silence("private_repo", project_id=project_id, repo_slug=slug)
    if looks_like_archived_repo(fact_blob):
        return host_silence("archived_repo", project_id=project_id, repo_slug=slug)
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
                "story_kind": StoryKind.HARD_ISSUE.value,
                "claims_ship": False,
                "tryable": False,
                "source": SOURCE,
                "created_at": created_at,
            }
        )
    except (HomError, ValueError):
        return host_silence("scan_failed", project_id=project_id, repo_slug=slug)
    try:
        raced = repo.admit_brief(brief, event_type="brief.feedback")
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
    blocked = open_story_reason(repo, pid, now)
    if blocked == "social_draft" and is_hn_camp_arena(repo.living_stack_arena(pid, now)):
        packed = collect_feedback(slug, gh=look_declared_gh(slug, gh) if gh is not None else None, now=now)
        if packed.get("status") != "ok":
            return host_silence(
                str(packed.get("reason") or HN_CAMP_REASON),
                project_id=pid,
                repo_slug=slug,
            )
        return host_silence(HN_CAMP_REASON, project_id=pid, repo_slug=slug)
    if blocked:
        return host_silence(blocked, project_id=pid, repo_slug=slug)
    if repo.list_operator_drafts(pid):
        return host_silence("open_draft", project_id=pid, repo_slug=slug)
    inner = gh if gh is not None else github_feedback_mod.run_gh
    if repo_is_fork(inner, slug):
        return host_silence("fork_not_a_site", project_id=pid, repo_slug=slug)
    if repo_is_empty(inner, slug):
        return host_silence("empty_repo_not_a_site", project_id=pid, repo_slug=slug)
    if repo_is_private(inner, slug):
        return host_silence("private_repo", project_id=pid, repo_slug=slug)
    if repo_is_archived(inner, slug):
        return host_silence("archived_repo", project_id=pid, repo_slug=slug)
    try:
        runner = look_declared_gh(slug, gh) if gh is not None else None
        packed = collect_feedback(slug, gh=runner, now=now)
    except Exception:
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
