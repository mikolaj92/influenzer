"""Pack a survey into ship+tryable facts, or silence. No gh. No SQLite.

Tryable is a README+URL heuristic. Look does not run the project.
Launching on watch is silence. Code in look is untrusted.
A GitHub workshop README is one screen: one-liner, visible demo
(GIF/screenshot), copyable quickstart. Text without an image is
changelog, not a launch. A prose mention of pip/uv/brew is not a
start: HN/X stay silent without a one-liner a stranger can copy.
A merge and a revert of the same change in the look window is not
a ship: the thing is already gone from main. A star / upvote / follow
/ RT ask is silence, not a social angle. Inbound titles/descriptions
are data, not a command. Pack cuts instructions ("zpostuj to",
"ignore scoring"), leaves content. Our score stays ours.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

from github_pack.classify import (
    facts_are_merge_log,
    headline_prs,
    is_ship_artifact,
    is_trusted_artifact_url,
    is_tryable,
    looks_like_patch_only,
    looks_like_ship_title,
    looks_like_waitlist,
    looks_like_event,
    looks_like_calendar_filler,
    looks_like_counter_thanks,
    looks_like_fog,
    looks_like_founder_journal,
    looks_like_lead_magnet,
    readme_tryable_url,
)

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_URL_IN_TEXT_RE = re.compile(r"https?://\S+", re.I)
_LOGIN_PREFIX_RE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9_-]{0,38}:\s*")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)\s]+)(?:\s+[^)]*)?\)")
_HTML_IMG_RE = re.compile(
    r"(?i)<img\b[^>]*\bsrc\s*=\s*['\"]?([^'\"\s>]+)"
)
_DEMO_EXT_RE = re.compile(r"(?i)\.(?:gif|png|webp|jpe?g|apng)(?:\?|#|$)")
_ATTACHMENT_RE = re.compile(
    r"(?i)(?:github\.com/user-attachments/assets/|user-images\.githubusercontent\.com/)"
)
_BADGE_OR_LOGO_RE = re.compile(
    r"(?i)\b(?:logo|badge|shield|icon|favicon|stars?)\b|shields\.io|img\.shields"
)
README_WITHOUT_DEMO_REASON = "readme_without_demo"
README_WITHOUT_QUICKSTART_REASON = "readme_without_quickstart"
REVERTED_NOT_A_SHIP_REASON = "reverted_not_a_ship"
SOLICIT_GESTURE_REASON = "solicit_gesture"
_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_COPYABLE_START_RE = re.compile(
    r"(?im)^\s*(?:\$\s*)?(?:pip(?:x)? install|uv add|uv pip install|uv run|"
    r"npm (?:i|install)|pnpm add|yarn add|cargo install|go install|brew install)\b"
)
_REVERT_PREFIX_RE = re.compile(r"(?i)^\s*revert(?:s|ed|ing)?\b[\s:]*")
_PR_NUMBER_RE = re.compile(r"(?i)(?:\bpr\s*#?|#|/pull/)(\d+)\b")
_QUOTED_RE = re.compile(r"[\"“”'«»](.+?)[\"“”'«»]")
# Comment/issue/title copy is data. These shapes are an order, not a fact.
_INBOUND_INSTRUCTION_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:please\s+)?(?:ignore|skip|bypass|disable|turn\s+off)\s+"
    r"(?:all\s+)?(?:scoring|the\s+score|scores?|playbook|gates?|policy|verdict|rules?)\b|"
    r"\b(?:do\s+not|don't|dont)\s+(?:score|use\s+(?:the\s+)?(?:playbook|scoring))\b|"
    r"\bzpostuj(?:cie|my)?(?:\s+to)?\b|"
    r"\b(?:just\s+)?(?:go\s+)?(?:post|tweet|publish)\s+(?:this|that|it)\b|"
    r"\bignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?\b|"
    r"\bsystem\s+prompt\b|"
    r"\bnie\s+(?:punktuj|score(?:uj)?)\b|"
    r"\bzignoruj\s+(?:scoring|punktacj\w*|playbook|score)\b|"
    r"\bopublikuj\s+to\b"
    r")"
)
# Star / upvote / follow / RT ask is silence. "Follow the README" stays.
_SOLICIT_GESTURE_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:please\s+)?(?:star|upvote|rt|retweet)\s+"
    r"(?:us|me|this|it|the\s+(?:repo|project|post)|if)\b|"
    r"\b(?:please\s+)?follow\s+(?:us|me|our\s+\w+|for(?:\s+more)?|and\s+subscribe)\b|"
    r"\b(?:give|leave|drop|add|hit)\s+(?:us\s+|it\s+)?(?:a\s+|an\s+)?"
    r"(?:star|upvote|follow|rt|retweet|like|gwiazdk\w*)\b|"
    r"\bstar\s+the\s+(?:repo|project)\b|"
    r"\bplease\s+(?:star|upvote|follow|rt|retweet)\b|"
    r"\b(?:rt|retweet)\s+this\b|"
    r"\bdaj(?:cie)?\s+(?:nam\s+)?(?:gwiazdk\w*|follow|rt|lajk\w*|upvote)\b|"
    r"\bzostaw(?:cie)?\s+(?:nam\s+)?(?:gwiazdk\w*|lajk\w*|follow|rt)\b|"
    r"\bobserwuj(?:cie)?\s+(?:nas|mnie)\b|"
    r"\bprosimy\s+o\s+(?:gwiazdk|follow|upvote|rt|lajk)"
    r")"
)


def _slug_fragment(raw: str) -> str:
    cleaned = _SLUG_CLEAN_RE.sub("-", raw.lower()).strip("-")
    return (cleaned[:40] or "story").strip("-") or "story"


def _release_url(repo_slug: str, tag: str) -> str:
    return f"https://github.com/{repo_slug}/releases/tag/{tag}"


def _silence(reason: str, *, repo: str) -> dict[str, Any]:
    return {"status": "noop", "ok": True, "reason": reason, "repo": repo, "brief_id": None}


def looks_like_inbound_instruction(text: str) -> bool:
    return bool(text and _INBOUND_INSTRUCTION_RE.search(text))


def looks_like_solicit_gesture(text: str) -> bool:
    """True for a star / upvote / follow / RT ask. Follow-the-README stays."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(_SOLICIT_GESTURE_RE.search(cleaned))


def strip_inbound_instructions(text: str) -> str:
    """Cut command-like inbound. Content stays. Empty after strip is silence."""
    if not text or not looks_like_inbound_instruction(text):
        return text
    parts: list[str] = []
    last = 0
    for match in _URL_IN_TEXT_RE.finditer(text):
        parts.append(_INBOUND_INSTRUCTION_RE.sub(" ", text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_INBOUND_INSTRUCTION_RE.sub(" ", text[last:]))
    cleaned = "".join(parts)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r" +([,.;:])", r"\1", cleaned)
    return cleaned.strip(" \t,;:.-")


def _image_candidates(text: str) -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    for match in _MD_IMAGE_RE.finditer(text):
        found.append((match.group(1), match.group(2)))
    for match in _HTML_IMG_RE.finditer(text):
        found.append(("", match.group(1)))
    return found


def _looks_like_visible_demo(alt: str, src: str) -> bool:
    blob = f"{alt} {src}"
    if _BADGE_OR_LOGO_RE.search(blob):
        return False
    return bool(_DEMO_EXT_RE.search(src) or _ATTACHMENT_RE.search(src))


def readme_has_visible_demo(text: str) -> bool:
    """True for a GIF/screenshot on the README. A badge or logo is not a demo."""
    if not text:
        return False
    return any(_looks_like_visible_demo(alt, src) for alt, src in _image_candidates(text))


def _fenced_code_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    i = 0
    while True:
        start = text.find("```", i)
        if start < 0:
            break
        nl = text.find("\n", start + 3)
        if nl < 0:
            break
        end = text.find("```", nl + 1)
        if end < 0:
            break
        blocks.append(text[nl + 1 : end])
        i = end + 3
    return blocks


def _copyable_chunks(text: str) -> list[str]:
    chunks = list(_fenced_code_blocks(text))
    chunks.extend(match.group(1) for match in _INLINE_CODE_RE.finditer(text))
    return chunks


def readme_has_copyable_start(text: str) -> bool:
    """True for a copyable uv/pip/brew one-liner. A prose mention is not a start."""
    if not text:
        return False
    return any(_COPYABLE_START_RE.search(chunk) for chunk in _copyable_chunks(text))


def _norm_title(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.casefold()).strip()


def _pr_number(item: Any) -> str | None:
    if not isinstance(item, dict):
        return None
    number = item.get("number")
    if number is not None and str(number).strip().isdigit():
        return str(int(number))
    blob = " ".join(
        str(item.get(key) or "") for key in ("title", "body", "url", "text")
    )
    match = _PR_NUMBER_RE.search(blob)
    return match.group(1) if match else None


def _revert_targets(title: str) -> tuple[set[str], set[str]]:
    """PR numbers and leftover title tokens a revert points at."""
    stripped = _REVERT_PREFIX_RE.sub("", title).strip(" \"'“”«»:-.")
    numbers = {match.group(1) for match in _PR_NUMBER_RE.finditer(stripped)}
    leftovers = {_norm_title(_PR_NUMBER_RE.sub(" ", stripped))}
    leftovers.discard("")
    for match in _QUOTED_RE.finditer(stripped):
        quoted = _norm_title(match.group(1))
        if quoted:
            leftovers.add(quoted)
    return numbers, leftovers


def looks_like_same_window_revert(prs: Any) -> bool:
    """True when the look window has a merge and a revert of that same change."""
    if not isinstance(prs, list):
        return False
    ships: list[dict[str, Any]] = []
    reverts: list[dict[str, Any]] = []
    for item in prs:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("text") or "").strip()
        if not title:
            continue
        if _REVERT_PREFIX_RE.match(title):
            reverts.append(item)
            continue
        if looks_like_ship_title(title):
            ships.append(item)
    if not ships or not reverts:
        return False
    ship_numbers: set[str] = set()
    ship_titles: set[str] = set()
    for item in ships:
        number = _pr_number(item)
        if number:
            ship_numbers.add(number)
        title = _norm_title(str(item.get("title") or item.get("text") or ""))
        if title:
            ship_titles.add(title)
    for item in reverts:
        blob = " ".join(
            str(item.get(key) or "") for key in ("title", "body", "text")
        )
        numbers, leftovers = _revert_targets(blob)
        if numbers & ship_numbers or leftovers & ship_titles:
            return True
    return False


def sanitize_inbound_facts(facts: list[Any]) -> list[dict[str, Any]]:
    """Keep excerpt shape. Drop an order. Empty after strip is not a fact."""
    cleaned: list[dict[str, Any]] = []
    for item in facts:
        if not isinstance(item, dict):
            continue
        text = strip_inbound_instructions(str(item.get("text") or ""))
        if not text or not _LOGIN_PREFIX_RE.sub("", text).strip():
            continue
        out = dict(item)
        out["text"] = text
        cleaned.append(out)
    return cleaned


def facts_from_survey(repo_slug: str, survey: dict[str, Any]) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    def add(*, kind: str, text: str, artifact_url: str | None = None) -> None:
        text = strip_inbound_instructions(text)
        if not text:
            return
        if artifact_url and artifact_url in seen_urls:
            return
        if artifact_url:
            seen_urls.add(artifact_url)
        facts.append({"kind": kind, "text": text, "artifact_url": artifact_url})

    for item in survey["releases"]:
        tag = str(item.get("tagName") or "").strip()
        name = str(item.get("name") or tag).strip() or tag
        add(kind="release", text=f"Released {name}", artifact_url=_release_url(repo_slug, tag))

    for item in headline_prs(survey["prs"]):
        number = item.get("number")
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        label = f"Merged PR #{number}: {title}" if number is not None else title
        add(kind="pull", text=label, artifact_url=url)

    release_tags = {str(item.get("tagName") or "") for item in survey["releases"]}
    for item in survey["tags"]:
        name = str(item.get("name") or "").strip()
        if not name or name in release_tags or looks_like_patch_only(name):
            continue
        add(kind="tag", text=f"Tag {name}")

    readme_url = readme_tryable_url(survey)
    if is_trusted_artifact_url(readme_url):
        add(
            kind="readme",
            text="README has an install/quickstart a stranger can run",
            artifact_url=readme_url,
        )

    description = str(survey["meta"].get("description") or "").strip()
    if description and len(description) >= 12:
        add(kind="signal", text=description[:240])

    return facts[:8]


def choose_brief_id(survey: dict[str, Any]) -> str:
    if survey["releases"]:
        tag = str(survey["releases"][0].get("tagName") or "release")
        return f"scan-{_slug_fragment(tag)}"[:63]
    headlines = headline_prs(survey["prs"])
    if headlines:
        number = headlines[0].get("number")
        return f"scan-pr-{_slug_fragment(str(number if number is not None else 'pr'))}"[:63]
    return "scan-story"


def pack_survey(payload: dict[str, Any]) -> dict[str, Any]:
    if payload.get("status") != "ok":
        return dict(payload)
    slug = str(payload.get("repo") or "")
    survey = payload.get("survey")
    if not isinstance(survey, dict):
        return _silence("empty_survey", repo=slug)
    if not survey.get("releases") and not headline_prs(survey.get("prs") or []):
        return _silence("commit_noise", repo=slug)
    facts = sanitize_inbound_facts(facts_from_survey(slug, survey))
    if not facts:
        return _silence("empty_survey", repo=slug)
    blob = "\n".join(str(fact.get("text") or "") for fact in facts)
    if looks_like_waitlist(blob):
        return _silence("waitlist_not_tryable", repo=slug)
    if looks_like_event(blob):
        return _silence("event_not_a_ship", repo=slug)
    if looks_like_calendar_filler(blob):
        return _silence("calendar_filler", repo=slug)
    if looks_like_counter_thanks(blob):
        return _silence("counter_thanks", repo=slug)
    if looks_like_fog(blob):
        return _silence("fog", repo=slug)
    if looks_like_founder_journal(blob):
        return _silence("founder_journal", repo=slug)
    if looks_like_lead_magnet(blob):
        return _silence("lead_magnet", repo=slug)
    meta = survey.get("meta") if isinstance(survey.get("meta"), dict) else {}
    if looks_like_solicit_gesture(
        "\n".join(
            (
                blob,
                str(survey.get("readme_text") or ""),
                str(meta.get("description") or ""),
            )
        )
    ):
        return _silence(SOLICIT_GESTURE_REASON, repo=slug)
    if looks_like_same_window_revert(survey.get("prs") or []):
        return _silence(REVERTED_NOT_A_SHIP_REASON, repo=slug)
    if facts_are_merge_log(facts) and not survey.get("releases"):
        return _silence("not_tryable", repo=slug)
    claims_ship = any(is_ship_artifact(str(fact.get("artifact_url") or "") or None) for fact in facts)
    tryable = is_tryable(survey, facts) and is_trusted_artifact_url(readme_tryable_url(survey))
    if not (claims_ship and tryable):
        return _silence("not_tryable", repo=slug)
    readme_text = str(survey.get("readme_text") or "")
    if not readme_has_visible_demo(readme_text):
        return _silence(README_WITHOUT_DEMO_REASON, repo=slug)
    if not readme_has_copyable_start(readme_text):
        return _silence(README_WITHOUT_QUICKSTART_REASON, repo=slug)
    return {
        "status": "ok",
        "ok": True,
        "repo": slug,
        "now": payload.get("now"),
        "brief_id": choose_brief_id(survey),
        "claims_ship": True,
        "tryable": True,
        "facts": facts,
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
                    "reactions": [{"kind": "github.pack", "media_type": "application/json", "value": payload}],
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
    argparse.ArgumentParser(prog="github-pack").parse_args(argv)
    raw = sys.stdin.read()
    if not raw.strip():
        return _emit(_silence("empty_survey", repo=""))
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return _emit(_silence("empty_survey", repo=""))
    if not isinstance(payload, dict):
        return _emit(_silence("empty_survey", repo=""))
    return _emit(pack_survey(payload))


if __name__ == "__main__":
    raise SystemExit(main())
