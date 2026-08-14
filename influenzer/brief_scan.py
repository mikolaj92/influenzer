"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Reply and code are not this path.
Does not clone. Does not launch the project from a watch.
Tryable is a README+URL heuristic. Code in look (theirs or ours) is untrusted.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from github_pack import pack_survey
from github_survey import GhCall, GhRunner, invalid_repo_reason, survey_public_repo
from github_survey.gh import allowlisted_gh_argv, gh_argv

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository

# Clone / run / install of the watched tree. Look never spawns these.
# Tryable stays a README+URL heuristic, not proof we launched anything.
_PROJECT_LAUNCH_HEADS = frozenset(
    {
        "bash",
        "brew",
        "bun",
        "cargo",
        "cmake",
        "compose",
        "docker",
        "fish",
        "git",
        "go",
        "hatch",
        "make",
        "mise",
        "npm",
        "npx",
        "pdm",
        "pip",
        "pip3",
        "pipx",
        "pnpm",
        "podman",
        "poetry",
        "python",
        "python3",
        "rtx",
        "sh",
        "uv",
        "yarn",
        "zsh",
    }
)


def is_project_launch_argv(argv: Sequence[str]) -> bool:
    """True when argv would clone or run a project. Look refuses that."""
    if not argv or any(not isinstance(item, str) for item in argv):
        return False
    tokens = [item.strip() for item in argv if isinstance(item, str) and item.strip()]
    if not tokens:
        return False
    if any(token.lower() == "clone" for token in tokens):
        return True
    head = tokens[0].rsplit("/", 1)[-1].lower()
    if head.endswith(".exe"):
        head = head[:-4]
    return head in _PROJECT_LAUNCH_HEADS


def look_only_gh(gh: GhRunner | None) -> GhRunner | None:
    """Look may only GET. comment/label/close/push/clone/run is silence, not a spawn."""
    if gh is None:
        return None

    def _read_only(argv: Sequence[str]) -> GhCall:
        if is_project_launch_argv(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        child = gh_argv(argv)
        if child is None or not allowlisted_gh_argv(child):
            return GhCall(returncode=0, stdout="", stderr="")
        if is_project_launch_argv(child):
            return GhCall(returncode=0, stdout="", stderr="")
        return gh(argv)

    return _read_only


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
        packed = pack_survey(survey_public_repo(slug, gh=look_only_gh(gh), now=now))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    return admit_pack(repo, packed, project_id=project_id, now=now or utc_now())


__all__ = ["SOURCE", "is_project_launch_argv", "look_only_gh", "scan_github"]
