"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not launch or run the project from watch. Tryable is a README+URL
heuristic, not a process we spawned. Foreign and our code in look is untrusted.
Reply and code are not this path.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from github_pack import pack_survey
from github_survey import GhCall, GhRunner, invalid_repo_reason, survey_public_repo
from github_survey import survey as github_survey_survey
from github_survey.gh import allowlisted_gh_argv, gh_argv

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository

_LAUNCH_HEADS = frozenset(
    {
        "bash",
        "bun",
        "bundle",
        "cargo",
        "cmake",
        "compose",
        "docker",
        "docker-compose",
        "env",
        "fish",
        "flask",
        "gem",
        "gmake",
        "go",
        "gunicorn",
        "influenzer",
        "make",
        "node",
        "nodejs",
        "npm",
        "npx",
        "open",
        "pip",
        "pip3",
        "pipx",
        "pnpm",
        "podman",
        "poetry",
        "python",
        "python3",
        "ruby",
        "sh",
        "uvicorn",
        "uv",
        "uvx",
        "xdg-open",
        "yarn",
        "zsh",
    }
)
_LAUNCH_VERBS = frozenset(
    {
        "apply",
        "build",
        "dev",
        "exec",
        "install",
        "run",
        "serve",
        "start",
        "up",
    }
)


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


def _token_basename(token: str) -> str:
    name = token.rsplit("/", 1)[-1].lower()
    if name.startswith("python3."):
        return "python3"
    return name


def look_argv_is_launch(argv: object) -> bool:
    """True when argv would launch or run a project on the host.

    Unparseable argv is a launch (fail closed). Look does not try the project.
    """
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    if not tokens:
        return False
    heads = [_token_basename(token) for token in tokens]
    if heads[0] == "gh":
        return False
    if heads[0] in _LAUNCH_HEADS or heads[0].startswith("python"):
        return True
    if heads[0] in {"env", "/usr/bin/env"} and any(
        _token_basename(token) in _LAUNCH_HEADS or _token_basename(token).startswith("python")
        for token in tokens[1:]
    ):
        return True
    return any(head in _LAUNCH_VERBS for head in heads)


def look_only_gh(gh: GhRunner | None) -> GhRunner:
    """Look may only GET. Launch/run, comment/label/close/push is silence."""
    runner = github_survey_survey.run_gh if gh is None else gh

    def _read_only(argv: Sequence[str]) -> GhCall:
        if look_argv_is_launch(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        child = gh_argv(argv)
        if child is None or not allowlisted_gh_argv(child):
            return GhCall(returncode=0, stdout="", stderr="")
        return runner(argv)

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


__all__ = ["SOURCE", "look_argv_is_launch", "look_only_gh", "scan_github"]
