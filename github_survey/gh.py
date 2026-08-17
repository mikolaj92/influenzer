"""Injectable ``gh`` subprocess. Missing binary, auth, bad JSON, or non-UTF8 is silence, not a crash.

The child cwd is an empty temporary directory, never HOME and never the host
checkout. A cwd outside that empty temp is silence, not a spawn.

gh is always an argv list, never a shell string. A watch slug is validated
before it reaches the process. A string from the database does not compose
a command.

GhRunner has a positive allowlist: read-only catalog (repo view, pr list,
release list, GET api). An argv outside that catalog is silence, not a
comment, label, close, or push. The catalog is the latch, not compose.

The child environment is an allowlist, never the host world. Host secrets
do not reach the process. Only what gh must have. An env outside the
allowlist is silence, not a spawn.
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
_LIMIT_RE = re.compile(r"^[1-9]\d{0,2}$")
_FIELDS_RE = re.compile(r"^[A-Za-z0-9_]+(?:,[A-Za-z0-9_]+)*$")
_SINCE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_SLUG_PATH = r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
_GH_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
GH_CHILD_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TZ",
        "TMPDIR",
        "GH_TOKEN",
        "GITHUB_TOKEN",
        "GH_ENTERPRISE_TOKEN",
        "GITHUB_ENTERPRISE_TOKEN",
        "GH_HOST",
        "GH_CONFIG_DIR",
        "GH_NO_UPDATE_NOTIFIER",
        "GH_PROMPT_DISABLED",
        "NO_COLOR",
        "XDG_CONFIG_HOME",
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
    if not isinstance(repo_slug, str) or not REPO_RE.fullmatch(repo_slug.strip()):
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


def _argv_repo_slug(argv: Sequence[str]) -> str | None:
    """Repo slug that would reach the child, if this argv carries one."""
    if len(argv) >= 4 and argv[0] == "gh" and argv[1] == "repo" and argv[2] == "view":
        return argv[3]
    if "--repo" in argv:
        index = argv.index("--repo")
        if index + 1 < len(argv):
            return argv[index + 1]
    if len(argv) >= 3 and argv[0] == "gh" and argv[1] == "api":
        parts = str(argv[2]).split("/")
        if len(parts) >= 3 and parts[0] == "repos":
            return f"{parts[1]}/{parts[2].split('?', 1)[0]}"
    return None


def gh_argv(argv: object) -> list[str] | None:
    """Build the child argv. A shell string is not a command."""
    if isinstance(argv, (str, bytes, bytearray)) or not isinstance(argv, Sequence):
        return None
    tokens = list(argv)
    if not tokens or any(not isinstance(item, str) or "\x00" in item for item in tokens):
        return None
    return ["gh", *tokens]


def isolated_gh_argv(argv: object) -> bool:
    """True only for an argv list headed by gh. A shell string is silence."""
    if isinstance(argv, (str, bytes, bytearray)) or not isinstance(argv, Sequence):
        return False
    if not argv or argv[0] != "gh":
        return False
    if any(not isinstance(item, str) or "\x00" in item for item in argv):
        return False
    slug = _argv_repo_slug(argv)
    if slug is not None and invalid_repo_reason(slug):
        return False
    return True


def _api_query(raw: str) -> dict[str, str] | None:
    if not raw:
        return {}
    query: dict[str, str] = {}
    for part in raw.split("&"):
        if "=" not in part:
            return None
        key, value = part.split("=", 1)
        if not key or key in query:
            return None
        query[key] = value
    return query


def _allowlisted_api_path(path: str) -> bool:
    """True only for a GET repos/... read. Method flags and writes are silence."""
    if not isinstance(path, str) or not path or path.startswith("/") or ".." in path:
        return False
    resource, separator, query = path.partition("?")
    if not resource or resource.endswith("/"):
        return False
    params = _api_query(query) if separator else {}
    if params is None:
        return False
    if re.fullmatch(rf"repos/{_SLUG_PATH}/readme", resource):
        return params == {}
    if re.fullmatch(rf"repos/{_SLUG_PATH}/tags", resource):
        return set(params) <= {"per_page"} and all(_LIMIT_RE.fullmatch(value) for value in params.values())
    if re.fullmatch(rf"repos/{_SLUG_PATH}/issues/comments", resource) or re.fullmatch(
        rf"repos/{_SLUG_PATH}/pulls/comments", resource
    ):
        allowed = {"per_page", "since"}
        if not set(params) <= allowed:
            return False
        if "per_page" in params and not _LIMIT_RE.fullmatch(params["per_page"]):
            return False
        if "since" in params and not _SINCE_RE.fullmatch(params["since"]):
            return False
        return True
    if re.fullmatch(rf"repos/{_SLUG_PATH}/issues", resource):
        allowed = {"per_page", "since", "state"}
        if not set(params) <= allowed:
            return False
        if params.get("state") != "open":
            return False
        if "per_page" in params and not _LIMIT_RE.fullmatch(params["per_page"]):
            return False
        if "since" in params and not _SINCE_RE.fullmatch(params["since"]):
            return False
        return True
    return False


def _flag_pairs(tokens: Sequence[str], *, allowed: frozenset[str]) -> dict[str, str] | None:
    if len(tokens) % 2 != 0:
        return None
    pairs: dict[str, str] = {}
    for index in range(0, len(tokens), 2):
        flag, value = tokens[index], tokens[index + 1]
        if flag not in allowed or flag in pairs or not isinstance(value, str) or value.startswith("-"):
            return None
        pairs[flag] = value
    return pairs


def _allowlisted_repo_view(rest: Sequence[str]) -> bool:
    if rest[:2] != ["repo", "view"] or len(rest) < 3:
        return False
    if invalid_repo_reason(rest[2]) is not None:
        return False
    if len(rest) == 3:
        return True
    return len(rest) == 5 and rest[3] == "--json" and bool(_FIELDS_RE.fullmatch(rest[4]))


def _allowlisted_pr_list(rest: Sequence[str]) -> bool:
    if rest[:2] != ["pr", "list"]:
        return False
    pairs = _flag_pairs(rest[2:], allowed=frozenset({"--repo", "--state", "--limit", "--json"}))
    if pairs is None or "--repo" not in pairs:
        return False
    if invalid_repo_reason(pairs["--repo"]) is not None:
        return False
    if "--state" in pairs and pairs["--state"] != "merged":
        return False
    if "--limit" in pairs and not _LIMIT_RE.fullmatch(pairs["--limit"]):
        return False
    if "--json" in pairs and not _FIELDS_RE.fullmatch(pairs["--json"]):
        return False
    return True


def _allowlisted_release_list(rest: Sequence[str]) -> bool:
    if rest[:2] != ["release", "list"]:
        return False
    tokens = list(rest[2:])
    switches = {"--exclude-drafts", "--exclude-pre-releases"}
    flags: list[str] = []
    for token in tokens:
        if token in switches:
            continue
        flags.append(token)
    pairs = _flag_pairs(flags, allowed=frozenset({"--repo", "--limit", "--json"}))
    if pairs is None or "--repo" not in pairs:
        return False
    if invalid_repo_reason(pairs["--repo"]) is not None:
        return False
    if "--limit" in pairs and not _LIMIT_RE.fullmatch(pairs["--limit"]):
        return False
    if "--json" in pairs and not _FIELDS_RE.fullmatch(pairs["--json"]):
        return False
    return True


def allowlisted_gh_argv(argv: object) -> bool:
    """True only for the read-only catalog. comment/label/close/push is silence."""
    if not isolated_gh_argv(argv):
        return False
    rest = list(argv)[1:]
    if _allowlisted_repo_view(rest):
        return True
    if _allowlisted_pr_list(rest):
        return True
    if _allowlisted_release_list(rest):
        return True
    if rest[:1] == ["api"] and len(rest) == 2:
        return _allowlisted_api_path(rest[1])
    return False


def _allowlisted_env_item(key: object, value: object) -> bool:
    if not isinstance(key, str) or not isinstance(value, str):
        return False
    if not _GH_ENV_NAME.fullmatch(key) or key not in GH_CHILD_ENV_ALLOWLIST:
        return False
    if "\x00" in key or "\x00" in value:
        return False
    return True


def gh_child_env(environ: Mapping[str, str] | None = None) -> dict[str, str]:
    """Copy only the gh allowlist. Host secrets stay on the host."""
    source = os.environ if environ is None else environ
    child: dict[str, str] = {}
    for key, value in source.items():
        if _allowlisted_env_item(key, value):
            child[key] = value
    child.setdefault("GH_PROMPT_DISABLED", "1")
    child.setdefault("GH_NO_UPDATE_NOTIFIER", "1")
    return child


def isolated_gh_env(environ: object) -> bool:
    """True only when every key is on the allowlist. The host world is silence."""
    if not isinstance(environ, Mapping):
        return False
    if not environ:
        return False
    for key, value in environ.items():
        if not _allowlisted_env_item(key, value):
            return False
    return True


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
        child_argv = gh_argv(argv)
        if child_argv is None or not isolated_gh_argv(child_argv) or not allowlisted_gh_argv(child_argv):
            return GhCall(returncode=0, stdout="", stderr="")
        child_env = gh_child_env()
        if not isolated_gh_env(child_env):
            return GhCall(returncode=0, stdout="", stderr="")
        cwd = tempfile.mkdtemp(prefix="influenzer-gh-")
        if not isolated_gh_cwd(Path(cwd)):
            return GhCall(returncode=0, stdout="", stderr="")
        completed = subprocess.run(
            child_argv,
            capture_output=True,
            timeout=timeout,
            check=False,
            cwd=cwd,
            shell=False,
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
        if "/issues" in path:
            return "issues"
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
