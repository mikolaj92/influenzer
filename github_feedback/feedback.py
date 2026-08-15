"""Collect public issue/PR comments. No storage. No replies.

Feedback is gh api only. git clone / worktree on the host is silence.
Mini is not a checkout cache.
Look stops after N pages. Whole-repo history in one look is silence.

A fact is a short excerpt + comment/issue URL. One excerpt per thread.
The rest stays on GitHub. A whole thread in state.db is silence, not storage.
This is retention, not a timeout.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from datetime import timedelta
from pathlib import Path
from typing import Any

from github_survey.gh import (
    REPO_JSON_FIELDS,
    GhRunner,
    invalid_repo_reason,
    optional_json,
    required_json,
    run_gh,
)
from github_survey.survey import LOOKBACK_DAYS, in_window, look_short_gh, parse_now

SOURCE = "github-feedback"
MAX_FACTS = 8
MAX_FACT_CHARS = 240
# @login: prefix on a clipped body. Longer than this is a dump, not an excerpt.
MAX_STORED_FACT_CHARS = MAX_FACT_CHARS + 48
MIN_BODY_CHARS = 12
WHOLE_THREAD = "whole_thread"

_COMMENT_URL_RE = re.compile(
    r"^https://github\.com/"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<name>[A-Za-z0-9_.-]+)/"
    r"(?P<kind>issues|pull)/(?P<number>\d+)"
    r"(?:#(?P<anchor>issuecomment-\d+|discussion_r\d+|pullrequestreview-\d+|issue-\d+))?$",
    re.I,
)
_RAW_THREAD_FACT_KEYS = frozenset(
    {
        "body",
        "user",
        "comments",
        "timeline",
        "reactions",
        "issue",
        "pull_request",
        "review_comments",
        "html_url",
    }
)
_RAW_THREAD_PAYLOAD_KEYS = frozenset(
    {
        "comments",
        "survey",
        "timeline",
        "issue",
        "pull_request",
        "review_comments",
    }
)

_BOT_LOGINS = frozenset(
    {
        "dependabot",
        "dependabot[bot]",
        "renovate",
        "renovate[bot]",
        "github-actions",
        "github-actions[bot]",
        "codecov",
        "codecov[bot]",
        "imgbot",
        "imgbot[bot]",
        "greenkeeper",
        "snyk-bot",
        "copilot",
        "copilot[bot]",
        "sonarcloud",
        "sonarcloud[bot]",
    }
)
_THANKS_RE = re.compile(r"(?i)^\s*(?:thanks(?:\s+you)?|thank\s+you|ty|thx)(?:\s*[!.]*)?\s*$")
_LGTM_RE = re.compile(
    r"(?i)^\s*(?:lgtm|looks\s+good(?:\s+to\s+me)?|\+1|👍|:shipit:|ship\s+it|"
    r"approved|sgtm|nit(?:pick)?)\s*[!.]*\s*$"
)
_SIGNAL_RE = re.compile(
    r"(?i)\?|"
    r"\b(?:bug|broken|crash(?:es|ed|ing)?|error|fail(?:s|ed|ing|ure)?|"
    r"doesn'?t work|cannot|can'?t|regression|repro(?:duce)?|"
    r"stacktrace|exception|blocker?|disagree|wrong|this breaks|"
    r"how (?:do|does|can|should)|why (?:did|does|is|would|can))\b"
)


def _silence(reason: str, *, repo: str) -> dict[str, Any]:
    return {"status": "noop", "ok": True, "reason": reason, "repo": repo, "brief_id": None}


def _clip(text: str, limit: int = MAX_FACT_CHARS) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return collapsed[: limit - 3].rstrip() + "..."


def _thread_key(url: str) -> str | None:
    match = _COMMENT_URL_RE.fullmatch(url.strip().rstrip("/"))
    if match is None:
        return None
    return "/".join(
        (
            match.group("owner").lower(),
            match.group("name").lower(),
            match.group("kind").lower(),
            match.group("number"),
        )
    )


def is_feedback_excerpt_url(url: str) -> bool:
    return _thread_key(url) is not None


_EXCERPT_FACT_KEYS = frozenset({"kind", "text", "artifact_url"})


def _is_excerpt_shaped(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    if set(item) - _EXCERPT_FACT_KEYS:
        return False
    if any(key in item for key in _RAW_THREAD_FACT_KEYS):
        return False
    kind = str(item.get("kind") or "").strip().lower()
    if kind not in {"excerpt", "issue_comment", "pull_comment"}:
        return False
    text = str(item.get("text") or "").strip()
    url = str(item.get("artifact_url") or "").strip()
    if not text or not is_feedback_excerpt_url(url):
        return False
    if len(text) > MAX_STORED_FACT_CHARS:
        return False
    return True


def whole_thread_reason(payload: Any) -> str | None:
    """Silence when a pack would store a thread dump instead of excerpts."""
    if not isinstance(payload, dict):
        return WHOLE_THREAD
    if any(key in payload for key in _RAW_THREAD_PAYLOAD_KEYS):
        return WHOLE_THREAD
    facts = payload.get("facts")
    if not isinstance(facts, list) or not facts:
        return None
    seen_threads: set[str] = set()
    for item in facts:
        if not _is_excerpt_shaped(item):
            return WHOLE_THREAD
        key = _thread_key(str(item.get("artifact_url") or ""))
        if key is None or key in seen_threads:
            return WHOLE_THREAD
        seen_threads.add(key)
    return None


def _login(user: Any) -> str:
    if not isinstance(user, dict):
        return ""
    return str(user.get("login") or "").strip()


def is_bot_user(user: Any) -> bool:
    if not isinstance(user, dict):
        return True
    login = _login(user).lower()
    if str(user.get("type") or "") == "Bot":
        return True
    if not login:
        return True
    if login.endswith("[bot]"):
        return True
    return login in _BOT_LOGINS


def is_noise_body(text: str) -> bool:
    stripped = text.strip()
    if len(stripped) < MIN_BODY_CHARS:
        return True
    if _THANKS_RE.fullmatch(stripped):
        return True
    if _LGTM_RE.fullmatch(stripped):
        return True
    return False


def is_feedback_signal(text: str) -> bool:
    if is_noise_body(text):
        return False
    return bool(_SIGNAL_RE.search(text))


def is_noise_comment(item: dict[str, Any]) -> bool:
    if is_bot_user(item.get("user")):
        return True
    return not is_feedback_signal(str(item.get("body") or ""))


def _items(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []
    return [item for item in raw if isinstance(item, dict)]


def _comment_url(item: dict[str, Any]) -> str:
    return str(item.get("html_url") or "").strip()


def _fact_from_comment(item: dict[str, Any], *, kind: str) -> dict[str, Any] | None:
    if is_noise_comment(item):
        return None
    url = _comment_url(item)
    if not url.startswith("https://github.com/"):
        return None
    body = _clip(str(item.get("body") or ""))
    if not body:
        return None
    login = _login(item.get("user")) or "someone"
    return {
        "kind": kind,
        "text": f"@{login}: {body}",
        "artifact_url": url,
    }


def _brief_id(facts: list[dict[str, Any]]) -> str:
    first = str(facts[0].get("artifact_url") or "")
    match = re.search(r"(?:issuecomment-|discussion_r)(\d+)", first)
    if match:
        return f"fb-{match.group(1)}"[:63]
    digits = re.search(r"(\d+)$", first.rstrip("/"))
    if digits:
        return f"fb-{digits.group(1)}"[:63]
    return "fb-comments"


def collect_comments(repo_slug: str, *, gh: GhRunner, now: Any) -> tuple[dict[str, Any] | None, str | None]:
    meta, reason = required_json(gh(["repo", "view", repo_slug, "--json", REPO_JSON_FIELDS]))
    if reason:
        return None, "empty_feedback" if reason == "empty_survey" else reason
    if not isinstance(meta, dict):
        return None, "empty_feedback"
    if bool(meta.get("isPrivate")):
        return None, "private_repo"

    since = (now - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues_raw, reason = required_json(
        gh(["api", f"repos/{repo_slug}/issues/comments?per_page=100&since={since}"])
    )
    if reason:
        return None, "empty_feedback" if reason == "empty_survey" else reason
    pulls_raw = optional_json(
        gh(["api", f"repos/{repo_slug}/pulls/comments?per_page=100&since={since}"]),
        [],
    )
    comments: list[tuple[str, dict[str, Any]]] = []
    for item in _items(issues_raw):
        if in_window(str(item.get("created_at") or ""), now=now):
            comments.append(("issue_comment", item))
    for item in _items(pulls_raw):
        if in_window(str(item.get("created_at") or ""), now=now):
            comments.append(("pull_comment", item))
    comments.sort(key=lambda pair: str(pair[1].get("created_at") or ""))
    return {"comments": comments}, None


def pack_comments(repo_slug: str, collected: dict[str, Any]) -> dict[str, Any]:
    facts: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    seen_threads: set[str] = set()
    for kind, item in collected.get("comments") or []:
        fact = _fact_from_comment(item, kind=kind)
        if fact is None:
            continue
        url = str(fact.get("artifact_url") or "")
        thread = _thread_key(url)
        if not url or thread is None or url in seen_urls or thread in seen_threads:
            continue
        seen_urls.add(url)
        seen_threads.add(thread)
        facts.append(fact)
        if len(facts) >= MAX_FACTS:
            break
    if not facts:
        return _silence("comment_noise", repo=repo_slug)
    packed = {
        "status": "ok",
        "ok": True,
        "repo": repo_slug,
        "brief_id": _brief_id(facts),
        "source": SOURCE,
        "story_kind": "hard_issue",
        "claims_ship": False,
        "tryable": False,
        "facts": facts,
    }
    if whole_thread_reason(packed):
        return _silence(WHOLE_THREAD, repo=repo_slug)
    return packed


def collect_feedback(
    repo_slug: str,
    *,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return _silence("repo must be owner/name", repo=slug)
    runner = look_short_gh(run_gh if gh is None else gh)
    clock = parse_now(now)
    try:
        collected, reason = collect_comments(slug, gh=runner, now=clock)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return _silence("empty_feedback", repo=slug)
    except (OSError, TypeError, ValueError):
        return _silence("scan_failed", repo=slug)
    if reason:
        return _silence(reason, repo=slug)
    assert collected is not None
    packed = pack_comments(slug, collected)
    if packed.get("status") == "ok":
        packed["now"] = now or clock.isoformat().replace("+00:00", "Z")
    return packed


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
                    "reactions": [
                        {"kind": "github.feedback", "media_type": "application/json", "value": payload}
                    ],
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
    parser = argparse.ArgumentParser(prog="github-feedback")
    parser.add_argument("--repo", required=True, help="owner/name of a public GitHub repo")
    parser.add_argument("--now", help="ISO-8601 clock for the lookback window")
    parser.add_argument("--project-id", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    return _emit(collect_feedback(args.repo, now=args.now))


if __name__ == "__main__":
    raise SystemExit(main())
