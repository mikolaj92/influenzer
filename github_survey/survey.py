"""Collect public merged PRs / releases / tags / README. No storage.

Survey is gh api only. git clone / worktree on the host is silence.
Mini is not a checkout cache.
Look does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
A template repo is not a product. isTemplate, or generate-from-template
without an own ship, is silence. Show HN from boilerplate is silence.
An archived or disabled repo is dead. Watch on a museum is silence.
Do not launch a museum.
README/comments/JSON over the hard byte limit is an empty look, not a feast.
50MB in state.db is silence. The loop lives.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from github_survey.gh import (
    PR_JSON_FIELDS,
    RELEASE_JSON_FIELDS,
    REPO_JSON_FIELDS,
    GhCall,
    GhRunner,
    allowlisted_gh_argv,
    classify_gh_argv,
    gh_argv,
    invalid_repo_reason,
    optional_json,
    required_json,
    run_gh,
)

LOOKBACK_DAYS = 7
MAX_PAGES = 2
MAX_GH_LOOK_BYTES = 1 * 1024 * 1024
MAX_STATE_BYTES = 50 * 1024 * 1024
LOOK_OVER_LIMIT = "look_over_limit"
_GH_PAGE_SIZE = 100
_PAGED_KINDS = frozenset({"prs", "releases", "tags", "issue_comments", "pull_comments"})
_GIT_HEADS = frozenset({"git", "git-clone", "git-worktree"})
_CLONE_OR_WORKTREE = frozenset({"clone", "worktree"})
_SHIP_PR_TITLE_RE = re.compile(
    r"(?i)(?:^feat(?:ure)?(?:\([^)]*\))?:\s|"
    r"\b(?:ship(?:ped)?|launch(?:ed)?|released?)\b|"
    r"^add(?:ed)?\s)"
)
_TEMPLATE_PR_TITLE_RE = re.compile(
    r"(?i)\b(?:"
    r"generat(?:e|ed)\s+from(?:\s+a)?\s+template"
    r"|generate-from-template"
    r"|initial\s+commit\s+from(?:\s+a)?\s+template"
    r"|created\s+from(?:\s+a)?\s+template"
    r"|apply(?:ing)?\s+(?:the\s+)?template"
    r")\b"
)
_PROJECT_LAUNCH_HEADS = frozenset(
    {
        "python",
        "python2",
        "python3",
        "pypy",
        "pypy3",
        "uv",
        "pip",
        "pip3",
        "pipx",
        "poetry",
        "hatch",
        "pdm",
        "pixi",
        "rye",
        "npm",
        "npx",
        "pnpm",
        "yarn",
        "bun",
        "node",
        "deno",
        "cargo",
        "go",
        "make",
        "gmake",
        "cmake",
        "docker",
        "docker-compose",
        "compose",
        "podman",
        "bash",
        "sh",
        "zsh",
        "fish",
        "brew",
        "ruby",
        "perl",
        "php",
        "java",
        "gradle",
        "mvn",
        "open",
        "xdg-open",
        "osascript",
        "codespace",
        "devcontainer",
        "act",
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


def look_argv_is_clone_or_worktree(argv: object) -> bool:
    """True when argv would run git, clone, or make a worktree on the host."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    lowered = [token.lower() for token in tokens]
    if not lowered:
        return False
    if lowered[0] in _GIT_HEADS:
        return True
    if any(token in _CLONE_OR_WORKTREE for token in lowered):
        return True
    return any(token.startswith("--work-tree") for token in lowered)


def look_argv_launches_project(argv: object) -> bool:
    """True when argv would run the watched project. Launching is silence."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    if look_argv_is_clone_or_worktree(tokens):
        return True
    lowered = [token.lower() for token in tokens]
    if not lowered:
        return False
    head = Path(lowered[0]).name
    if head.endswith(".exe"):
        head = head[:-4]
    return head in _PROJECT_LAUNCH_HEADS


def look_api_only_gh(gh: GhRunner | None = None) -> GhRunner:
    """Survey/feedback only through gh api. clone/worktree/launch is silence."""
    runner = run_gh if gh is None else gh

    def _api_only(argv: Sequence[str]) -> GhCall:
        if look_argv_launches_project(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        child = gh_argv(argv)
        if child is None or not allowlisted_gh_argv(child):
            return GhCall(returncode=0, stdout="", stderr="")
        return runner(argv)

    return _api_only


def _look_api_query(tokens: Sequence[str]) -> dict[str, str]:
    path = ""
    for index, token in enumerate(tokens):
        if token == "api" and index + 1 < len(tokens):
            path = tokens[index + 1]
            break
        if token.startswith("repos/") and "?" in token:
            path = token
            break
    if "?" not in path:
        return {}
    query: dict[str, str] = {}
    for part in path.split("?", 1)[1].split("&"):
        if "=" not in part:
            continue
        key, value = part.split("=", 1)
        if key and key not in query:
            query[key] = value
    return query


def _flag_value(tokens: Sequence[str], flag: str) -> str | None:
    if flag not in tokens:
        return None
    index = tokens.index(flag)
    if index + 1 >= len(tokens):
        return ""
    return tokens[index + 1]


def _look_classify(argv: object) -> str:
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return "other"
    if tokens and tokens[0] == "gh":
        tokens = tokens[1:]
    return classify_gh_argv(tokens)


def _look_page_bucket(argv: object) -> str | None:
    kind = _look_classify(argv)
    if kind in _PAGED_KINDS:
        return kind
    return None


def _look_argv_page_number(argv: object) -> int | None:
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return None
    raw = _look_api_query(tokens).get("page")
    if raw is None:
        raw = _flag_value(tokens, "--page")
    if raw is None:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def look_argv_is_unbounded_pages(argv: object) -> bool:
    """True when argv would walk every GitHub page / whole repo history."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    lowered = [token.lower() for token in tokens]
    if any(token == "--paginate" or token.startswith("--paginate=") for token in lowered):
        return True
    raw_limit = _flag_value(tokens, "--limit")
    if raw_limit is not None:
        try:
            limit = int(raw_limit)
        except ValueError:
            return True
        if limit < 1 or limit > MAX_PAGES * _GH_PAGE_SIZE:
            return True
    return False


def _look_argv_repo_slug(argv: object) -> str | None:
    """Repo slug this argv would look at, if it carries one."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return None
    if tokens and tokens[0] == "gh":
        tokens = tokens[1:]
    if len(tokens) >= 3 and tokens[0] == "repo" and tokens[1] == "view":
        return tokens[2]
    if "--repo" in tokens:
        index = tokens.index("--repo")
        if index + 1 < len(tokens):
            return tokens[index + 1]
    if tokens[:1] == ["api"] and len(tokens) >= 2:
        path = tokens[1]
        lowered = path.lower()
        marker = "repos/"
        if lowered.startswith(marker):
            rest = path[len(marker) :]
        elif marker in lowered:
            rest = path[lowered.index(marker) + len(marker) :]
        else:
            return None
        parts = rest.split("/")
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1].split('?', 1)[0]}"
    return None


def look_argv_leaves_declared_repo(argv: object, declared: str) -> bool:
    """True when argv would survey a repo other than the declared watch."""
    tokens = _look_argv_tokens(argv)
    if tokens is None:
        return True
    wanted = declared.strip()
    if not wanted or invalid_repo_reason(wanted):
        return True
    slug = _look_argv_repo_slug(argv)
    if slug is None:
        return False
    if invalid_repo_reason(slug):
        return True
    return slug.strip().casefold() != wanted.casefold()


def look_declared_gh(repo_slug: str, gh: GhRunner | None = None) -> GhRunner:
    """Look stays on the declared repo. A foreign slug is silence, not a survey."""
    runner = gh if gh is not None else run_gh
    slug = repo_slug.strip()

    def _declared(argv: Sequence[str]) -> GhCall:
        if look_argv_leaves_declared_repo(argv, slug):
            return GhCall(returncode=0, stdout="", stderr="")
        return runner(argv)

    return _declared


def payload_byte_size(blob: object) -> int:
    """UTF-8 byte length of a gh blob or JSON payload. Unserializable is over."""
    if blob is None:
        return 0
    if isinstance(blob, (bytes, bytearray)):
        return len(blob)
    if isinstance(blob, str):
        return len(blob.encode("utf-8"))
    try:
        return len(json.dumps(blob, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return MAX_STATE_BYTES + 1


def look_bytes_over_limit(blob: object, *, limit: int | None = None) -> bool:
    """True when README/comments/JSON exceeds the hard look-byte cap."""
    cap = MAX_GH_LOOK_BYTES if limit is None else limit
    return payload_byte_size(blob) > cap


def state_bytes_over_limit(blob: object) -> bool:
    """True when a payload would put 50MB in state.db. Do not swallow."""
    return payload_byte_size(blob) > MAX_STATE_BYTES


def look_payload_reason(call: GhCall) -> str | None:
    """Empty look when a gh payload is over the hard byte limit."""
    if call.stderr == LOOK_OVER_LIMIT or look_bytes_over_limit(call.stdout) or look_bytes_over_limit(call.stderr):
        return "empty_survey"
    return None


def look_short_gh(gh: GhRunner | None = None) -> GhRunner:
    """Look is short. After MAX_PAGES, stop. Whole-history is silence.
    README/comments/JSON over the hard byte limit is an empty look."""
    runner = look_api_only_gh(gh)
    pages: dict[str, int] = {}

    def _short(argv: Sequence[str]) -> GhCall:
        if look_argv_is_unbounded_pages(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        bucket = _look_page_bucket(argv)
        if bucket is not None:
            used = pages.get(bucket, 0) + 1
            page = _look_argv_page_number(argv)
            ordinal = page if page is not None else used
            if used > MAX_PAGES or ordinal > MAX_PAGES:
                return GhCall(returncode=0, stdout="[]", stderr="")
            pages[bucket] = used
        call = runner(argv)
        if look_payload_reason(call):
            return GhCall(returncode=0, stdout="", stderr=LOOK_OVER_LIMIT)
        return call

    return _short


def parse_github_time(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_now(now: str | None) -> datetime:
    parsed = parse_github_time(now) if now else None
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def in_window(ts: str | None, *, now: datetime, days: int = LOOKBACK_DAYS) -> bool:
    parsed = parse_github_time(ts)
    if parsed is None:
        return False
    return parsed >= now - timedelta(days=days)


def decode_readme(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    encoding = str(payload.get("encoding") or "")
    content = payload.get("content")
    if encoding == "base64" and isinstance(content, str):
        try:
            raw = base64.b64decode(content, validate=False)
            return raw.decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError):
            return ""
    if isinstance(content, str):
        return content
    return ""


def _silence(reason: str, *, repo: str) -> dict[str, Any]:
    return {"status": "noop", "ok": True, "reason": reason, "repo": repo}


def _truthy_meta(meta: dict[str, Any], *keys: str) -> bool:
    for key in keys:
        value = meta.get(key)
        if isinstance(value, bool):
            if value:
                return True
            continue
        if isinstance(value, str) and value.strip().casefold() in {"true", "1", "yes"}:
            return True
        if isinstance(value, dict) and value:
            return True
        if isinstance(value, str) and value.strip() and key.casefold() != "istemplate":
            return True
    return False


def _looks_like_template_pr(item: dict[str, Any]) -> bool:
    blob = " ".join(
        str(item.get(key) or "")
        for key in ("title", "body")
    )
    return bool(_TEMPLATE_PR_TITLE_RE.search(blob))


def _looks_like_own_ship_pr(item: dict[str, Any]) -> bool:
    title = str(item.get("title") or "")
    if _looks_like_template_pr(item):
        return False
    return bool(_SHIP_PR_TITLE_RE.search(title))


def _flag_true(meta: dict[str, Any], *keys: str) -> bool:
    """True only for an explicit true tombstone. Unknown is not a museum."""
    for key in keys:
        value = meta.get(key)
        if value is True:
            return True
        if isinstance(value, str) and value.strip().casefold() in {"true", "1", "yes"}:
            return True
    return False


def _repo_is_dead(meta: dict[str, Any]) -> bool:
    """True when the repo is archived or disabled. A museum is not a launch."""
    if _flag_true(
        meta,
        "isArchived",
        "is_archived",
        "isDisabled",
        "is_disabled",
        "archived",
        "disabled",
    ):
        return True
    archived_at = meta.get("archivedAt") or meta.get("archived_at")
    return isinstance(archived_at, str) and bool(archived_at.strip())


def template_repo_silence(meta: dict[str, Any], *, prs: Sequence[Any], releases: Sequence[Any]) -> str | None:
    """A template, or generate-from-template without an own ship, is silence."""
    if _truthy_meta(meta, "isTemplate", "is_template"):
        return "template_not_a_product"
    generated = _truthy_meta(
        meta,
        "templateRepository",
        "template_repository",
        "parentRepository",
        "generatedFrom",
        "generated_from",
    )
    if not generated:
        return None
    own_prs = [item for item in prs if isinstance(item, dict) and _looks_like_own_ship_pr(item)]
    if releases or own_prs:
        return None
    return "template_not_a_product"


def collect_survey(repo_slug: str, *, gh: GhRunner, now: datetime) -> tuple[dict[str, Any] | None, str | None]:
    repo_call = gh(["repo", "view", repo_slug, "--json", f"{REPO_JSON_FIELDS},isArchived"])
    if look_payload_reason(repo_call):
        return None, "empty_survey"
    meta, reason = required_json(repo_call)
    if reason:
        return None, reason
    if not isinstance(meta, dict):
        return None, "empty_survey"
    if bool(meta.get("isPrivate")):
        return None, "private_repo"
    if _repo_is_dead(meta):
        return None, "archived_repo"
    if _truthy_meta(meta, "isTemplate", "is_template"):
        return None, "template_not_a_product"

    prs_call = gh(["pr", "list", "--repo", repo_slug, "--state", "merged", "--limit", "20", "--json", PR_JSON_FIELDS])
    if look_payload_reason(prs_call):
        return None, "empty_survey"
    prs_raw, reason = required_json(prs_call)
    if reason:
        return None, reason
    if not isinstance(prs_raw, list):
        return None, "empty_survey"

    rel_call = gh(
        [
            "release",
            "list",
            "--repo",
            repo_slug,
            "--limit",
            "10",
            "--exclude-drafts",
            "--exclude-pre-releases",
            "--json",
            RELEASE_JSON_FIELDS,
        ]
    )
    if look_payload_reason(rel_call):
        return None, "empty_survey"
    rel_raw, reason = required_json(rel_call)
    if reason:
        return None, reason
    if not isinstance(rel_raw, list):
        return None, "empty_survey"

    tags_call = gh(["api", f"repos/{repo_slug}/tags?per_page=20"])
    if look_payload_reason(tags_call):
        return None, "empty_survey"
    tags_raw = optional_json(tags_call, [])
    readme_call = gh(["api", f"repos/{repo_slug}/readme"])
    if look_payload_reason(readme_call):
        return None, "empty_survey"
    readme_raw = optional_json(readme_call, {})
    readme_text = decode_readme(readme_raw)
    if look_bytes_over_limit(readme_text):
        return None, "empty_survey"
    prs = [item for item in prs_raw if isinstance(item, dict)]
    releases = [item for item in rel_raw if isinstance(item, dict)]
    tags = [item for item in tags_raw if isinstance(item, dict)] if isinstance(tags_raw, list) else []
    recent_releases = []
    for item in releases:
        if bool(item.get("isDraft")) or bool(item.get("isPrerelease")):
            continue
        if not in_window(str(item.get("publishedAt") or ""), now=now):
            continue
        if not str(item.get("tagName") or "").strip():
            continue
        recent_releases.append(item)
    survey = {
        "meta": meta,
        "prs": [item for item in prs if in_window(str(item.get("mergedAt") or ""), now=now)],
        "releases": recent_releases,
        "tags": tags,
        "readme_text": readme_text,
        "readme_url": str((readme_raw or {}).get("html_url") or "") if isinstance(readme_raw, dict) else "",
    }
    if look_bytes_over_limit(survey) or state_bytes_over_limit(survey):
        return None, "empty_survey"
    return survey, None


def survey_public_repo(
    repo_slug: str,
    *,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return _silence("repo must be owner/name", repo=slug)
    runner = look_declared_gh(slug, look_short_gh(gh))
    clock = parse_now(now)
    try:
        survey, reason = collect_survey(slug, gh=runner, now=clock)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _silence("empty_survey", repo=slug)
    except (OSError, TypeError, ValueError):
        return _silence("scan_failed", repo=slug)
    if reason:
        return _silence(reason, repo=slug)
    assert survey is not None
    if not survey["releases"] and not survey["prs"] and not survey["tags"]:
        return _silence("empty_survey", repo=slug)
    if _repo_is_dead(survey["meta"]):
        return _silence("archived_repo", repo=slug)
    blocked = template_repo_silence(survey["meta"], prs=survey["prs"], releases=survey["releases"])
    if blocked:
        return _silence(blocked, repo=slug)
    stamp = now or clock.isoformat().replace("+00:00", "Z")
    payload = {
        "status": "ok",
        "ok": True,
        "repo": slug,
        "now": stamp,
        "survey": survey,
    }
    if look_bytes_over_limit(payload) or state_bytes_over_limit(payload):
        return _silence("empty_survey", repo=slug)
    return payload


def _emit(payload: dict[str, Any]) -> int:
    print(json.dumps(payload, sort_keys=True))
    output_dir = os.environ.get("FALA_EFFECTOR_OUTPUT_DIR")
    if output_dir:
        path = Path(output_dir) / "result.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "values": payload,
                    "associations": [],
                    "reactions": [{"kind": "github.survey", "media_type": "application/json", "value": payload}],
                    "metadata": {"published": False, "mutated": False},
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="github-survey")
    parser.add_argument("--repo", required=True, help="owner/name of a public GitHub repo")
    parser.add_argument("--now", help="ISO-8601 clock for the lookback window")
    args = parser.parse_args(argv)
    return _emit(survey_public_repo(args.repo, now=args.now))


if __name__ == "__main__":
    raise SystemExit(main())
