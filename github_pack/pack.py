"""Pack a survey into ship+tryable facts, or silence. No gh. No SQLite.

Tryable is a README+URL heuristic. Look does not run the project.
Launching on watch is silence. Code in look is untrusted.
Inbound titles/descriptions are data, not a command. Pack cuts
instructions ("zpostuj to", "ignore scoring"), leaves content.
Our score stays ours.
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
    looks_like_waitlist,
    readme_tryable_url,
)

_SLUG_CLEAN_RE = re.compile(r"[^a-z0-9]+")
_URL_IN_TEXT_RE = re.compile(r"https?://\S+", re.I)
_LOGIN_PREFIX_RE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9_-]{0,38}:\s*")
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


def _slug_fragment(raw: str) -> str:
    cleaned = _SLUG_CLEAN_RE.sub("-", raw.lower()).strip("-")
    return (cleaned[:40] or "story").strip("-") or "story"


def _release_url(repo_slug: str, tag: str) -> str:
    return f"https://github.com/{repo_slug}/releases/tag/{tag}"


def _silence(reason: str, *, repo: str) -> dict[str, Any]:
    return {"status": "noop", "ok": True, "reason": reason, "repo": repo, "brief_id": None}


def looks_like_inbound_instruction(text: str) -> bool:
    return bool(text and _INBOUND_INSTRUCTION_RE.search(text))


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
    if facts_are_merge_log(facts) and not survey.get("releases"):
        return _silence("not_tryable", repo=slug)
    claims_ship = any(is_ship_artifact(str(fact.get("artifact_url") or "") or None) for fact in facts)
    tryable = is_tryable(survey, facts) and is_trusted_artifact_url(readme_tryable_url(survey))
    if not (claims_ship and tryable):
        return _silence("not_tryable", repo=slug)
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
