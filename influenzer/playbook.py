"""Deterministic HoM playbook: arenas, costumes, and wave checklists.

Canon (first-person notes): https://github.com/mikolaj92/influenzer-playbook
This module is the machine-readable copy the plugin applies without freeform vibe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


CANON_URL = "https://github.com/mikolaj92/influenzer-playbook"


class StoryKind(str, Enum):
    MAJOR = "major"
    HARD_ISSUE = "hard_issue"
    EXPLORATION = "exploration"
    DECISION = "decision"
    FAILURE = "failure"
    PATCH = "patch"


class Verdict(str, Enum):
    KILL = "kill"
    CHANGELOG_ONLY = "changelog_only"
    DRAFT = "draft"


class ArenaId(str, Enum):
    X = "x"
    LINKEDIN = "linkedin"
    YOUTUBE = "youtube"
    SHORTS = "shorts"
    GITHUB = "github"
    HN = "hn"
    REDDIT = "reddit"
    NEWSLETTER = "newsletter"
    DISCORD = "discord"
    BLUESKY = "bluesky"
    MASTODON = "mastodon"


@dataclass(frozen=True)
class ArenaPlay:
    arena: ArenaId
    costume: str
    game: str
    wave: tuple[str, ...]
    canon_path: str

    @property
    def canon_url(self) -> str:
        return f"{CANON_URL}/blob/main/{self.canon_path}"


# One angle per story kind. Patches never become a social angle.
ANGLES: dict[StoryKind, str] = {
    StoryKind.MAJOR: "what shipped and why a stranger should try it",
    StoryKind.HARD_ISSUE: "I struggled with X",
    StoryKind.EXPLORATION: "what we tried and what we learned",
    StoryKind.DECISION: "what we chose and why",
    StoryKind.FAILURE: "what broke and what we learned",
    StoryKind.PATCH: "changelog only",
}


ARENAS: dict[ArenaId, ArenaPlay] = {
    ArenaId.X: ArenaPlay(
        arena=ArenaId.X,
        costume="agora",
        game="other people's rising threads, not an empty feed",
        wave=(
            "Steal heat: first replies on rising mid-KOLs; comments are inventory.",
            "Two jobs: comment earns the click; profile converts the follow.",
            "Max P(reply), then reply to replies. Quote beats Repost when small.",
            "Under 1k mostly replies; author diversity; first hour is the clock.",
            "Do not flood originals into an empty feed.",
        ),
        canon_path="x.md",
    ),
    ArenaId.LINKEDIN: ArenaPlay(
        arena=ArenaId.LINKEDIN,
        costume="court",
        game="dwell + ICP graph, not likes",
        wave=(
            "Retrieval: 3–4 pillars until the graph knows why to fetch you.",
            "Seed ICP: early 2+ line add (not echo) on people buyers already watch.",
            "Dwell: win the ~210-char fold; body must be finishable.",
            "First 60–90 min: reply with new substance (re-entry).",
            "Zero-click: insight in the post. No pitch in line one.",
        ),
        canon_path="linkedin.md",
    ),
    ArenaId.YOUTUBE: ArenaPlay(
        arena=ArenaId.YOUTUBE,
        costume="cinema",
        game="CTR × AVD, then Suggested",
        wave=(
            "Package first: title+thumb one message in 0.5s.",
            "Pay the promise in 15–30s. No logo, no hey-guys.",
            "Retention is deletion. Re-hook tutorials 60–90s, narrative 3–5 min.",
            "Suggested is a co-watch graph + session, not tags.",
            "End without announcing the end. One CTA.",
        ),
        canon_path="youtube.md",
    ),
    ArenaId.SHORTS: ArenaPlay(
        arena=ArenaId.SHORTS,
        costume="fair",
        game="swipe (hook, completion, loop), not followers",
        wave=(
            "Hook 1–3s: picture + voice + text together. No logo, no hey.",
            "Completion: each beat buys the next second.",
            "Loop: last frame into first. Rewatch is extra signal.",
            "Spine: Hook → Escalation → Payoff → CTA. Loop or one ask, not both.",
            "Do not paste the same cut on TikTok, Shorts, and Reels.",
        ),
        canon_path="shorts.md",
    ),
    ArenaId.GITHUB: ArenaPlay(
        arena=ArenaId.GITHUB,
        costume="workshop",
        game="README conversion + star velocity in a window",
        wave=(
            "Repo is the website. README one screen: one-liner → GIF → working quickstart.",
            "Broken install is a false launch. Do not buy stars.",
            "Launch is one 24–48h stack, not a week of drip.",
            "Sit on the repo during the spike (issues, Discussions).",
            "Score installs and life after the spike, not a dead star count.",
        ),
        canon_path="github.md",
    ),
    ArenaId.HN: ArenaPlay(
        arena=ArenaId.HN,
        costume="seminar",
        game="curiosity auction plus gravity; tryable thing, not a launch post",
        wave=(
            "Title starts with Show HN and a working demo. No waitlist, no blog-as-Show.",
            "URL in the URL field (text posts eat nourl-factor).",
            "First comment = backstory. Camp the thread. Human username.",
            "Never solicit upvotes (ban / domain penalty).",
            "Press-release tone dies here.",
        ),
        canon_path="hn.md",
    ),
    ArenaId.REDDIT: ArenaPlay(
        arena=ArenaId.REDDIT,
        costume="village",
        game="N rooms, each with its own constitution",
        wave=(
            "Lurk and earn karma in that sub before asking.",
            "Native self-post, receipts, repo at the bottom or first comment. Disclose.",
            "Tailor per sub; same-hour blast across programming subs is the spam signature.",
            "First-hour hot velocity. Vote rings are death.",
        ),
        canon_path="reddit.md",
    ),
    ArenaId.NEWSLETTER: ArenaPlay(
        arena=ArenaId.NEWSLETTER,
        costume="letter",
        game="owned list plus habit plus recs graph",
        wave=(
            "Named editor, one promise, cadence you can keep on a bad week.",
            "Rent-to-own: social/GitHub feed the exportable list.",
            "No user-facing change means no email.",
            "Recs: adjacent, give first. Hygiene beats vanity size.",
        ),
        canon_path="newsletter.md",
    ),
    ArenaId.DISCORD: ArenaPlay(
        arena=ArenaId.DISCORD,
        costume="tavern",
        game="co-op structure, not member count",
        wave=(
            "Intent split: help / show / contribute / lounge.",
            "Seed about 10 builders before a public invite.",
            "Celebrate merges here; decisions merge on the repo.",
            "Durable Q&A goes to Discussions, not Discord search.",
        ),
        canon_path="discord.md",
    ),
    ArenaId.BLUESKY: ArenaPlay(
        arena=ArenaId.BLUESKY,
        costume="newer cafe",
        game="curation-as-protocol; packs onboard, feeds retain",
        wave=(
            "Tight 20–50 active accounts in a niche pack plus 2–3 custom feeds.",
            "Reciprocity: put peers in the pack. Dead accounts poison.",
            "Bluesky is reach; GitHub converts. Artifact, not vibe.",
            "Pack without a feed is half the game.",
        ),
        canon_path="bluesky.md",
    ),
    ArenaId.MASTODON: ArenaPlay(
        arena=ArenaId.MASTODON,
        costume="parish",
        game="slow, no PR tone",
        wave=(
            "Speak slowly; no press-release costume.",
            "Do not paste an X punchline into the parish.",
            "Prefer a local conversation over broadcast.",
        ),
        canon_path="arenas.md",
    ),
}


def arena_play(arena: ArenaId | str) -> ArenaPlay:
    key = arena if isinstance(arena, ArenaId) else ArenaId(arena)
    return ARENAS[key]


def parse_arena(value: str | None) -> ArenaId | None:
    if value is None or value == "":
        return None
    return ArenaId(value)


# --- Fail-closed tables. First matching gate wins; silence is a correct decision. ---

# Borrowed-attention surfaces. A draft here is a social post, not the GitHub website.
SOCIAL_ARENAS: frozenset[ArenaId] = frozenset(
    {
        ArenaId.X,
        ArenaId.LINKEDIN,
        ArenaId.YOUTUBE,
        ArenaId.SHORTS,
        ArenaId.HN,
        ArenaId.REDDIT,
        ArenaId.BLUESKY,
        ArenaId.MASTODON,
    }
)

# Ship claims must point at a tryable GitHub artifact: the repo (the website),
# a PR, a release, or an issue — not a vibe, landing page, commit, or GitHub chrome.
# Repo root may have a trailing slash. Gist/wiki/compare/commit/tree/blob/actions/
# settings and user/org profile URLs are not ship artifacts.
SHIP_ARTIFACT_RE = re.compile(
    r"^https://github\.com/"
    r"(?!(?:gist|orgs|settings|users)/)"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"(?:/(?:pull/\d+|issues/\d+|releases(?:/tag/[A-Za-z0-9._~-]+|/\d+))?)?$"
)
# A film is not click-and-run. YouTube/Vimeo/Loom as the only URL is silence
# on seminar. A film next to a repo can stay as evidence. Cinema is separate.
VIDEO_HOSTS: frozenset[str] = frozenset(
    {
        "youtube.com",
        "youtu.be",
        "youtube-nocookie.com",
        "vimeo.com",
        "loom.com",
    }
)

WAITLIST_RE = re.compile(
    r"(?i)\b(?:waitlist|coming soon|join the (?:beta|waitlist)|landing page|no demo)\b"
)
PRESS_RELEASE_RE = re.compile(
    r"(?i)\b(?:excited to announce|humbled to announce|we are (?:excited|pleased|proud) to|"
    r"game[- ]changer|revolutionary|disrupt(?:ing|s)? the)\b"
)
COMMIT_NOISE_RE = re.compile(
    r"(?i)^\s*(?:chore|typo|lint|ci|wip|bump\s+(?:version|deps)|fix(?:es)?\s+tests|merge\s+branch)\b"
)
# A window of merged PRs is changelog, not a clickable product.
MERGED_PR_FACT_RE = re.compile(r"(?i)^merged\s+pr\s+#\d+")
SUBREDDIT_RE = re.compile(r"\br/[A-Za-z0-9_]+\b")
CINEMA_PACKAGE_RE = re.compile(r"(?i)\b(?:title|thumb(?:nail)?|package|poster|0\.5s)\b")
FAIR_HOOK_RE = re.compile(r"(?i)\b(?:hook|loop|1-3s|first (?:frame|second|3s))\b")

# Social drafts need more than a single thin signal unless a ship artifact is attached.
MIN_SOCIAL_FACTS = 2
MIN_FACT_CHARS = 12

HN_STORY_KINDS: frozenset[StoryKind] = frozenset({StoryKind.MAJOR, StoryKind.HARD_ISSUE})
WORKSHOP_STORY_KINDS: frozenset[StoryKind] = frozenset(
    {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE, StoryKind.DECISION}
)
NEWSLETTER_STORY_KINDS: frozenset[StoryKind] = frozenset(
    {StoryKind.MAJOR, StoryKind.DECISION, StoryKind.FAILURE}
)


@dataclass(frozen=True)
class ArenaGate:
    """Named fail-closed checks for one arena. Missing proof kills; it does not draft."""

    reason: str
    always_kill: bool = False
    require_tryable: bool = False
    require_clickable_url: bool = False
    require_ship_artifact: bool = False
    require_subreddit: bool = False
    require_package: bool = False
    require_hook: bool = False
    forbid_ship_claim: bool = False
    min_facts: int = 0
    allowed_story_kinds: frozenset[StoryKind] | None = None
    mismatch_verdict: Verdict = Verdict.KILL


ARENA_GATES: dict[ArenaId, ArenaGate] = {
    ArenaId.DISCORD: ArenaGate(reason="discord_pre_pmf", always_kill=True),
    ArenaId.HN: ArenaGate(
        reason="hn_not_tryable",
        require_tryable=True,
        require_clickable_url=True,
        allowed_story_kinds=HN_STORY_KINDS,
    ),
    ArenaId.X: ArenaGate(
        reason="x_empty_feed",
        require_tryable=True,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE}
        ),
    ),
    ArenaId.LINKEDIN: ArenaGate(
        reason="court_not_ready",
        min_facts=2,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.DECISION, StoryKind.FAILURE}
        ),
    ),
    ArenaId.YOUTUBE: ArenaGate(
        reason="cinema_missing_package",
        require_package=True,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE}
        ),
    ),
    ArenaId.SHORTS: ArenaGate(
        reason="fair_missing_hook",
        require_hook=True,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE}
        ),
    ),
    ArenaId.REDDIT: ArenaGate(
        reason="reddit_no_room",
        require_subreddit=True,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE}
        ),
    ),
    ArenaId.BLUESKY: ArenaGate(
        reason="bluesky_vibe_without_artifact",
        require_ship_artifact=True,
        allowed_story_kinds=frozenset({StoryKind.MAJOR, StoryKind.HARD_ISSUE}),
    ),
    ArenaId.MASTODON: ArenaGate(
        reason="mastodon_pr_tone",
        forbid_ship_claim=True,
        allowed_story_kinds=frozenset({StoryKind.HARD_ISSUE, StoryKind.FAILURE}),
    ),
    ArenaId.NEWSLETTER: ArenaGate(
        reason="newsletter_no_user_facing_change",
        allowed_story_kinds=NEWSLETTER_STORY_KINDS,
    ),
    ArenaId.GITHUB: ArenaGate(
        reason="workshop_not_a_story",
        allowed_story_kinds=WORKSHOP_STORY_KINDS,
        mismatch_verdict=Verdict.CHANGELOG_ONLY,
    ),
}


def is_social_arena(arena: ArenaId | str | None) -> bool:
    if arena is None:
        return False
    key = arena if isinstance(arena, ArenaId) else ArenaId(arena)
    return key in SOCIAL_ARENAS


def is_ship_artifact_url(url: str | None) -> bool:
    if not url:
        return False
    return bool(SHIP_ARTIFACT_RE.fullmatch(url.strip()))


def is_video_host_url(url: str | None) -> bool:
    """True for a YouTube/Vimeo/Loom URL. A film is not a tryable demo."""
    if not url:
        return False
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return any(host == name or host.endswith("." + name) for name in VIDEO_HOSTS)


def looks_like_commit_noise(text: str) -> bool:
    return bool(COMMIT_NOISE_RE.search(text.strip()))


def looks_like_merged_pr_fact(text: str) -> bool:
    return bool(MERGED_PR_FACT_RE.match(text.strip()))


def is_merge_log_texts(texts: tuple[str, ...] | list[str]) -> bool:
    """True when the look is a stack of 'Merged PR #N: …' (lead or all wearable)."""
    meat = [item.strip() for item in texts if item and item.strip()]
    if not meat:
        return False
    merge = [item for item in meat if looks_like_merged_pr_fact(item)]
    if not merge:
        return False
    return looks_like_merged_pr_fact(meat[0]) or len(merge) == len(meat)


def looks_like_waitlist(text: str) -> bool:
    return bool(WAITLIST_RE.search(text))


def looks_like_press_release(text: str) -> bool:
    return bool(PRESS_RELEASE_RE.search(text))


def has_named_subreddit(text: str) -> bool:
    return bool(SUBREDDIT_RE.search(text))


def has_cinema_package(text: str) -> bool:
    return bool(CINEMA_PACKAGE_RE.search(text))


def has_fair_hook(text: str) -> bool:
    return bool(FAIR_HOOK_RE.search(text))


def arena_gate(arena: ArenaId | str) -> ArenaGate:
    key = arena if isinstance(arena, ArenaId) else ArenaId(arena)
    return ARENA_GATES[key]


__all__ = [
    "ANGLES",
    "ARENA_GATES",
    "ARENAS",
    "ArenaGate",
    "ArenaId",
    "ArenaPlay",
    "CANON_URL",
    "COMMIT_NOISE_RE",
    "HN_STORY_KINDS",
    "MERGED_PR_FACT_RE",
    "MIN_FACT_CHARS",
    "MIN_SOCIAL_FACTS",
    "NEWSLETTER_STORY_KINDS",
    "SHIP_ARTIFACT_RE",
    "SOCIAL_ARENAS",
    "VIDEO_HOSTS",
    "StoryKind",
    "Verdict",
    "WORKSHOP_STORY_KINDS",
    "arena_gate",
    "arena_play",
    "has_cinema_package",
    "has_fair_hook",
    "has_named_subreddit",
    "is_merge_log_texts",
    "is_ship_artifact_url",
    "is_social_arena",
    "is_video_host_url",
    "looks_like_commit_noise",
    "looks_like_merged_pr_fact",
    "looks_like_press_release",
    "looks_like_waitlist",
    "parse_arena",
]
