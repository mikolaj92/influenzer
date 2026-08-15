"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
"""

from __future__ import annotations

import json
from typing import Any

from github_pack import pack_survey
from github_survey import GhRunner, invalid_repo_reason, survey_public_repo
from github_survey.survey import look_declared_gh, look_short_gh

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository


def look_only_gh(gh: GhRunner | None, repo_slug: str | None = None) -> GhRunner:
    """Look may only GET the declared repo via gh api. After N pages, stop."""
    runner = look_short_gh(gh)
    slug = (repo_slug or "").strip()
    if not slug:
        return runner
    return look_declared_gh(slug, runner)


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
    try:
        packed = pack_survey(survey_public_repo(slug, gh=look_only_gh(gh, slug), now=now))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    return admit_pack(repo, packed, project_id=project_id, now=now or utc_now())


__all__ = ["SOURCE", "look_only_gh", "scan_github"]
