"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Does not launch the project. Tryable is a README+URL heuristic, not a run.
Foreign and our own code in look is untrusted. Launching the project is silence.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from github_pack import pack_survey
from github_survey import GhCall, GhRunner, invalid_repo_reason, survey_public_repo
from github_survey.survey import look_short_gh

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository

_LAUNCH_HEADS = frozenset(
    {
        "uv",
        "pip",
        "pip3",
        "pipx",
        "python",
        "python3",
        "py",
        "node",
        "npm",
        "npx",
        "yarn",
        "pnpm",
        "bun",
        "deno",
        "cargo",
        "go",
        "make",
        "gmake",
        "cmake",
        "ninja",
        "meson",
        "docker",
        "docker-compose",
        "podman",
        "compose",
        "brew",
        "bash",
        "sh",
        "zsh",
        "fish",
        "cmd",
        "powershell",
        "pwsh",
    }
)
_LAUNCH_VERBS = frozenset({"run", "start", "serve", "dev", "install", "exec", "up"})


def _look_argv_tokens(argv: object) -> list[str] | None:
    if isinstance(argv, (bytes, bytearray)):
        try:
            argv = argv.decode("utf-8")
        except UnicodeDecodeError:
            return None
    if isinstance(argv, str):
        return argv.split()
    if isinstance(argv, Sequence):
        tokens: list[str] = []
        for item in argv:
            if isinstance(item, (bytes, bytearray)):
                try:
                    tokens.append(item.decode("utf-8"))
                except UnicodeDecodeError:
                    return None
            elif isinstance(item, str):
                tokens.append(item)
            else:
                return None
        return tokens
    return None


def look_argv_is_project_launch(argv: object) -> bool:
    """True when argv would install, start, or run the watched project on the host."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    if not tokens:
        return False
    lowered = [token.lower() for token in tokens]
    head = lowered[1] if lowered[0] == "gh" and len(lowered) > 1 else lowered[0]
    if head in _LAUNCH_HEADS:
        return True
    if any(token in _LAUNCH_VERBS for token in lowered):
        return True
    return any(token.startswith(("./", ".\\")) for token in lowered)


def look_only_gh(gh: GhRunner | None) -> GhRunner:
    """Look may only GET via gh api. Launching the project is silence, not a spawn."""
    runner = look_short_gh(gh)

    def _look(argv: Sequence[str]) -> GhCall:
        if look_argv_is_project_launch(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        return runner(argv)

    return _look


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


__all__ = ["SOURCE", "look_argv_is_project_launch", "look_only_gh", "scan_github"]
