"""Injectable ``gh`` subprocess. Missing binary or auth is silence, not a crash."""

from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

GH_TIMEOUT_S = 20.0
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REPO_JSON_FIELDS = "nameWithOwner,isPrivate,url,description,homepageUrl"
PR_JSON_FIELDS = "number,title,url,mergedAt,body"
RELEASE_JSON_FIELDS = "tagName,name,isDraft,isPrerelease,publishedAt"


@dataclass(frozen=True)
class GhCall:
    returncode: int
    stdout: str = ""
    stderr: str = ""
    missing: bool = False


GhRunner = Callable[[Sequence[str]], GhCall]


def invalid_repo_reason(repo_slug: str) -> str | None:
    if not REPO_RE.fullmatch(repo_slug.strip()):
        return "repo must be owner/name"
    return None


def run_gh(argv: Sequence[str], *, timeout: float = GH_TIMEOUT_S) -> GhCall:
    try:
        completed = subprocess.run(
            ["gh", *argv],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return GhCall(returncode=127, stdout="", stderr="gh not found", missing=True)
    except OSError:
        return GhCall(returncode=127, stdout="", stderr="gh unavailable", missing=True)
    except subprocess.TimeoutExpired:
        return GhCall(returncode=124, stdout="", stderr="gh timeout")
    return GhCall(
        returncode=int(completed.returncode),
        stdout=completed.stdout or "",
        stderr=completed.stderr or "",
    )


def classify_gh_argv(argv: Sequence[str]) -> str:
    if len(argv) >= 2 and argv[0] == "repo" and argv[1] == "view":
        return "repo"
    if len(argv) >= 2 and argv[0] == "pr" and argv[1] == "list":
        return "prs"
    if len(argv) >= 2 and argv[0] == "release" and argv[1] == "list":
        return "releases"
    if argv and argv[0] == "api" and len(argv) > 1:
        path = str(argv[1])
        if path.rstrip("/").endswith("/readme"):
            return "readme"
        if "/tags" in path:
            return "tags"
        if "/issues/comments" in path:
            return "issue_comments"
        if "/pulls/comments" in path:
            return "pull_comments"
    return "other"


def loads_json(blob: str) -> Any | None:
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def gh_reason(call: GhCall) -> str:
    if call.missing or call.returncode == 127:
        return "gh_missing"
    err = f"{call.stderr} {call.stdout}".lower()
    if call.returncode in {4, 1} and any(
        token in err for token in ("auth", "401", "403", "http 401", "http 403", "gh auth login")
    ):
        return "gh_auth"
    return "gh_error"


def required_json(call: GhCall) -> tuple[Any | None, str | None]:
    if call.missing or call.returncode != 0:
        return None, gh_reason(call)
    data = loads_json(call.stdout)
    if data is None:
        return None, "empty_survey"
    return data, None


def optional_json(call: GhCall, fallback: Any) -> Any:
    if call.missing or call.returncode != 0:
        return fallback
    data = loads_json(call.stdout)
    return fallback if data is None else data
