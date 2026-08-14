"""Collect public merged PRs / releases / tags / README. No storage.

Survey is gh api only. git clone / worktree on the host is silence.
Mini is not a checkout cache.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
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
    gh_argv,
    invalid_repo_reason,
    optional_json,
    required_json,
    run_gh,
)

LOOKBACK_DAYS = 7
_GIT_HEADS = frozenset({"git", "git-clone", "git-worktree"})
_CLONE_OR_WORKTREE = frozenset({"clone", "worktree"})


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


def look_api_only_gh(gh: GhRunner | None = None) -> GhRunner:
    """Survey/feedback only through gh api. clone/worktree is silence, not a spawn."""
    runner = run_gh if gh is None else gh

    def _api_only(argv: Sequence[str]) -> GhCall:
        if look_argv_is_clone_or_worktree(argv):
            return GhCall(returncode=0, stdout="", stderr="")
        child = gh_argv(argv)
        if child is None or not allowlisted_gh_argv(child):
            return GhCall(returncode=0, stdout="", stderr="")
        return runner(argv)

    return _api_only


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


def collect_survey(repo_slug: str, *, gh: GhRunner, now: datetime) -> tuple[dict[str, Any] | None, str | None]:
    meta, reason = required_json(gh(["repo", "view", repo_slug, "--json", REPO_JSON_FIELDS]))
    if reason:
        return None, reason
    if not isinstance(meta, dict):
        return None, "empty_survey"
    if bool(meta.get("isPrivate")):
        return None, "private_repo"

    prs_raw, reason = required_json(
        gh(["pr", "list", "--repo", repo_slug, "--state", "merged", "--limit", "20", "--json", PR_JSON_FIELDS])
    )
    if reason:
        return None, reason
    if not isinstance(prs_raw, list):
        return None, "empty_survey"

    rel_raw, reason = required_json(
        gh(
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
    )
    if reason:
        return None, reason
    if not isinstance(rel_raw, list):
        return None, "empty_survey"

    tags_raw = optional_json(gh(["api", f"repos/{repo_slug}/tags?per_page=20"]), [])
    readme_raw = optional_json(gh(["api", f"repos/{repo_slug}/readme"]), {})
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
    return {
        "meta": meta,
        "prs": [item for item in prs if in_window(str(item.get("mergedAt") or ""), now=now)],
        "releases": recent_releases,
        "tags": tags,
        "readme_text": decode_readme(readme_raw),
        "readme_url": str((readme_raw or {}).get("html_url") or "") if isinstance(readme_raw, dict) else "",
    }, None


def survey_public_repo(
    repo_slug: str,
    *,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return _silence("repo must be owner/name", repo=slug)
    runner = look_api_only_gh(gh)
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
    stamp = now or clock.isoformat().replace("+00:00", "Z")
    return {
        "status": "ok",
        "ok": True,
        "repo": slug,
        "now": stamp,
        "survey": survey,
    }


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
