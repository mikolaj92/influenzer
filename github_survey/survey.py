"""Collect public merged PRs / releases / tags / README. No storage."""

from __future__ import annotations

import argparse
import base64
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from github_survey.gh import (
    PR_JSON_FIELDS,
    RELEASE_JSON_FIELDS,
    REPO_JSON_FIELDS,
    GhRunner,
    invalid_repo_reason,
    optional_json,
    required_json,
    run_gh,
)

LOOKBACK_DAYS = 7


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
    runner = gh if gh is not None else run_gh
    clock = parse_now(now)
    try:
        survey, reason = collect_survey(slug, gh=runner, now=clock)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
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
