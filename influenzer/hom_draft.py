"""Costume-native draft body from a scored brief, or silence.

One job: dress a Brief + a Score that already chose one arena and one
angle. Kill and changelog-only emit nothing. If the brief cannot be
worn as that costume, emit nothing rather than a label dump.

Does not survey GitHub. Does not call gh. Does not write state.db.
Does not pick the arena. Does not score. Does not publish.
Does not enable live social. Does not know Heimdall.
Does not open runtime.db. Does not embed a Fala host.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from typing import Any, Mapping

from influenzer.domain import utc_now
from influenzer.hom import (
    Brief,
    Draft,
    Fact,
    HomError,
    Score,
    brief_artifacts,
    brief_from_mapping,
    is_ship_artifact,
)
from influenzer.playbook import (
    ARENAS,
    CANON_URL,
    ArenaId,
    Verdict,
    arena_play,
    has_cinema_package,
    has_fair_hook,
    has_named_subreddit,
    is_blog_host_url,
    is_merge_log_texts,
    is_store_host_url,
    is_video_host_url,
    looks_like_listicle_title,
    looks_like_merged_pr_fact,
    looks_like_press_release,
    looks_like_store_pitch,
    looks_like_waitlist,
    unquotable_reason,
)

# Bodies must look like the arena, not operator metadata.
_FORBIDDEN_IN_BODY = (
    "Costume:",
    "One arena:",
    "One angle:",
    "Wave checklist:",
)

_PITCH_LINE_RE = re.compile(
    r"^\s*(?:(?:we|i)\s+)?(?:just\s+)?(?:shipped|launched|announcing|introducing)\b|"
    r"^\s*(?:excited to|proud to|please to|try (?:it|this|ours?)\b|sign up|click here)",
    re.I,
)
_URL_IN_TEXT_RE = re.compile(r"https?://", re.I)
_SUBREDDIT_RE = re.compile(r"\br/[A-Za-z0-9_]+\b")

LINKEDIN_FOLD = 210
X_REPLY_LIMIT = 280
HN_TITLE_LIMIT = 72


@dataclass(frozen=True)
class CopyBits:
    one_liner: str
    rest: tuple[str, ...]
    artifact_url: str | None
    clickable_url: str | None
    subreddit: str | None
    package_text: str | None
    hook_text: str | None
    blob: str


def _silence(reason: str) -> dict[str, Any]:
    return {
        "status": "noop",
        "ok": True,
        "reason": reason,
        "draft_id": None,
        "body": None,
        "published": False,
    }


def _clip(text: str, limit: int) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned.rstrip(".,;:")
    clipped = cleaned[:limit].rsplit(" ", 1)[0].rstrip(".,;:")
    return clipped or cleaned[:limit]


def _clickable_urls(brief: Brief) -> tuple[str, ...]:
    found: list[str] = []
    for fact in brief.facts:
        url = (fact.artifact_url or "").strip()
        if not url:
            continue
        if is_ship_artifact(url):
            if url not in found:
                found.append(url)
            continue
        if (
            url.startswith("https://")
            and not is_video_host_url(url)
            and not is_store_host_url(url)
            and not is_blog_host_url(url)
            and url not in found
        ):
            found.append(url)
    return tuple(found)


def _is_artifact_stub(fact: Fact) -> bool:
    """Operator proof slot, not wearable copy. URL still belongs in the proof slot."""
    return fact.kind.strip().lower() == "artifact" or fact.text.strip().casefold() == "ship artifact"


def _copy_bits(brief: Brief) -> CopyBits | None:
    texts: list[str] = []
    package_text: str | None = None
    hook_text: str | None = None
    subreddit: str | None = None
    for fact in brief.facts:
        text = fact.text.strip()
        if not text or _is_artifact_stub(fact):
            continue
        kind = fact.kind.strip().lower()
        if kind == "package" or (package_text is None and has_cinema_package(text)):
            package_text = text
        if kind == "hook" or (hook_text is None and has_fair_hook(text)):
            hook_text = text
        found_room = _SUBREDDIT_RE.search(text)
        if kind == "subreddit" or (subreddit is None and found_room):
            subreddit = found_room.group(0) if found_room else text
        texts.append(text)
    if not texts:
        return None
    one_liner = texts[0]
    rest = tuple(item for item in texts[1:] if item != one_liner)
    ship = next((url for url in brief_artifacts(brief) if is_ship_artifact(url)), None)
    clickable = ship or (next(iter(_clickable_urls(brief)), None))
    blob = "\n".join(
        part
        for fact in brief.facts
        for part in (fact.text, fact.kind, fact.artifact_url or "")
        if part
    )
    return CopyBits(
        one_liner=one_liner,
        rest=rest,
        artifact_url=ship,
        clickable_url=clickable,
        subreddit=subreddit,
        package_text=package_text,
        hook_text=hook_text,
        blob=blob,
    )


def _join_rest(bits: CopyBits) -> str:
    return "\n\n".join(bits.rest)


def _proof_url(bits: CopyBits) -> str | None:
    return bits.artifact_url or bits.clickable_url


def _undressable_blob(bits: CopyBits) -> bool:
    return looks_like_waitlist(bits.blob) or looks_like_press_release(bits.blob)


def _merge_log_bits(bits: CopyBits) -> bool:
    return is_merge_log_texts((bits.one_liner, *bits.rest))


def _body_or_none(body: str) -> str | None:
    text = body.strip()
    if not text:
        return None
    if any(marker in text for marker in _FORBIDDEN_IN_BODY):
        return None
    return text


def _dress_github(bits: CopyBits, score: Score) -> str | None:
    """Workshop: README one-liner → what it is → working quickstart URL."""
    if not bits.one_liner:
        return None
    lines = [bits.one_liner.rstrip("."), ""]
    what = _join_rest(bits)
    if what:
        lines.append(what)
        lines.append("")
    url = _proof_url(bits)
    if url:
        lines.append("## Quickstart")
        lines.append("")
        lines.append(url)
    return _body_or_none("\n".join(lines))


def _show_hn_title(one_liner: str) -> str:
    text = one_liner.strip()
    lowered = text.lower()
    if lowered.startswith("show hn:"):
        text = text.split(":", 1)[1].strip()
    return f"Show HN: {_clip(text, HN_TITLE_LIMIT)}"


def _dress_hn(bits: CopyBits, score: Score) -> str | None:
    """Seminar: Show HN title + tryable URL + first-comment backstory."""
    title_src = bits.one_liner.strip()
    if title_src.lower().startswith("show hn:"):
        title_src = title_src.split(":", 1)[1].strip()
    if looks_like_merged_pr_fact(title_src) or _merge_log_bits(bits):
        return None
    if looks_like_listicle_title(title_src):
        return None
    url = _proof_url(bits)
    if not url or is_video_host_url(url) or is_store_host_url(url) or is_blog_host_url(url):
        return None
    if looks_like_store_pitch("\n".join((bits.one_liner, *bits.rest))):
        return None
    parts = [_show_hn_title(bits.one_liner), url]
    backstory = _join_rest(bits)
    if backstory:
        parts.append(backstory)
    return _body_or_none("\n\n".join(parts))


def _dress_x(bits: CopyBits, score: Score) -> str | None:
    """Agora: short reply-shaped hook, not a thread dump or empty-feed essay."""
    hook = bits.one_liner
    if not hook:
        return None
    url = _proof_url(bits)
    if url:
        budget = max(24, X_REPLY_LIMIT - len(url) - 1)
        hook = _clip(hook, budget)
        return _body_or_none(f"{hook}\n{url}")
    return _body_or_none(_clip(hook, X_REPLY_LIMIT))


def _court_insight(bits: CopyBits) -> str | None:
    candidates = (bits.one_liner, *bits.rest)
    for text in candidates:
        if _URL_IN_TEXT_RE.search(text):
            continue
        if _PITCH_LINE_RE.search(text):
            continue
        if text.strip():
            return text.strip()
    return None


def _dress_linkedin(bits: CopyBits, score: Score) -> str | None:
    """Court: win the ~210-char fold; insight first; no pitch in line one."""
    insight = _court_insight(bits)
    if insight is None:
        return None
    fold = insight if len(insight) <= LINKEDIN_FOLD else _clip(insight, LINKEDIN_FOLD)
    leftover = [text for text in (bits.one_liner, *bits.rest) if text.strip() != insight]
    parts = [fold]
    rest = "\n\n".join(leftover)
    if rest:
        parts.extend(["", rest])
    url = _proof_url(bits)
    if url:
        parts.extend(["", url])
    body = _body_or_none("\n".join(parts))
    if body is None:
        return None
    first = body.split("\n\n", 1)[0]
    if len(first) > LINKEDIN_FOLD or _PITCH_LINE_RE.search(first) or _URL_IN_TEXT_RE.search(first):
        return None
    return body


def _dress_youtube(bits: CopyBits, score: Score) -> str | None:
    """Cinema: package (title/thumb) first, then pay the promise."""
    if not bits.package_text:
        return None
    pay = next((text for text in (bits.one_liner, *bits.rest) if text != bits.package_text), "")
    parts = [bits.package_text]
    if pay:
        parts.extend(["", pay])
    url = _proof_url(bits)
    if url:
        parts.extend(["", url])
    return _body_or_none("\n".join(parts))


def _dress_shorts(bits: CopyBits, score: Score) -> str | None:
    """Fair: hook in the first line, then one beat. Not an essay."""
    hook = bits.hook_text or bits.one_liner
    if not hook:
        return None
    pay = next((text for text in (bits.one_liner, *bits.rest) if text != hook), "")
    parts = [_clip(hook, 120)]
    if pay:
        parts.extend(["", _clip(pay, 160)])
    return _body_or_none("\n".join(parts))


def _dress_reddit(bits: CopyBits, score: Score) -> str | None:
    """Village: native self-post for one named room; receipts at the bottom."""
    if not bits.subreddit or not has_named_subreddit(bits.subreddit):
        return None
    parts = [bits.one_liner]
    rest = _join_rest(bits)
    if rest:
        parts.extend(["", rest])
    url = _proof_url(bits)
    if url:
        parts.extend(["", url])
    parts.extend(["", bits.subreddit])
    return _body_or_none("\n".join(parts))


def _dress_newsletter(bits: CopyBits, score: Score) -> str | None:
    """Letter: named-editor cadence; user-facing change, not a blast."""
    if not bits.one_liner:
        return None
    parts = [bits.one_liner]
    rest = _join_rest(bits)
    if rest:
        parts.extend(["", rest])
    url = _proof_url(bits)
    if url:
        parts.extend(["", url])
    return _body_or_none("\n".join(parts))


def _dress_bluesky(bits: CopyBits, score: Score) -> str | None:
    """Newer cafe: artifact, not vibe."""
    url = bits.artifact_url
    if not url:
        return None
    return _body_or_none(f"{_clip(bits.one_liner, 200)}\n\n{url}")


def _dress_mastodon(bits: CopyBits, score: Score) -> str | None:
    """Parish: slow, no PR tone, not an X punchline paste."""
    if not bits.one_liner:
        return None
    parts = [bits.one_liner]
    rest = _join_rest(bits)
    if rest:
        parts.extend(["", rest])
    return _body_or_none("\n".join(parts))


def _dress_discord(bits: CopyBits, score: Score) -> str | None:
    """Tavern is not a launch costume. Fail closed."""
    return None


_DRESSERS = {
    ArenaId.GITHUB: _dress_github,
    ArenaId.HN: _dress_hn,
    ArenaId.X: _dress_x,
    ArenaId.LINKEDIN: _dress_linkedin,
    ArenaId.YOUTUBE: _dress_youtube,
    ArenaId.SHORTS: _dress_shorts,
    ArenaId.REDDIT: _dress_reddit,
    ArenaId.NEWSLETTER: _dress_newsletter,
    ArenaId.BLUESKY: _dress_bluesky,
    ArenaId.MASTODON: _dress_mastodon,
    ArenaId.DISCORD: _dress_discord,
}

assert set(_DRESSERS) == set(ARENAS)


def dress_brief(brief: Brief, score: Score, *, now: str | None = None) -> Draft | None:
    """Wear the chosen costume. Kill/changelog/undressable → None."""
    if score.verdict is not Verdict.DRAFT or score.arena is None or score.angle is None:
        return None
    if score.arena is ArenaId.DISCORD:
        return None
    bits = _copy_bits(brief)
    if bits is None or _undressable_blob(bits):
        return None
    triples = tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)
    if unquotable_reason(triples):
        return None
    dresser = _DRESSERS.get(score.arena)
    if dresser is None:
        return None
    body = dresser(bits, score)
    if body is None or unquotable_reason(triples, extra=body):
        return None
    play = arena_play(score.arena)
    clock = now or utc_now()
    return Draft(
        project_id=brief.project_id,
        brief_id=brief.brief_id,
        draft_id=f"draft-{brief.brief_id}",
        arena=score.arena,
        costume=play.costume,
        angle=score.angle,
        body=body,
        wave_checklist=play.wave,
        canon_url=play.canon_url,
        created_at=clock,
    ).with_hash()


def score_from_mapping(data: Mapping[str, Any]) -> Score:
    verdict = Verdict(str(data.get("verdict") or ""))
    arena_raw = data.get("arena")
    arena: ArenaId | None
    if arena_raw in (None, ""):
        arena = None
    else:
        arena = ArenaId(str(arena_raw))
    angle_raw = data.get("angle")
    angle = None if angle_raw in (None, "") else str(angle_raw)
    wave_raw = data.get("wave_checklist") or ()
    if isinstance(wave_raw, list):
        wave = tuple(str(item) for item in wave_raw)
    else:
        wave = tuple(str(item) for item in wave_raw) if isinstance(wave_raw, tuple) else ()
    return Score(
        brief_id=str(data.get("brief_id") or ""),
        verdict=verdict,
        reason=str(data.get("reason") or ""),
        arena=arena,
        angle=angle,
        wave_checklist=wave,
        canon_url=str(data.get("canon_url") or CANON_URL),
        score_hash=str(data.get("score_hash") or ""),
    )


def dress_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """JSON in, draft JSON or silence out. No SQLite. No scoring."""
    score_raw = payload.get("score")
    brief_raw = payload.get("brief")
    if not isinstance(score_raw, Mapping) or not isinstance(brief_raw, Mapping):
        return _silence("undressable")
    try:
        brief = brief_from_mapping(brief_raw)
        score = score_from_mapping(score_raw)
    except (HomError, ValueError, TypeError, KeyError):
        return _silence("undressable")
    now = payload.get("now")
    clock = now if isinstance(now, str) else None
    draft = dress_brief(brief, score, now=clock)
    if draft is None:
        if score.verdict is Verdict.KILL:
            reason = "kill"
        elif score.verdict is Verdict.CHANGELOG_ONLY:
            reason = "changelog_only"
        else:
            reason = "undressable"
        return _silence(reason)
    return {
        "status": "ok",
        "ok": True,
        "reason": None,
        "draft_id": draft.draft_id,
        "arena": draft.arena.value,
        "costume": draft.costume,
        "angle": draft.angle,
        "body": draft.body,
        "wave_checklist": list(draft.wave_checklist),
        "canon_url": draft.canon_url,
        "content_hash": draft.content_hash,
        "published": False,
    }


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(prog="hom-draft").parse_args(argv)
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    out = dress_payload(payload)
    print(json.dumps(out, sort_keys=True))
    from influenzer.fala_result import write_fala_result

    write_fala_result(out, reaction_kind="hom.draft")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "dress_brief",
    "dress_payload",
    "main",
    "score_from_mapping",
]
