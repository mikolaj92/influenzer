"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
A fork is not a website. isFork is silence, even when the owner is ours.
Angle comes from the canonical source, not a copy. Helping upstream is
silence here, not our launch.
"""

from __future__ import annotations

import json
from typing import Any

from github_pack import pack_survey
from github_survey import GhRunner, invalid_repo_reason, survey_public_repo
from github_survey.survey import look_declared_gh, look_short_gh
from influenzer.playbook import looks_like_fork

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository


def look_only_gh(gh: GhRunner | None, repo_slug: str | None = None) -> GhRunner:
    """Look may only GET the declared repo via gh api. Launching is silence."""
    runner = look_short_gh(gh)
    slug = (repo_slug or "").strip()
    if not slug:
        return runner
    return look_declared_gh(slug, runner)


def repo_is_fork(gh: GhRunner | None, repo_slug: str) -> bool:
    """True when gh says isFork. Owner does not matter. A copy is not a site."""
    slug = (repo_slug or "").strip()
    if not slug or invalid_repo_reason(slug):
        return False
    runner = look_only_gh(gh, slug)
    try:
        call = runner(["repo", "view", slug, "--json", "isFork"])
    except (OSError, TypeError, ValueError):
        return False
    raw = getattr(call, "stdout", "") or ""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and bool(data.get("isFork"))


def _payload_is_fork(payload: dict[str, Any]) -> bool:
    if bool(payload.get("isFork")):
        return True
    survey = payload.get("survey")
    if not isinstance(survey, dict):
        return False
    meta = survey.get("meta")
    bits: list[str] = []
    if isinstance(meta, dict):
        if bool(meta.get("isFork")):
            return True
        bits.append(str(meta.get("description") or ""))
    bits.append(str(survey.get("readme_text") or ""))
    return looks_like_fork("\n".join(bits))


def scan_github(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose survey → pack → admit. At most one pending brief, or silence."""
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return host_silence("repo must be owner/name", project_id=project_id, repo_slug=slug)
    blocked = open_story_reason(repo, project_id)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    runner = look_only_gh(gh, slug)
    if repo_is_fork(runner, slug):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    try:
        surveyed = survey_public_repo(slug, gh=runner, now=now)
        if _payload_is_fork(surveyed):
            return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
        packed = pack_survey(surveyed)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    return admit_pack(repo, packed, project_id=project_id, now=now or utc_now())


__all__ = ["SOURCE", "look_only_gh", "repo_is_fork", "scan_github"]
