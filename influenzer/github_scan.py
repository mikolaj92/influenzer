"""GitHub → 0 or 1 pending HoM brief.

Explicit command. Tick still scores; this path never publishes or calls adapters.
Public signals only, via an injectable ``gh`` subprocess. Fail closed: silence
is a correct decision (missing gh, auth failure, noise, empty survey, one story
already in flight).
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from influenzer.domain import utc_now
from influenzer.envelope import noop, ok
from influenzer.hom import Brief, Fact, HomError, is_ship_artifact
from influenzer.playbook import (
    StoryKind,
    is_social_arena,
    looks_like_commit_noise,
    looks_like_waitlist,
)
from influenzer.storage import StateRepository, StorageError

LOOKBACK_DAYS = 7
SOURCE = "github-scan"
GH_TIMEOUT_S = 20.0

REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REPO_JSON_FIELDS = "nameWithOwner,isPrivate,url,description,homepageUrl"
PR_JSON_FIELDS = "number,title,url,mergedAt,body"
RELEASE_JSON_FIELDS = "tagName,name,isDraft,isPrerelease,publishedAt"

# Conventional / patch-only titles that are not a social story.
_PATCH_ONLY_RE = re.compile(
    r"(?i)^\s*(?:docs|style|test|refactor|build)(?:\([^)]*\))?:\s|"
    r"^\s*(?:fix(?:es)?\s+)?(?:a\s+)?typo\b|"
    r"\btypo\b|"
    r"^\s*patch\b"
)
_SHIP_TITLE_RE = re.compile(
    r"(?i)(?:^feat(?:ure)?(?:\([^)]*\))?:\s|"
    r"\b(?:ship(?:ped)?|launch(?:ed)?|released?)\b|"
    r"^add(?:ed)?\s)"
)
_INSTALL_RE = re.compile(
    r"(?i)\b(?:pip(?:x)? install|uv add|uv pip install|uv run|npm (?:i|install)|"
    r"pnpm add|yarn add|cargo install|go install|brew install)\b"
)
_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")


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
    """Default ``gh`` subprocess. Tests inject a fake runner instead."""
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


def _silence(reason: str, *, project_id: str, repo_slug: str, **extra: Any) -> dict[str, Any]:
    return noop(
        reason,
        published=False,
        project_id=project_id,
        repo=repo_slug,
        brief_id=None,
        source=SOURCE,
        **extra,
    )


def _parse_github_time(value: str | None) -> datetime | None:
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


def _parse_now(now: str | None) -> datetime:
    parsed = _parse_github_time(now) if now else None
    return parsed or datetime.now(timezone.utc).replace(microsecond=0)


def _in_window(ts: str | None, *, now: datetime, days: int = LOOKBACK_DAYS) -> bool:
    parsed = _parse_github_time(ts)
    if parsed is None:
        return False
    return parsed >= now - timedelta(days=days)


def _slug_fragment(raw: str) -> str:
    cleaned = _SLUG_CLEAN_RE.sub("-", raw.lower()).strip("-")
    return (cleaned[:40] or "story").strip("-") or "story"


def looks_like_patch_only(text: str) -> bool:
    stripped = text.strip()
    if looks_like_commit_noise(stripped):
        return True
    return bool(_PATCH_ONLY_RE.search(stripped))


def looks_like_ship_title(text: str) -> bool:
    if looks_like_patch_only(text):
        return False
    return bool(_SHIP_TITLE_RE.search(text.strip()))


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
    return "other"


def _loads_json(blob: str) -> Any | None:
    try:
        return json.loads(blob)
    except json.JSONDecodeError:
        return None


def _gh_reason(call: GhCall) -> str:
    if call.missing or call.returncode == 127:
        return "gh_missing"
    err = f"{call.stderr} {call.stdout}".lower()
    if call.returncode in {4, 1} and any(
        token in err for token in ("auth", "401", "403", "http 401", "http 403", "gh auth login")
    ):
        return "gh_auth"
    return "gh_error"


def _required_json(call: GhCall) -> tuple[Any | None, str | None]:
    if call.missing or call.returncode != 0:
        return None, _gh_reason(call)
    data = _loads_json(call.stdout)
    if data is None:
        return None, "empty_survey"
    return data, None


def _optional_json(call: GhCall, fallback: Any) -> Any:
    if call.missing or call.returncode != 0:
        return fallback
    data = _loads_json(call.stdout)
    return fallback if data is None else data


def _decode_readme(payload: Any) -> str:
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


def _release_url(repo_slug: str, tag: str) -> str:
    return f"https://github.com/{repo_slug}/releases/tag/{tag}"


def _readme_installable(text: str) -> bool:
    return bool(_INSTALL_RE.search(text))


def _project_has_pending_brief(repo: StateRepository, project_id: str) -> bool:
    return any(brief.project_id == project_id for brief in repo.list_pending_briefs(project_id))


def _project_has_social_draft(repo: StateRepository, project_id: str) -> bool:
    for draft in repo.list_operator_drafts(project_id):
        if is_social_arena(draft.arena):
            return True
    return False


def _already_told(repo: StateRepository, project_id: str, urls: Sequence[str], brief_id: str) -> bool:
    if repo.get_brief(project_id, brief_id) is not None:
        return True
    wanted = {url for url in urls if url}
    if not wanted:
        return False
    for brief in repo.list_briefs(project_id):
        for fact in brief.facts:
            if fact.artifact_url and fact.artifact_url in wanted:
                return True
    return False


def _survey(
    repo_slug: str,
    *,
    gh: GhRunner,
    now: datetime,
) -> tuple[dict[str, Any] | None, str | None]:
    repo_call = gh(
        ["repo", "view", repo_slug, "--json", REPO_JSON_FIELDS],
    )
    meta, reason = _required_json(repo_call)
    if reason:
        return None, reason
    if not isinstance(meta, dict):
        return None, "empty_survey"
    if bool(meta.get("isPrivate")):
        return None, "private_repo"

    prs_call = gh(
        [
            "pr",
            "list",
            "--repo",
            repo_slug,
            "--state",
            "merged",
            "--limit",
            "20",
            "--json",
            PR_JSON_FIELDS,
        ]
    )
    prs_raw, reason = _required_json(prs_call)
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
    rel_raw, reason = _required_json(rel_call)
    if reason:
        return None, reason
    if not isinstance(rel_raw, list):
        return None, "empty_survey"

    tags_raw = _optional_json(gh(["api", f"repos/{repo_slug}/tags?per_page=20"]), [])
    readme_raw = _optional_json(gh(["api", f"repos/{repo_slug}/readme"]), {})

    prs = [item for item in prs_raw if isinstance(item, dict)]
    releases = [item for item in rel_raw if isinstance(item, dict)]
    tags = [item for item in tags_raw if isinstance(item, dict)] if isinstance(tags_raw, list) else []
    readme_text = _decode_readme(readme_raw)

    recent_prs = [item for item in prs if _in_window(str(item.get("mergedAt") or ""), now=now)]
    recent_releases: list[dict[str, Any]] = []
    for item in releases:
        if bool(item.get("isDraft")) or bool(item.get("isPrerelease")):
            continue
        if not _in_window(str(item.get("publishedAt") or ""), now=now):
            continue
        tag = str(item.get("tagName") or "").strip()
        if not tag:
            continue
        recent_releases.append(item)

    return {
        "meta": meta,
        "prs": recent_prs,
        "releases": recent_releases,
        "tags": tags,
        "readme_text": readme_text,
        "readme_url": str((readme_raw or {}).get("html_url") or "") if isinstance(readme_raw, dict) else "",
    }, None


def _headline_prs(prs: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for item in prs:
        title = str(item.get("title") or "")
        url = str(item.get("url") or "").strip()
        if looks_like_patch_only(title):
            continue
        if not looks_like_ship_title(title):
            continue
        if not is_ship_artifact(url):
            continue
        found.append(item)
    return found


def _facts_from_survey(repo_slug: str, survey: dict[str, Any]) -> tuple[Fact, ...]:
    facts: list[Fact] = []
    seen_urls: set[str] = set()

    def add(fact: Fact) -> None:
        url = fact.artifact_url
        if url and url in seen_urls:
            return
        if url:
            seen_urls.add(url)
        facts.append(fact)

    for item in survey["releases"]:
        tag = str(item.get("tagName") or "").strip()
        name = str(item.get("name") or tag).strip() or tag
        url = _release_url(repo_slug, tag)
        add(Fact(kind="release", text=f"Released {name}", artifact_url=url))

    for item in _headline_prs(survey["prs"]):
        number = item.get("number")
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        label = f"Merged PR #{number}: {title}" if number is not None else title
        add(Fact(kind="pull", text=label, artifact_url=url))

    release_tags = {str(item.get("tagName") or "") for item in survey["releases"]}
    for item in survey["tags"]:
        name = str(item.get("name") or "").strip()
        if not name or name in release_tags or looks_like_patch_only(name):
            continue
        add(Fact(kind="tag", text=f"Tag {name}"))

    readme_text = str(survey.get("readme_text") or "")
    if _readme_installable(readme_text):
        url = str(survey.get("readme_url") or survey["meta"].get("url") or "")
        snippet = "README has an install/quickstart a stranger can run"
        add(
            Fact(
                kind="readme",
                text=snippet,
                artifact_url=url if url.startswith("https://") else None,
            )
        )

    description = str(survey["meta"].get("description") or "").strip()
    if description and len(description) >= 12:
        add(Fact(kind="signal", text=description[:240]))

    return tuple(facts[:8])


def _choose_brief_id(survey: dict[str, Any]) -> str:
    if survey["releases"]:
        tag = str(survey["releases"][0].get("tagName") or "release")
        return f"scan-{_slug_fragment(tag)}"[:63]
    headlines = _headline_prs(survey["prs"])
    if headlines:
        number = headlines[0].get("number")
        return f"scan-pr-{_slug_fragment(str(number if number is not None else 'pr'))}"[:63]
    return "scan-story"


def _is_tryable(survey: dict[str, Any], facts: Sequence[Fact]) -> bool:
    if survey["releases"]:
        return True
    if _readme_installable(str(survey.get("readme_text") or "")):
        return True
    return any(is_ship_artifact(fact.artifact_url) and fact.kind == "pull" for fact in facts)


def scan_github(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Survey public GitHub signals and store at most one pending brief.

    Never publishes. Never enables live social. Missing ``gh`` or an empty /
    noisy survey returns a silent noop envelope (exit-safe).
    """
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return _silence("repo must be owner/name", project_id=project_id, repo_slug=slug)
    if repo.get_project(project_id) is None:
        return _silence("project not found", project_id=project_id, repo_slug=slug)
    if _project_has_pending_brief(repo, project_id):
        return _silence("pending_brief", project_id=project_id, repo_slug=slug)
    if _project_has_social_draft(repo, project_id):
        return _silence("social_draft", project_id=project_id, repo_slug=slug)

    runner = gh if gh is not None else run_gh
    clock = _parse_now(now)
    try:
        survey, reason = _survey(slug, gh=runner, now=clock)
    except (OSError, TypeError, ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return _silence("scan_failed", project_id=project_id, repo_slug=slug)
    if reason:
        return _silence(reason, project_id=project_id, repo_slug=slug)
    assert survey is not None

    if not survey["releases"] and not survey["prs"] and not survey["tags"]:
        return _silence("empty_survey", project_id=project_id, repo_slug=slug)

    headlines = _headline_prs(survey["prs"])
    if not survey["releases"] and not headlines:
        return _silence("commit_noise", project_id=project_id, repo_slug=slug)

    try:
        facts = _facts_from_survey(slug, survey)
    except HomError:
        return _silence("scan_failed", project_id=project_id, repo_slug=slug)
    if not facts:
        return _silence("empty_survey", project_id=project_id, repo_slug=slug)

    blob = "\n".join(fact.text for fact in facts)
    if looks_like_waitlist(blob):
        return _silence("waitlist_not_tryable", project_id=project_id, repo_slug=slug)

    tryable = _is_tryable(survey, facts)
    claims_ship = any(is_ship_artifact(fact.artifact_url) for fact in facts)
    if not (claims_ship and tryable):
        return _silence("not_tryable", project_id=project_id, repo_slug=slug)

    brief_id = _choose_brief_id(survey)
    artifact_urls = tuple(url for url in (fact.artifact_url for fact in facts) if url)
    if _already_told(repo, project_id, artifact_urls, brief_id):
        return _silence("already_told", project_id=project_id, repo_slug=slug)

    created_at = now or utc_now()
    try:
        brief = Brief.create(
            project_id=project_id,
            brief_id=brief_id,
            facts=facts,
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            source=SOURCE,
            created_at=created_at,
        )
    except (HomError, ValueError):
        return _silence("scan_failed", project_id=project_id, repo_slug=slug)

    try:
        repo.save_brief(brief, event_type="brief.scanned")
    except StorageError:
        return _silence("already_told", project_id=project_id, repo_slug=slug)

    return ok(
        published=False,
        project_id=brief.project_id,
        brief_id=brief.brief_id,
        repo=slug,
        story_kind=brief.story_kind.value,
        source=brief.source,
        fact_count=len(brief.facts),
        claims_ship=True,
        tryable=True,
        pending=True,
    )


__all__ = [
    "LOOKBACK_DAYS",
    "SOURCE",
    "GhCall",
    "GhRunner",
    "classify_gh_argv",
    "invalid_repo_reason",
    "looks_like_patch_only",
    "looks_like_ship_title",
    "run_gh",
    "scan_github",
]
