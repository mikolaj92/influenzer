"""Ship vs patch/typo/chore noise. Waitlist is not a ship. A merge log is not a ship."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

_PATCH_ONLY_RE = re.compile(
    r"(?i)^\s*(?:docs|style|test|refactor|build)(?:\([^)]*\))?:\s|"
    r"^\s*(?:fix(?:es)?\s+)?(?:a\s+)?typo\b|"
    r"\btypo\b|"
    r"^\s*patch\b"
)
_COMMIT_NOISE_RE = re.compile(
    r"(?i)^\s*(?:chore|typo|lint|ci|wip|bump\s+(?:version|deps)|fix(?:es)?\s+tests|merge\s+branch)\b"
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
_WAITLIST_RE = re.compile(
    r"(?i)\b(?:waitlist|coming soon|join the (?:beta|waitlist)|landing page|no demo)\b"
)
_SHIP_ARTIFACT_RE = re.compile(
    r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:pull/\d+|issues/\d+|releases(?:/tag/[A-Za-z0-9._~-]+|/\d+))$"
)
_MERGED_PR_FACT_RE = re.compile(r"(?i)^merged\s+pr\s+#\d+")


def looks_like_patch_only(text: str) -> bool:
    stripped = text.strip()
    if _COMMIT_NOISE_RE.search(stripped):
        return True
    return bool(_PATCH_ONLY_RE.search(stripped))


def looks_like_ship_title(text: str) -> bool:
    if looks_like_patch_only(text):
        return False
    return bool(_SHIP_TITLE_RE.search(text.strip()))


def looks_like_waitlist(text: str) -> bool:
    return bool(_WAITLIST_RE.search(text))


def is_ship_artifact(url: str | None) -> bool:
    if not url:
        return False
    return bool(_SHIP_ARTIFACT_RE.fullmatch(url.strip()))


def headline_prs(prs: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
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
        found.append(dict(item))
    return found


def readme_installable(text: str) -> bool:
    return bool(_INSTALL_RE.search(text))


def looks_like_merged_pr_fact(text: str) -> bool:
    return bool(_MERGED_PR_FACT_RE.match(text.strip()))


def facts_are_merge_log(facts: Sequence[Mapping[str, Any]]) -> bool:
    """A stack of 'Merged PR #N: …' is changelog, not a tryable ship."""
    meat = [str(item.get("text") or "").strip() for item in facts if str(item.get("text") or "").strip()]
    if not meat:
        return False
    merge = [text for text in meat if looks_like_merged_pr_fact(text)]
    if not merge:
        return False
    return looks_like_merged_pr_fact(meat[0]) or len(merge) == len(meat)


def is_tryable(survey: Mapping[str, Any], facts: Sequence[Mapping[str, Any]]) -> bool:
    if facts_are_merge_log(facts) and not survey.get("releases"):
        return False
    if survey.get("releases"):
        return True
    if readme_installable(str(survey.get("readme_text") or "")):
        return True
    return False
