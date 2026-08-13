"""Deterministic HoM playbook: arenas, costumes, and wave checklists.

Canon (first-person notes): https://github.com/mikolaj92/influenzer-playbook
This module is the machine-readable copy the plugin applies without freeform vibe.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


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


__all__ = [
    "ANGLES",
    "ARENAS",
    "ArenaId",
    "ArenaPlay",
    "CANON_URL",
    "StoryKind",
    "Verdict",
    "arena_play",
    "parse_arena",
]
