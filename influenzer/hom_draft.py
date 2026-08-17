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
    HN_TITLE_LIMIT,
    HN_TITLE_PREFIX,
    LINKEDIN_FOLD,
    X_REPLY_LIMIT,
    ArenaId,
    Verdict,
    arena_play,
    agora_reason,
    has_parent_post,
    cinema_end_reason,
    court_reason,
    fair_loop_reason,
    tavern_reason,
    cafe_reason,
    letter_reason,
    reddit_reason,
    seminar_reason,
    has_cinema_package,
    has_fair_hook,
    has_fair_loop,
    has_named_subreddit,
    looks_like_fair_cta,
    is_blog_host_url,
    is_launch_host_url,
    is_merge_log_texts,
    is_news_host_url,
    is_ranking_host_url,
    is_store_host_url,
    is_social_arena,
    is_tryable_artifact_url,
    is_video_host_url,
    looks_like_hn_title_overflow,
    looks_like_linkedin_fold_overflow,
    looks_like_x_overflow,
    show_hn_title_text,
    looks_like_bot_bump_week,
    looks_like_dead_star_story,
    looks_like_monday_without_history,
    looks_like_contest,
    looks_like_poll,
    looks_like_dunk,
    looks_like_worse_clone,
    looks_like_foreign_wave,
    looks_like_reply,
    is_parent_post_url,
    PARENT_FACT_KINDS,
    looks_like_engagement_bait,
    looks_like_ranking_dump,
    looks_like_thread,
    looks_like_emoji_title,
    looks_like_hashtag_wall,
    looks_like_hire_fundraise,
    looks_like_listicle_title,
    looks_like_merged_pr_fact,
    looks_like_person_mention,
    looks_like_press_release,
    looks_like_private_conversation,
    looks_like_secret,
    looks_like_open_source_without_license,
    looks_like_source_available_as_oss,
    looks_like_world_commentary,
    looks_like_shouty_title,
    looks_like_store_pitch,
    looks_like_launch_pitch,
    looks_like_superlative,
    looks_like_dead_link,
    looks_like_dead_release_asset,
    looks_like_issues_disabled,
    looks_like_fork,
    looks_like_empty_repo,
    looks_like_private_repo,
    looks_like_archived_repo,
    looks_like_login_gate,
    looks_like_shortener,
    looks_like_utm_farm,
    looks_like_click_here,
    looks_like_server_splash,
    looks_like_roadmap,
    looks_like_pending_ci,
    looks_like_failed_ci,
    looks_like_prerelease,
    looks_like_waitlist,
    strip_open_source_claim,
    strip_person_mentions,
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


def looks_like_solicit_gesture(text: str) -> bool:
    """True for a star / upvote / follow / RT ask. Follow-the-README stays."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(_SOLICIT_GESTURE_RE.search(cleaned))



@dataclass(frozen=True)
class CopyBits:
    one_liner: str
    rest: tuple[str, ...]
    artifact_url: str | None
    clickable_url: str | None
    subreddit: str | None
    package_text: str | None
    hook_text: str | None
    loop_text: str | None
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
            is_tryable_artifact_url(url)
            and not is_ranking_host_url(url)
            and url not in found
        ):
            found.append(url)
    return tuple(found)


def _is_artifact_stub(fact: Fact) -> bool:
    """Operator proof slot, not wearable copy. URL still belongs in the proof slot."""
    return fact.kind.strip().lower() == "artifact" or fact.text.strip().casefold() == "ship artifact"


def _is_parent_fact(fact: Fact) -> bool:
    """A parent URL / reply-under slot is the thread, not the new thought."""
    kind = fact.kind.strip().lower()
    if kind in PARENT_FACT_KINDS:
        return True
    if looks_like_reply(fact.text):
        return True
    return bool(fact.artifact_url and is_parent_post_url(fact.artifact_url))


def _copy_bits(brief: Brief) -> CopyBits | None:
    texts: list[str] = []
    package_text: str | None = None
    hook_text: str | None = None
    loop_text: str | None = None
    subreddit: str | None = None
    evidence = "\n".join(
        part
        for fact in brief.facts
        for part in (fact.text, fact.artifact_url or "")
        if part
    )
    drop_oss_sticker = looks_like_open_source_without_license(evidence)
    for fact in brief.facts:
        text = fact.text.strip()
        if not text or _is_artifact_stub(fact) or _is_parent_fact(fact):
            continue
        wearable = strip_person_mentions(text)
        if drop_oss_sticker:
            wearable = strip_open_source_claim(wearable)
        if not wearable:
            continue
        kind = fact.kind.strip().lower()
        if kind == "package" or (package_text is None and has_cinema_package(wearable)):
            package_text = wearable
        if kind == "hook" or (hook_text is None and has_fair_hook(wearable)):
            hook_text = wearable
        if kind == "loop" or (loop_text is None and has_fair_loop(wearable)):
            loop_text = wearable
        found_room = _SUBREDDIT_RE.search(wearable)
        if kind == "subreddit" or (subreddit is None and found_room):
            subreddit = found_room.group(0) if found_room else wearable
        texts.append(wearable)
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
        loop_text=loop_text,
        blob=blob,
    )


def _join_rest(bits: CopyBits) -> str:
    return "\n\n".join(bits.rest)


def _proof_url(bits: CopyBits) -> str | None:
    return bits.artifact_url or bits.clickable_url


def _undressable_blob(bits: CopyBits) -> bool:
    return (
        looks_like_waitlist(bits.blob)
        or looks_like_pending_ci(bits.blob)
        or looks_like_failed_ci(bits.blob)
        or looks_like_prerelease(bits.blob)
        or looks_like_login_gate(bits.blob)
        or looks_like_shortener(bits.blob)
        or looks_like_utm_farm(bits.blob)
        or looks_like_click_here(bits.blob)
        or looks_like_solicit_gesture(bits.blob)
        or looks_like_dead_link(bits.blob)
        or looks_like_dead_release_asset(bits.blob)
        or looks_like_roadmap(bits.blob)
        or looks_like_worse_clone(bits.blob)
        or looks_like_press_release(bits.blob)
        or looks_like_world_commentary(bits.blob)
        or looks_like_hire_fundraise(bits.blob)
        or looks_like_source_available_as_oss(bits.blob)
    )


def _superlative_without_proof(brief: Brief, bits: CopyBits) -> bool:
    """A slogan without a tryable GitHub artifact is silence. Proof or nothing."""
    if not looks_like_superlative(bits.blob):
        return False
    return not (brief.tryable and any(is_ship_artifact(url) for url in brief_artifacts(brief)))


def _merge_log_bits(bits: CopyBits) -> bool:
    return is_merge_log_texts((bits.one_liner, *bits.rest))


def _bot_bump_week_bits(bits: CopyBits) -> bool:
    return looks_like_bot_bump_week((bits.one_liner, *bits.rest))


def _dead_star_story_bits(bits: CopyBits) -> bool:
    return looks_like_dead_star_story((bits.one_liner, *bits.rest))


def _body_or_none(body: str) -> str | None:
    text = strip_person_mentions(body)
    if not text:
        return None
    if any(marker in text for marker in _FORBIDDEN_IN_BODY):
        return None
    if looks_like_person_mention(text):
        return None
    return text


def _dress_github(bits: CopyBits, score: Score) -> str | None:
    """Workshop: README one-liner → what it is → working quickstart URL."""
    if not bits.one_liner or looks_like_shouty_title(bits.one_liner) or looks_like_emoji_title(bits.one_liner):
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


def _show_hn_title(one_liner: str) -> str | None:
    """One line, not a blog. Overflow is silence, not a mid-word clip."""
    if looks_like_hn_title_overflow(one_liner):
        return None
    title = show_hn_title_text(one_liner)
    if not title:
        return None
    dressed = f"{HN_TITLE_PREFIX}{title}"
    if len(dressed) > HN_TITLE_LIMIT or "\n" in dressed:
        return None
    return dressed


def _dress_hn(bits: CopyBits, score: Score) -> str | None:
    """Seminar: Show HN title + tryable URL + first-comment backstory."""
    if seminar_reason(bits.blob):
        return None
    title_src = bits.one_liner.strip()
    if title_src.lower().startswith("show hn:"):
        title_src = title_src.split(":", 1)[1].strip()
    if looks_like_merged_pr_fact(title_src) or _merge_log_bits(bits) or _bot_bump_week_bits(bits):
        return None
    if looks_like_listicle_title(title_src) or looks_like_shouty_title(title_src) or looks_like_emoji_title(title_src):
        return None
    if looks_like_hn_title_overflow(bits.one_liner):
        return None
    url = _proof_url(bits)
    if (
        not url
        or not is_tryable_artifact_url(url)
        or is_video_host_url(url)
        or is_store_host_url(url)
        or is_blog_host_url(url)
        or is_launch_host_url(url)
        or is_ranking_host_url(url)
        or is_news_host_url(url)
    ):
        return None
    if looks_like_store_pitch("\n".join((bits.one_liner, *bits.rest))):
        return None
    if looks_like_launch_pitch("\n".join((bits.one_liner, *bits.rest))):
        return None
    title = _show_hn_title(bits.one_liner)
    if title is None:
        return None
    parts = [title, url]
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
    if looks_like_x_overflow(hook, url):
        return None
    cleaned = " ".join(hook.split())
    if url:
        body = f"{cleaned}\n{url}"
        if len(body) > X_REPLY_LIMIT:
            return None
        return _body_or_none(body)
    if len(cleaned) > X_REPLY_LIMIT:
        return None
    return _body_or_none(cleaned)


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
    if looks_like_linkedin_fold_overflow(insight):
        return None
    fold = " ".join(insight.split())
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
    if cinema_end_reason(bits.blob) or fair_loop_reason(bits.blob) == "fair_cta_with_loop":
        return None
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
    """Fair: hook, then the loop beat. Missing loop or CTA+loop is silence."""
    if fair_loop_reason(bits.blob):
        return None
    hook = bits.hook_text or bits.one_liner
    if not hook:
        return None
    loop = bits.loop_text if bits.loop_text and bits.loop_text != hook else ""
    pay = next(
        (text for text in (bits.one_liner, *bits.rest) if text not in {hook, loop}),
        "",
    )
    parts = [_clip(hook, 120)]
    if loop:
        parts.extend(["", _clip(loop, 160)])
    elif pay:
        parts.extend(["", _clip(pay, 160)])
    body = _body_or_none("\n".join(parts))
    if body is None or looks_like_fair_cta(body):
        return None
    return body


def _dress_reddit(bits: CopyBits, score: Score) -> str | None:
    """Village: native self-post, disclose it's ours, repo at the bottom."""
    if reddit_reason(bits.blob):
        return None
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
    """Letter: named-editor cadence; give first, then maybe ask."""
    if letter_reason(bits.blob):
        return None
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
    """Newer cafe: pack onboarduje, feed trzyma. Artifact alone is half the game."""
    if cafe_reason(bits.blob):
        return None
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
    """Tavern: public invite only with intent split and ~10 builders."""
    if tavern_reason(bits.blob):
        return None
    if not bits.one_liner:
        return None
    parts = [bits.one_liner]
    rest = _join_rest(bits)
    if rest:
        parts.extend(["", rest])
    return _body_or_none("\n".join(parts))


def _overflows_arena(arena: ArenaId, bits: CopyBits, body: str) -> bool:
    """Hard arena limits. Overflow is silence, not a mid-word clip."""
    if arena is ArenaId.X:
        return len(body) > X_REPLY_LIMIT or looks_like_x_overflow(bits.one_liner, _proof_url(bits))
    if arena is ArenaId.HN:
        title = body.splitlines()[0] if body.strip() else ""
        return looks_like_hn_title_overflow(title) or "\n" in title
    if arena is ArenaId.LINKEDIN:
        fold = body.split("\n\n", 1)[0]
        return looks_like_linkedin_fold_overflow(fold) or len(fold) > LINKEDIN_FOLD
    return False


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
    bits = _copy_bits(brief)
    triples = tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)
    if (
        bits is None
        or _undressable_blob(bits)
        or _superlative_without_proof(brief, bits)
        or looks_like_dunk(bits.blob)
        or looks_like_worse_clone(bits.blob)
        or looks_like_foreign_wave(triples)
        or looks_like_engagement_bait(bits.blob)
        or looks_like_solicit_gesture(bits.blob)
        or looks_like_contest(bits.blob)
        or looks_like_poll(bits.blob)
        or looks_like_thread(bits.blob)
        or looks_like_ranking_dump(bits.blob)
        or looks_like_hashtag_wall(bits.blob)
        or looks_like_private_conversation(bits.blob)
        or looks_like_secret(bits.blob)
        or looks_like_world_commentary(bits.blob)
        or looks_like_hire_fundraise(bits.blob)
        or looks_like_source_available_as_oss(bits.blob)
        or (is_social_arena(score.arena) and looks_like_issues_disabled(bits.blob))
        or looks_like_fork(bits.blob)
        or looks_like_empty_repo(bits.blob)
        or looks_like_private_repo(bits.blob)
        or looks_like_archived_repo(bits.blob)
        or looks_like_server_splash(bits.blob)
        or looks_like_bot_bump_week(
            tuple(fact.text for fact in brief.facts),
            kinds=tuple(fact.kind for fact in brief.facts),
        )
        or _bot_bump_week_bits(bits)
        or looks_like_dead_star_story(
            tuple(fact.text for fact in brief.facts),
            kinds=tuple(fact.kind for fact in brief.facts),
        )
        or _dead_star_story_bits(bits)
        or looks_like_monday_without_history(
            story_kind=brief.story_kind,
            preferred_arena=score.arena or brief.preferred_arena,
            tryable=brief.tryable,
            artifact_urls=brief_artifacts(brief),
            facts=triples,
            blob=bits.blob,
        )
        or (
            score.arena is ArenaId.LINKEDIN
            and court_reason(bits.blob, claims_ship=brief.claims_ship)
        )
        or (score.arena is ArenaId.DISCORD and tavern_reason(bits.blob))
        or (score.arena is ArenaId.X and not has_parent_post(triples))
        or (score.arena is ArenaId.X and agora_reason(triples))
        or (score.arena is ArenaId.BLUESKY and cafe_reason(bits.blob))
        or (score.arena is ArenaId.NEWSLETTER and letter_reason(bits.blob))
        or (score.arena is ArenaId.REDDIT and reddit_reason(bits.blob))
        or (score.arena is ArenaId.HN and seminar_reason(bits.blob))
        or (score.arena is ArenaId.YOUTUBE and cinema_end_reason(bits.blob))
    ):
        return None
    if unquotable_reason(triples):
        return None
    dresser = _DRESSERS.get(score.arena)
    if dresser is None:
        return None
    body = dresser(bits, score)
    if body is not None and _overflows_arena(score.arena, bits, body):
        return None
    if (
        body is None
        or unquotable_reason(triples, extra=body)
        or looks_like_dunk(body)
        or looks_like_worse_clone(body)
        or looks_like_foreign_wave((*triples, ("signal", body, None)))
        or looks_like_engagement_bait(body)
        or looks_like_solicit_gesture(body)
        or looks_like_contest(body)
        or looks_like_poll(body)
        or looks_like_thread(body)
        or looks_like_ranking_dump(body)
        or looks_like_hashtag_wall(body)
        or looks_like_person_mention(body)
        or looks_like_private_conversation(body)
        or looks_like_secret(body)
        or looks_like_world_commentary(body)
        or looks_like_hire_fundraise(body)
        or looks_like_source_available_as_oss(body)
        or (is_social_arena(score.arena) and looks_like_issues_disabled(body))
        or looks_like_fork(body)
        or looks_like_empty_repo(body)
        or looks_like_private_repo(body)
        or looks_like_archived_repo(body)
        or looks_like_server_splash(body)
        or (
            score.arena is ArenaId.LINKEDIN
            and court_reason(body, claims_ship=brief.claims_ship)
        )
        or (score.arena is ArenaId.DISCORD and tavern_reason(body))
        or (score.arena is ArenaId.X and agora_reason(triples, extra=body))
        or (score.arena is ArenaId.NEWSLETTER and letter_reason(body))
        or (score.arena is ArenaId.REDDIT and reddit_reason(body))
        or (score.arena is ArenaId.HN and seminar_reason(body))
        or (score.arena is ArenaId.YOUTUBE and cinema_end_reason(body))
    ):
        return None
    if looks_like_open_source_without_license(body):
        body = strip_open_source_claim(body)
        if not body:
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
