"""Injectable ``gh`` subprocess. Missing binary, auth, bad JSON, or non-UTF8 is silence, not a crash.

The child cwd is an empty temporary directory, never HOME and never the host
checkout. A cwd outside that empty temp is silence, not a spawn.

The child env is an allowlist, never the host world. A key outside that
allowlist does not reach the process. An env that is not isolated is
silence, not a spawn.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GH_TIMEOUT_S = 20.0
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_GH_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "TMPDIR",
        "TZ",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GH_HOST",
        "GH_ENTERPRISE_TOKEN",
        "GH_CONFIG_DIR",
    }
)
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


def decode_gh_bytes(blob: bytes | str | None) -> str:
    """UTF-8 only. Invalid bytes are empty, not a raised decode."""
    if blob is None:
        return ""
    if isinstance(blob, str):
        return blob
    try:
        return blob.decode("utf-8")
    except UnicodeDecodeError:
        return ""


def _resolved(path: Path) -> Path | None:
    try:
        return path.resolve()
    except OSError:
        return None


def _empty_dir(path: Path) -> bool:
    try:
        if not path.is_dir():
            return False
        next(path.iterdir())
    except StopIteration:
        return True
    except OSError:
        return False
    return False


def _under_system_temp(path: Path) -> bool:
    resolved = _resolved(path)
    tmp = _resolved(Path(tempfile.gettempdir()))
    if resolved is None or tmp is None:
        return False
    try:
        resolved.relative_to(tmp)
    except ValueError:
        return False
    return True


def _forbidden_host_path(path: Path) -> bool:
    resolved = _resolved(path)
    if resolved is None:
        return True
    home = _resolved(Path.home())
    host = _resolved(Path.cwd())
    if home is not None and resolved == home:
        return True
    if host is not None and resolved == host:
        return True
    return False


def _inside_host_checkout(path: Path) -> bool:
    resolved = _resolved(path)
    host = _resolved(Path.cwd())
    if resolved is None or host is None:
        return False
    try:
        resolved.relative_to(host)
    except ValueError:
        return False
    return True


def isolated_gh_cwd(path: Path) -> bool:
    """True only for an empty temporary directory that is not HOME or host cwd."""
    resolved = _resolved(path)
    if resolved is None:
        return False
    return (
        _under_system_temp(resolved)
        and _empty_dir(resolved)
        and not _forbidden_host_path(resolved)
        and not _inside_host_checkout(resolved)
    )


def isolated_gh_env(env: object) -> bool:
    """True only for an allowlisted env. The host world is silence."""
    if not isinstance(env, Mapping) or not env:
        return False
    path = env.get("PATH") if hasattr(env, "get") else None
    if not isinstance(path, str) or not path or "\x00" in path:
        return False
    for key, value in env.items():
        if not isinstance(key, str) or key not in _GH_ENV_ALLOWLIST:
            return False
        if not isinstance(value, str) or value == "" or "\x00" in value:
            return False
    return True


def gh_env(source: Mapping[str, str] | None = None) -> dict[str, str] | None:
    """Copy only the allowlisted keys. The host world is not a child env."""
    environ = os.environ if source is None else source
    if not isinstance(environ, Mapping):
        return None
    getter = getattr(environ, "get", None)
    if not callable(getter):
        return None
    child: dict[str, str] = {}
    for key in _GH_ENV_ALLOWLIST:
        value = getter(key)
        if value is None:
            continue
        if not isinstance(value, str) or "\x00" in value:
            return None
        if value == "":
            continue
        child[key] = value
    if not isolated_gh_env(child):
        return None
    return child


def _remove_gh_cwd(cwd: str | None) -> None:
    if cwd is None:
        return
    path = Path(cwd)
    resolved = _resolved(path)
    if resolved is None or not resolved.name.startswith("influenzer-gh-"):
        return
    if not _under_system_temp(resolved) or _forbidden_host_path(resolved) or _inside_host_checkout(resolved):
        return
    shutil.rmtree(cwd, ignore_errors=True)


def run_gh(argv: Sequence[str], *, timeout: float = GH_TIMEOUT_S) -> GhCall:
    cwd: str | None = None
    try:
        child_env = gh_env()
        if child_env is None or not isolated_gh_env(child_env):
            return GhCall(returncode=0, stdout="", stderr="")
        cwd = tempfile.mkdtemp(prefix="influenzer-gh-")
        if not isolated_gh_cwd(Path(cwd)):
            return GhCall(returncode=0, stdout="", stderr="")
        completed = subprocess.run(
            ["gh", *argv],
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=cwd,
            env=child_env,
        )
    except FileNotFoundError:
        return GhCall(returncode=127, stdout="", stderr="gh not found", missing=True)
    except OSError:
        return GhCall(returncode=127, stdout="", stderr="gh unavailable", missing=True)
    except subprocess.TimeoutExpired:
        return GhCall(returncode=124, stdout="", stderr="gh timeout")
    except UnicodeDecodeError:
        return GhCall(returncode=0, stdout="", stderr="")
    finally:
        _remove_gh_cwd(cwd)
    return GhCall(
        returncode=int(completed.returncode),
        stdout=decode_gh_bytes(completed.stdout),
        stderr=decode_gh_bytes(completed.stderr),
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


def loads_json(blob: str | bytes | bytearray | None) -> Any | None:
    if isinstance(blob, (bytes, bytearray)):
        blob = decode_gh_bytes(bytes(blob))
    if not isinstance(blob, str):
        return None
    try:
        return json.loads(blob)
    except (json.JSONDecodeError, UnicodeDecodeError):
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
