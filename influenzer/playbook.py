"""Deterministic HoM playbook: arenas, costumes, and wave checklists.

Canon (first-person notes): https://github.com/mikolaj92/influenzer-playbook
This module is the machine-readable copy the plugin applies without freeform vibe.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from urllib.parse import parse_qs, urlparse


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
            "Do not flood originals into an empty feed. Not a hashtag catalog. Over 280 is silence, not a mid-word clip.",
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
            "Dwell: win the ~210-char fold; body must be finishable. Overflow is silence, not a mid-word clip.",
            "First 60–90 min: reply with new substance (re-entry).",
            "Zero-click: insight in the post. No pitch in line one, no hashtag wall. Language from the profile (audience). A foreign-language court is silence.",
            "Court is not a launch channel. claims_ship / Show HN energy is github/hn. Insight from the work (pillars), or silence. Also outside the launch window.",
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
            "Repo is the website. README one screen: one-liner → GIF → working quickstart. English only. No shouty CAPS title, no emoji. A Polish one-liner is silence. A fork is not a website. An empty repo or a repo without a README is not a website. A private repo is not a website. Workshop is a public README. An archived or disabled repo is dead. Do not launch a museum. Watch only on our repo. Owner must be the same GitHub as the maintainer. A foreign owner is silence, not a ship. Helping them is cisza here or contribute, not our launch. A default nginx / Apache / Caddy page is not a product. A week of only dependabot / renovate / github-actions bumps is not a story. A Monday without a ship or real public feedback is silence, not a recap. Weekly update without history stays in the changelog. Pending or yellow CI is not a ship. Red or failed CI on the default branch is a false launch. Press-release tone is changelog, not a workshop launch.",
            "Broken install is a false launch. Do not buy stars.",
            "Launch is one 24–48h stack, not a week of drip. Angle from the canonical source, not a copy.",
            "Sit on the repo during the spike (issues, Discussions). Issues disabled is not a camp.",
            "Score installs and life after the spike, not a dead star count.",
        ),
        canon_path="github.md",
    ),
    ArenaId.HN: ArenaPlay(
        arena=ArenaId.HN,
        costume="seminar",
        game="curiosity auction plus gravity; tryable thing, not a launch post",
        wave=(
            "Title starts with Show HN and a working demo. One line, not a blog. Overflow is silence, not a mid-word clip. English only. A Polish Show HN is silence. A lab notebook is not Show HN: exploration / decision / failure do not sit, even with a demo — workshop or silence. Seminar only when a stranger can click and run a major or hard-issue ship. No waitlist, no FOMO, no only-N-spots, no countdown, no last chance, no meme, no Drake, no wojak, no reaction image, no deck, no pitch deck, no PDF slides, no Notion one-pager, no linktree, no Carrd, no bio site, no list of links, no roadmap, no webinar, no meetup, no calendar, no rebrand, no logo reveal, no moodboard, no palette, no draft release, no prerelease, no RC, no beta, no pending CI, no yellow CI, no red CI, no failed CI, no login wall, no listed 404 asset, no dead link, no dead TLS, no cert error, no mixed content, no server splash, no off-allowlist redirect, no blog-as-Show, no store-as-Show, no aggregator-as-Show, no ranking dump, no listicle, no shouty CAPS, no emoji, no issues-disabled repo, no fork, no empty repo, no missing README, no private repo, no archived repo, no disabled repo, no museum launch, no foreign-owner repo, no someone else's ship, no template repo, no generate-from-template without a ship, no boilerplate Show HN, no bot-only bump week, no version-diff launch.",
            "URL in the URL field (text posts eat nourl-factor).",
            "First comment = backstory from BrandProfile.maintainer, first person. Camp the thread. A second Show is silence. Human username. Brand voice is silence.",
            "Never solicit upvotes (ban / domain penalty).",
            "Press-release tone dies here. We at Product announced is silence.",
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
            "Named editor from BrandProfile (display_name / maintainer), first and last name. we / the team is silence. A given name without a surname is silence. Language from the profile (audience). A foreign-language letter is silence.",
            "Rent-to-own: social/GitHub feed the exportable list.",
            "Letter only on ship+tryable (a stranger can click and run it). Patch, typo, internal, feedback-only: silence on the list; changelog may go to GitHub. Weekly update without a ship or real public feedback is silence, not a recap.",
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
            "Empty tavern is silence. Public invite only with the split and ~10 builders.",
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


# Launch stack: one 24–48h github/hn costume. Pair of #61 (primary) and #26 (window).
# One wearable github/hn angle in that window. Next scan/score is changelog or
# silence — not a second social angle, even after verdict pass. Hold or a dead
# window can change it. Shopping is silence. #63: format stays because we do
# not emit a second costume. #61: we sit on github (feedback) and hn (camp).
# X/shorts without a listener are not a first costume. Preferred YT sits so
# a cut without title+promise is silence — not a Show HN. Discord/bsky sit.
# Ship goes where we sit. #50: after Show HN, sit in the thread. Score does
# not pick HN again.
STACK_HOURS = 48
STACK_ARENAS: frozenset[ArenaId] = frozenset({ArenaId.GITHUB, ArenaId.HN})
PRIMARY_ARENAS: frozenset[ArenaId] = STACK_ARENAS
LIVING_STACK_REASON = "living_stack"
HN_CAMP_REASON = "hn_camp"


def is_stack_arena(arena: ArenaId | str | None) -> bool:
    """True for the github/hn launch pair. Other arenas are not this stack."""
    if arena is None or arena == "":
        return False
    try:
        key = arena if isinstance(arena, ArenaId) else ArenaId(arena)
    except ValueError:
        return False
    return key in STACK_ARENAS


def is_primary_arena(arena: ArenaId | str | None) -> bool:
    """True when we sit there with a listener. Today that is github/hn."""
    return is_stack_arena(arena)


def parse_stack_arena(value: ArenaId | str | None) -> ArenaId | None:
    if not is_stack_arena(value):
        return None
    return value if isinstance(value, ArenaId) else ArenaId(str(value))


def parse_stack_clock(value: datetime | str | None) -> datetime | None:
    """Aware UTC clock. Naive or malformed is unreadable, not a second costume."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def living_stack_arena(
    entries: Iterable[tuple[ArenaId | str | None, str | None]] | None,
    now: datetime | str | None,
) -> ArenaId | None:
    """Costume of the open github/hn stack while its 48h window lives.

    The window starts at the oldest unheld github/hn draft. Later looks in
    that stack do not refresh it — one launch, not a week of drip. Hold is
    the caller's filter. An unreadable clock keeps the stack alive. At
    exactly 48h the window is dead. A set-back clock is still living.
    """
    if not entries:
        return None
    found: list[tuple[datetime | None, ArenaId]] = []
    for arena, created_at in entries:
        locked = parse_stack_arena(arena)
        if locked is None:
            continue
        found.append((parse_stack_clock(created_at), locked))
    if not found:
        return None
    moment = parse_stack_clock(now)
    readable = [(created, locked) for created, locked in found if created is not None]
    # Unreadable now or created_at cannot prove the window is dead.
    if moment is None or not readable or any(created is None for created, _ in found):
        if readable:
            readable.sort(key=lambda item: item[0])
            return readable[0][1]
        return found[0][1]
    readable.sort(key=lambda item: item[0])
    start, locked = readable[0]
    if moment < start or moment - start < timedelta(hours=STACK_HOURS):
        return locked
    return None


def hn_camp_reason(stack_arena: ArenaId | str | None) -> str | None:
    """After Show HN, sit in the thread. A second Show is silence."""
    if parse_stack_arena(stack_arena) is ArenaId.HN:
        return HN_CAMP_REASON
    return None


def is_hn_camp_arena(arena: ArenaId | str | None) -> bool:
    """True when this costume is the open Show HN. Camp, do not Show again."""
    return parse_stack_arena(arena) is ArenaId.HN


def stack_costume_reason(
    preferred_arena: ArenaId | str | None,
    stack_arena: ArenaId | str | None,
) -> str | None:
    """Explicit other arena while the stack lives is silence, not a new costume."""
    locked = parse_stack_arena(stack_arena)
    if locked is None or preferred_arena is None or preferred_arena == "":
        return None
    try:
        wanted = (
            preferred_arena
            if isinstance(preferred_arena, ArenaId)
            else ArenaId(preferred_arena)
        )
    except ValueError:
        return LIVING_STACK_REASON
    if wanted is not locked:
        return LIVING_STACK_REASON
    return None


def choose_arena(
    *,
    preferred_arena: ArenaId | str | None = None,
    stack_arena: ArenaId | str | None = None,
    tryable: bool = False,
    claims_ship: bool = False,
    story_kind: StoryKind | str | None = None,
    clickable: bool = False,
    issues_disabled: bool = False,
    fork: bool = False,
    empty_repo: bool = False,
    private_repo: bool = False,
    archived_repo: bool = False,
    server_splash: bool = False,
    parent_post: bool = False,
) -> ArenaId:
    """One primary arena. A living github/hn stack keeps that costume.

    Score/scan do not emit a second social angle while the window lives —
    this only names the locked costume. Changelog or silence is the caller.

    We sit on github (feedback) and hn (camp). Preferred shorts without
    a listener is not a first costume — ship goes where we sit. Preferred
    YouTube sits so a cut without a title+promise pair (one message in
    0.5s) is silence — not a Show HN, not hey-guys, not a logo intro.
    Court is insight from the work, never a launch channel:
    preferred LinkedIn sits only when the brief does not claim ship.
    Preferred Discord sits so an empty tavern can be silence — public
    invite only with intent split and ~10 builders. A decision does not
    sit here: workshop on GitHub, never the tavern. Preferred Bluesky
    sits so an artifact-only cafe can be silence — pack onboarduje,
    feed trzyma. Preferred Reddit sits so a named room without
    disclosure or a repo at the bottom can be silence — native
    self-post, say it's ours. Preferred newsletter sits so subscribe /
    our launch without a gift, or a letter without a surname, can be
    silence — give first, sign First Last from the profile, recs are
    adjacent.
    Preferred X sits only on a parent-post URL (reply, borrowed heat).
    An empty-feed original is not a first costume: tryable ship without
    a thread goes github/HN; not tryable sits so x_empty_feed can kill.
    GitHub is the website. HN only when there is a
    clickable demo and no stack already chose the other costume.
    A lab notebook is not Show HN: exploration / decision / failure
    do not sit here — workshop on GitHub, or silence. Seminar only
    when a stranger can click and run it.
    Shopping while the window lives is not a new pick — the caller
    kills an explicit change; this keeps the locked costume when
    preferred is empty.
    """
    locked = parse_stack_arena(stack_arena)
    if locked is not None:
        return locked
    kind = (
        story_kind
        if isinstance(story_kind, StoryKind) or story_kind is None
        else StoryKind(story_kind)
    )
    seated = parse_stack_arena(preferred_arena)
    # #40: lab notebook is not Show HN. Exploration / decision / failure
    # do not sit — workshop or silence. Major / hard_issue still sit so
    # a missing tryable demo can die as hn_not_tryable.
    if seated is ArenaId.HN and kind in {
        StoryKind.EXPLORATION,
        StoryKind.DECISION,
        StoryKind.FAILURE,
    }:
        seated = None
    if seated is not None:
        return seated
    wanted = None
    if preferred_arena is not None and preferred_arena != "":
        try:
            wanted = (
                preferred_arena
                if isinstance(preferred_arena, ArenaId)
                else ArenaId(preferred_arena)
            )
        except ValueError:
            wanted = None
    # #49/#31: village without disclosure is spam. Sit so a named room
    # without ujawnienie + repo is silence.
    if wanted is ArenaId.REDDIT:
        return ArenaId.REDDIT
    # #57: empty tavern is silence. Sit so a public invite on emptiness dies.
    # #38: a decision is the workshop, never the tavern.
    if wanted is ArenaId.DISCORD and kind is not StoryKind.DECISION:
        return ArenaId.DISCORD
    # #55: pack without a feed is half the game. Sit so artifact-only cafe dies.
    if wanted is ArenaId.BLUESKY:
        return ArenaId.BLUESKY
    # #54/#51: letter gives first and signs a surname. Sit so nameless we/team dies.
    if wanted is ArenaId.NEWSLETTER:
        return ArenaId.NEWSLETTER
    # #27/#41: empty-feed original and reply-without-thought are silence.
    # Sit on a parent URL so agora can die closed. No thread: fall through
    # to github/HN when tryable; not tryable sits so x_empty_feed kills.
    if wanted is ArenaId.X and (parent_post or not tryable):
        return ArenaId.X
    # #37: cinema without title+promise is silence. Sit so a labeled
    # package or a fair hook is not a YouTube cut.
    if wanted is ArenaId.YOUTUBE:
        return ArenaId.YOUTUBE
    # #58: court is not a launch channel. Ship stays on github/hn.
    if wanted is ArenaId.LINKEDIN and not claims_ship:
        return ArenaId.LINKEDIN
    if (
        tryable
        and kind in {StoryKind.MAJOR, StoryKind.HARD_ISSUE}
        and clickable
        and not issues_disabled
        and not fork
        and not empty_repo
        and not private_repo
        and not archived_repo
        and not server_splash
    ):
        return ArenaId.HN
    return ArenaId.GITHUB


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
# A store is not click-and-run. App Store / Play / TestFlight as the only URL
# is silence on seminar. A store next to a repo can stay as evidence.
STORE_HOSTS: frozenset[str] = frozenset(
    {
        "apps.apple.com",
        "itunes.apple.com",
        "play.google.com",
        "testflight.apple.com",
    }
)
STORE_PITCH_RE = re.compile(
    r"(?i)\b(?:download the app|app store|google play|play store|testflight)\b"
)
# A launch board is not click-and-run. Product Hunt / BetaList as the only URL
# is silence on seminar. A card next to a repo can stay as evidence.
LAUNCH_HOSTS: frozenset[str] = frozenset(
    {
        "producthunt.com",
        "betalist.com",
    }
)
LAUNCH_PITCH_RE = re.compile(
    r"(?i)\b(?:launch(?:ed|ing)?\s+on\s+(?:ph|product\s*hunt)|product\s*hunt|betalist)\b"
)
# A magazine title is not a Show HN. "N ways", "you won't believe",
# or a trailing bang is silence on seminar. Curiosity, not a listicle.
LISTICLE_TITLE_RE = re.compile(
    r"(?i)(?:\b(?:\d+|n)\s+ways\b|you\s+(?:won'?t|will\s+not)\s+believe)"
)
# A carnival title is not a Show HN or a README one-liner. Emoji is silence
# on seminar/workshop. Arrows and ASCII stay; this is a sign, not length.
_EMOJI_RE = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # pictographs, faces, transport, supplemental
    "\U0001F1E6-\U0001F1FF"  # flags
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002700-\U000027BF"  # dingbats
    "\U0000FE0F"  # emoji presentation
    "\U00002B50"  # star
    "]"
)
# An article is not click-and-run. Medium / Substack / dev.to / hashnode as
# the only URL is silence on seminar. A blog next to a repo can stay as evidence.
BLOG_HOSTS: frozenset[str] = frozenset(
    {
        "medium.com",
        "substack.com",
        "dev.to",
        "hashnode.com",
        "hashnode.dev",
    }
)
# A newspaper is not a ship. NYT / BBC / TVN as the only URL is silence.
# A clipping next to a repo can stay as evidence. Commentary is not an angle.
NEWS_HOSTS: frozenset[str] = frozenset(
    {
        "nytimes.com",
        "washingtonpost.com",
        "bbc.com",
        "bbc.co.uk",
        "cnn.com",
        "reuters.com",
        "apnews.com",
        "theguardian.com",
        "foxnews.com",
        "wsj.com",
        "bloomberg.com",
        "politico.com",
        "npr.org",
        "aljazeera.com",
        "tvn24.pl",
        "wyborcza.pl",
        "polsatnews.pl",
        "notesfrompoland.com",
    }
)
# A deck is not a tryable artifact. Pitch / PDF slides / Notion one-pager
# as the only URL is silence. The website is the repo, not a slide pile.
# A deck next to a repo can stay as evidence. Neighbor of #40 (no tryable)
# and #122 (blog URL): here it is slides, not a blog.
DECK_HOSTS: frozenset[str] = frozenset(
    {
        "notion.so",
        "notion.site",
        "speakerdeck.com",
        "slideshare.net",
        "slideshare.com",
        "pitch.com",
    }
)
_GOOGLE_SLIDES_RE = re.compile(
    r"^https://docs\.google\.com/presentation(?:/.*)?$",
    re.I,
)
# A linktree is not a tryable artifact. Carrd / bio site / a list of
# links as the only URL is silence. The website is the repo, not a
# link board. A link page next to a repo can stay as evidence.
# Neighbor of #139 (CTA / link in bio) and #76 (trusted host): here
# it is a list page, not a CTA.
LINKTREE_HOSTS: frozenset[str] = frozenset(
    {
        "linktr.ee",
        "linktree.com",
        "carrd.co",
        "bio.site",
        "beacons.ai",
        "lnk.bio",
        "allmylinks.com",
        "hoo.be",
        "solo.to",
        "campsite.bio",
        "milkshake.app",
        "heylink.me",
        "linkin.bio",
        "about.me",
    }
)
# A ranking dump is not a tryable artifact. HN front / star-history /
# shields / stargazers as the only URL is silence. The website is the repo,
# not a vanity chart. A chart next to a repo can stay as evidence.
RANKING_HOSTS: frozenset[str] = frozenset(
    {
        "news.ycombinator.com",
        "hn.algolia.com",
        "star-history.com",
        "star-history.t9t.io",
        "shields.io",
        "img.shields.io",
        "gitstar-ranking.com",
    }
)
_GITHUB_VANITY_RE = re.compile(
    r"^https://github\.com/"
    r"(?:trending(?:/.*)?|"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:stargazers|watchers)(?:/.*)?)"
    r"$",
    re.I,
)
# HN front, star counter in the corner, vanity chart. Not a product angle.
# "star the repo after you try it" and a product dashboard stay.
RANKING_DUMP_RE = re.compile(
    r"(?i)(?:"
    r"\bhn\s+front(?:\s+page)?\b|"
    r"\bhacker\s+news\s+front(?:\s+page)?\b|"
    r"\bfront\s+page\s+of\s+(?:hn|hacker\s+news)\b|"
    r"\b(?:on|at)\s+the\s+(?:hn|hacker\s+news)\s+front\b|"
    r"(?:#1|\bnumber\s+one|\btop)\s+on\s+(?:hn|hacker\s+news)\b|"
    r"\bstar[- ]?(?:count|counter|badge|chart|history|dashboard)\b|"
    r"\bstars?\s+in\s+the\s+corner\b|"
    r"\blicznik\s+gwiazdek\b|"
    r"\bgwiazd(?:ek|ki)\s+w\s+k[aą]cie\b|"
    r"\bzrzut\s+rankingu\b|"
    r"\branking\s+dump\b|"
    r"\bwykres\s+(?:pr[oó][zż]no[ś]ci|gwiazdek|rankingu)\b|"
    r"\bvanity\s+(?:chart|graph|dashboard|metric)\b|"
    r"\bstargazers?\b"
    r")"
)

# A waitlist is not a ship. Coming soon / join the list / sign up to get
# access is not tryable and not Show HN. HN/X/shorts stay silent;
# changelog may keep the date. Empty copy is not a demo. Pair of #40.
WAITLIST_RE = re.compile(
    r"(?i)(?:"
    r"\bwaitlists?\b"
    r"|\bcoming\s+soon\b"
    r"|\bjoin\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?|mailing\s+lists?)\b"
    r"|\bsign\s*[- ]?up\s+to\s+get\s+(?:early\s+)?access\b"
    r"|\bsign\s*[- ]?up\s+for\s+(?:(?:early\s+)?access|(?:the|our|my)\s+(?:beta|waitlists?|lists?))\b"
    r"|\bget\s+on\s+(?:the|our|my)\s+(?:beta|waitlists?|lists?)\b"
    r"|\bget\s+early\s+access\b"
    r"|\brequest\s+(?:early\s+)?access\b"
    r"|\blanding\s+page\b"
    r"|\bno\s+demo\b"
    r")"
)
# Pending / yellow CI is not green. The look stays silent: not a ship, not
# "it is broken". We do not know the result, so we do not lie. Failed CI
# is a different gate (#81). A passing check / green CI stays. Pair of
# waitlist: unknown vs unpublished.
PENDING_CI_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:ci|checks?|check[- ]?runs?|check[- ]?suites?|status[- ]?checks?|"
    r"workflows?|actions|statusCheckRollup|status_check_rollup)"
    r"\s*(?:is\s+|are\s+|still\s+)?(?:pending|queued|in[- ]?progress|waiting|yellow)\b"
    r"|\b(?:pending|queued|in[- ]?progress|waiting|yellow)\s+"
    r"(?:ci|checks?|check[- ]?runs?|check[- ]?suites?|status[- ]?checks?|workflows?|actions)\b"
    r"|\b(?:statusCheckRollup|status_check_rollup|check[- ]?run|check[- ]?suite|"
    r"workflow[- ]?run)\"?\s*[:=]\s*\"?(?:pending|queued|in_progress|waiting|expected|requested)\b"
    r"|\bpending\s+(?:or\s+)?yellow\s+ci\b"
    r"|\byellow\s+(?:or\s+)?pending\s+ci\b"
    r"|\b(?:ci|checks?)\s+(?:jeszcze\s+)?(?:wisi|leci|czeka)\b"
    r"|\b(?:oczekuj[aą]c[aey]|w\s+toku)\s+(?:ci|check(?:i|ów)?|test(?:y|ów)?)\b"
    r"|\b(?:ci|check(?:i|ów)?|test(?:y|ów)?)\s+(?:oczekuj[aą]c[aey]|w\s+toku)\b"
    r"|\bżółt[aey]\s+(?:ci|check(?:i|ów)?)\b"
    r"|\b(?:ci|check(?:i|ów)?)\s+żółt[aey]\b"
    r")"
)
# Failed / red CI on the default branch is a false launch. Look stays
# silent: not tryable, not Show HN. Changelog may keep the tag. We do
# not say it works when main is red. Pending / yellow is a different
# gate (#82). A passing check / green CI stays. Pair of waitlist:
# broken vs unpublished.
FAILED_CI_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:ci|checks?|check[- ]?runs?|check[- ]?suites?|status[- ]?checks?|"
    r"workflows?|actions|statusCheckRollup|status_check_rollup)"
    r"\s*(?:is\s+|are\s+|still\s+)?(?:failed|failing|failure|broken|red)\b"
    r"|\b(?:failed|failing|failure|broken|red)\s+"
    r"(?:ci|checks?|check[- ]?runs?|check[- ]?suites?|status[- ]?checks?|workflows?|actions)\b"
    r"|\b(?:statusCheckRollup|status_check_rollup|check[- ]?run|check[- ]?suite|"
    r"workflow[- ]?run)\"?\s*[:=]\s*\"?(?:failure|failed|error|timed_out|startup_failure)\b"
    r"|\bred\s+(?:or\s+)?failed\s+ci\b"
    r"|\bfailed\s+(?:or\s+)?red\s+ci\b"
    r"|\b(?:default\s+branch|main)\s+(?:is\s+)?(?:red|failed)\b"
    r"|\b(?:ci|checks?)\s+(?:na\s+)?(?:default\s+branch|main)\s+(?:pad[lł][oay]?|czerwon)\b"
    r"|\bczerwon[aey]\s+(?:ci|check(?:i|ów)?|main)\b"
    r"|\b(?:ci|check(?:i|ów)?|main)\s+czerwon[aey]\b"
    r"|\bpadni[eę]t[aey]\s+(?:ci|check(?:i|ów)?)\b"
    r"|\b(?:ci|check(?:i|ów)?)\s+pad[lł][oay]?\b"
    r")"
)
# A GitHub draft / prerelease / RC / beta is not a ship. Only a published,
# non-prerelease release (or a merge with a tryable artifact) may claim
# ship. Changelog may keep the tag. Pair of waitlist: mailing list vs
# unpublished channel. "emits a draft" is operator copy, not this gate.
PRERELEASE_RE = re.compile(
    r"(?i)(?:"
    r"\bisDraft\"?\s*[:=]\s*\"?true\b"
    r"|\bis_draft\"?\s*[:=]\s*\"?true\b"
    r"|\bisPrerelease\"?\s*[:=]\s*\"?true\b"
    r"|\bis_prerelease\"?\s*[:=]\s*\"?true\b"
    r"|\bdraft\s+release\b"
    r"|\brelease\s+(?:is\s+)?(?:a\s+)?draft\b"
    r"|\bunpublished\s+(?:github\s+)?(?:draft\s+)?release\b"
    r"|\bgithub\s+draft\b"
    r"|\bpre[- ]?release\b"
    r"|\brelease\s+candidate\b"
    r"|\b(?:public|closed|open)\s+beta\b"
    r"|\b(?:rc|beta|alpha)\s+release\b"
    r"|\bv?\d+(?:\.\d+){1,3}[-.](?:rc|beta|alpha|pre)(?:[.-]?\d+)*\b"
    r"|\b(?:rc|beta|alpha)[.-]\d+\b"
    r"|/releases/tag/[A-Za-z0-9._~-]*(?:rc|beta|alpha|pre|draft)[A-Za-z0-9._~-]*"
    r"|\bwydanie\s+(?:robocze|szkic|wst[eę]pne)\b"
    r"|\bprzedpremier"
    r"|\bszkic\s+(?:wydania|release)\b"
    r")"
)
# A login wall is not a tryable artifact. HEAD/GET 401/403 = a stranger
# cannot run it. Silence on Show HN / ship claims. This is a gate, not a
# 404 corpse. Pair of waitlist: mailing list vs bramka.
# A login form as a product feature stays; a gated demo does not.
LOGIN_GATE_RE = re.compile(
    r"(?i)(?:"
    r"\bbehind\s+(?:a\s+|an\s+)?(?:login|sign[- ]?in|auth(?:entication)?|paywall)\b"
    r"|\b(?:login|sign[- ]?in|auth(?:entication)?)\s+(?:wall|gate|required|gated)\b"
    r"|\b(?:requires?|must)\s+(?:a\s+|an\s+)?(?:login|log[- ]?in|sign[- ]?in)\b"
    r"|\b(?:requires?|must)\s+an?\s+account\b"
    r"|\b(?:log|sign)\s*[- ]?in\s+to\s+(?:continue|view|access|see|try|run|use)\b"
    r"|\b(?:create\s+an?\s+account|register|sign\s*up)\s+to\s+(?:continue|view|access|see|try|run|use)\b"
    r"|\b(?:head|get)(?:\s*/\s*get)?\s+(?:returned\s+)?(?:401|403)\b"
    r"|\b(?:401|403)\s*/\s*(?:403|401)\b"
    r"|\b(?:401|403)\s+(?:unauthorized|forbidden)\b"
    r"|\bza\s+logowaniem\b"
    r"|\bwymaga\s+logowania\b"
    r"|\bbramk[aąę]\s+logowania\b"
    r")"
)
# A redirect hop is the chain, not the first URL. Host + https (#76/#77),
# not a 404 corpse (#92). A few hops stay tryable only when every host is
# on the list. A shortener or other origin is silence, not click-and-run.
MAX_ARTIFACT_REDIRECT_HOPS = 3
TRYABLE_ARTIFACT_HOSTS: frozenset[str] = frozenset({"github.com"})
SHORTENER_HOSTS: frozenset[str] = frozenset(
    {
        "bit.ly",
        "tinyurl.com",
        "t.co",
        "goo.gl",
        "ow.ly",
        "is.gd",
        "buff.ly",
        "rebrand.ly",
        "cutt.ly",
        "rb.gy",
        "shorturl.at",
        "tiny.cc",
    }
)
REDIRECT_CHAIN_RE = re.compile(
    r"(?i)(?:"
    r"\bredirect(?:s|ed|ing)?\b|"
    r"\bhop(?:s)?\s+to\b|"
    r"\blocation\s*:|"
    r"\b(?:301|302|303|307|308)\b|"
    r"\bskracacz\b|"
    r"\bshortener\b|"
    r"\binny\s+origin\b|"
    r"\boff[- ]allowlist\b"
    r")"
)
_ARROW_SPLIT_RE = re.compile(r"\s*(?:->|→|=>|»)\s*")
SHORTENER_TALK_RE = re.compile(
    r"(?i)(?:"
    r"\bskracacz\b|"
    r"\bshortener\b|"
    r"\binny\s+origin\b|"
    r"\bbit\.ly\b|"
    r"\btinyurl\.com\b|"
    r"\bt\.co\b"
    r")"
)
# A tracking farm is not a tryable demo. utm_* / fbclid / gclid on the
# artifact, or “kliknij tu” / click here as the pitch, is silence.
# Pair of #76: host allowlist first, then no bait on that host.
UTM_FARM_RE = re.compile(
    r"(?i)(?:"
    r"\butm_(?:source|medium|campaign|term|content|id)\b|"
    r"\butm[- ]farm\b|"
    r"\bfbclid\b|"
    r"\bgclid\b|"
    r"\bmc_cid\b|"
    r"\bmc_eid\b"
    r")"
)
CLICK_HERE_RE = re.compile(
    r"(?i)(?:"
    r"\bclick[-_ ]here\b|"
    r"\bkliknij[-_ ]tu(?:taj)?\b"
    r")"
)
_UTM_QUERY_KEYS = frozenset(
    {
        "utm_source",
        "utm_medium",
        "utm_campaign",
        "utm_term",
        "utm_content",
        "utm_id",
        "fbclid",
        "gclid",
        "mc_cid",
        "mc_eid",
    }
)
# A 404/410 artifact is not tryable. HEAD/GET status, not a URL scheme
# (#76/#77 are host+https). A probe would be bounded like gh (#79);
# recorded timeout is the same silence. Do not promise Show HN or a
# ship claim on a corpse. Do not click the corpse. Pair of login wall
# (401/403) and listed release asset (download 404). Bare HEAD 404 /
# GET 410 / 404/410 is this gate.
DEAD_LINK_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:head|get)(?:\s*/\s*get)?\s+(?:returned\s+)?(?:404|410)\b"
    r"|\b(?:head|get)(?:\s*/\s*get)?\s+timeout\b"
    r"|\b(?:404|410)\s*/\s*(?:410|404)\b"
    r"|\b(?:404|410)\s+(?:not\s+found|gone)\b"
    r"|\bdead\s+link\b"
    r"|\bmartw[yiae]\s+link\b"
    r")"
)
# A dead TLS artifact is not tryable. Certificate error, mixed content,
# HTTPS the browser rejects = silence. Neighbor of #77 (https only)
# and #92 (404/410 corpse): here it is the cert, not the scheme or a
# 404. Do not click the warning. A working handshake stays.
DEAD_TLS_REASON = "dead_tls_not_tryable"
DEAD_TLS_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:ssl|tls)\s+(?:error|handshake\s+fail(?:ed|ure)?|alert)\b"
    r"|\b(?:certificate|cert)\s+(?:error|warning|invalid|expired|untrusted|rejected|mismatch)\b"
    r"|\b(?:expired|invalid|untrusted|self[- ]signed|rejected)\s+(?:ssl\s+|tls\s+)?(?:certificate|cert)\b"
    r"|\bmixed[- ]content\b"
    r"|\bnet::err_cert"
    r"|\berr_cert_(?:authority_invalid|common_name_invalid|date_invalid)\b"
    r"|\bssl_error_"
    r"|\byour\s+connection\s+is\s+not\s+private\b"
    r"|\bthis\s+site\s+is\s+not\s+secure\b"
    r"|\bhttps\s+(?:rejected|odrzucon)\b"
    r"|\bbrowser\s+reject(?:s|ed|ing)?\s+https\b"
    r"|\bhttps\s+kt[oó]r[yiae]\s+przegl[aą]darka\s+odrzuca\b"
    r"|\bprzegl[aą]darka\s+odrzuca\s+https\b"
    r"|\bclick\s+(?:through|past)\s+(?:the\s+)?(?:cert(?:ificate)?|tls|ssl|security)\s+warning\b"
    r"|\bkliknij\s+w\s+ostrze[zż]enie\b"
    r"|\bmartw[yiae]\s+tls\b"
    r"|\bb[lł][aą]d\s+(?:ssl|tls|certyfikat)"
    r"|\bcertyfikat\s+(?:odrzucon|niewa[zż]n|wygas)"
    r"|\bodrzucon[yiae]\s+https\b"
    r"|\bpo[lł][aą]czenie\s+nie\s+jest\s+prywatne\b"
    r")"
)
# Issues disabled is not a camp. Show HN and the social angle sit on the
# repo during the spike. No issues tracker = no camp = silence. README
# and changelog may still move. Pair of waitlist: no inbox vs no demo.
# "issues" as a product noun stays; a closed tracker does not.
ISSUES_DISABLED_RE = re.compile(
    r"(?i)(?:"
    r"\bhasIssuesEnabled\"?\s*[:=]\s*\"?false\b"
    r"|\bhas_issues\"?\s*[:=]\s*\"?false\b"
    r"|\bissues\"?\s*[:=]\s*\"?(?:false|off|disabled|wy[lł][aą]czone)\b"
    r"|\b(?:issues?|issue\s+tracker)\s+(?:are\s+|is\s+)?(?:disabled|turned\s+off|switched\s+off|off)\b"
    r"|\b(?:disabled|turned\s+off|switched\s+off)\s+(?:the\s+)?(?:issues?|issue\s+tracker)\b"
    r"|\bno\s+issue\s+tracker\b"
    r"|\bwithout\s+(?:an?\s+)?issue\s+tracker\b"
    r"|\brepo\s+(?:z\s+)?wy[lł][aą]czon(?:ymi|e|ych)\s+issues\b"
    r"|\bwy[lł][aą]czon(?:e|ymi|ych)\s+issues\b"
    r"|\bissues\s+wy[lł][aą]czon(?:e|ymi|ych)\b"
    r")"
)
# A fork is not a website. isFork, even when the owner is ours, is
# silence. Angle from the canonical source, not a copy. Helping
# upstream is silence here, not our launch. Pair of #73 (watch only
# our repo) and nie-klon. "fork" as a product noun stays; a GitHub
# copy does not.
FORK_RE = re.compile(
    r"(?i)(?:"
    r"\bisFork\"?\s*[:=]\s*\"?true\b"
    r"|\bis_fork\"?\s*[:=]\s*\"?true\b"
    r"|\bfork\"?\s*[:=]\s*\"?true\b"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+a\s+fork\b"
    r"|\bfork\s+of\s+(?:https?://)?github\.com/\b"
    r"|\bforked\s+from\b"
    r"|\bforked\s+(?:this\s+)?(?:repo(?:sitory)?|project)\b"
    r"|\ba\s+fork\s+of\b"
    r"|\bupstream\s+(?:is|at)\s+(?:https?://)?github\.com/\b"
    r"|\bparentRepo(?:sitory)?\"?\s*[:=]"
    r"|\bparent\"?\s*[:=]\s*\"?[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\b"
    r"|\bnie\s+jest\s+witryn"
    r"|\bfork\s+nie\s+jest\b"
    r"|\bkopi[ae]\s+(?:repo|repozytorium|upstream)\b"
    r"|\bto\s+jest\s+fork\b"
    r")"
)
# An empty repo is not a website. No tree or no README is silence.
# This is not README-without-a-GIF (#48): here there is not even a card.
# Pair of puste and kartka. A working README stays; an empty tree does not.
EMPTY_REPO_RE = re.compile(
    r"(?i)(?:"
    r"\bisEmpty\"?\s*[:=]\s*\"?true\b"
    r"|\bis_empty\"?\s*[:=]\s*\"?true\b"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+empty\b"
    r"|\bempty\s+(?:git\s+)?tree\b"
    r"|\bno\s+default\s+branch\b"
    r"|\bwithout\s+(?:a\s+)?default\s+branch\b"
    r"|\bno\s+readme(?:\s+file)?\b"
    r"|\bwithout\s+(?:a\s+)?readme(?:\s+file)?\b"
    r"|\bmissing\s+readme(?:\s+file)?\b"
    r"|\bbrak\s+(?:drzewa|readme)\b"
    r"|\bbez\s+readme\b"
    r"|\bpuste\s+repo\b"
    r"|\bnie\s+ma\s+witryn"
    r"|\bnie\s+ma\s+nawet\s+kartk"
    r"|\bdiskUsage\"?\s*[:=]\s*\"?0\b"
    r"|\bdisk_usage\"?\s*[:=]\s*\"?0\b"
    r")"
)
# A private repo is not a website. isPrivate, even when the owner is ours,
# is silence. Watch on private is silence, not a 404 loop. Survey is
# already public; this is fail-closed on watch. Workshop is a public
# README. Pair of #73 (watch only our repo) and #48 (README without a demo).
# A living public repo stays; a locked tree does not.
PRIVATE_REPO_RE = re.compile(
    r"(?i)(?:"
    r"\bisPrivate\"?\s*[:=]\s*\"?true\b"
    r"|\bis_private\"?\s*[:=]\s*\"?true\b"
    r"|\bvisibility\"?\s*[:=]\s*\"?private\b"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+private\b"
    r"|\bprivate\s+(?:git(?:hub)?\s+)?repo(?:sitory)?\b"
    r"|\brepo(?:sitory)?\s+is\s+private\b"
    r"|\bprywatn[aey]\s+repo"
    r")"
)
# A template repo is not a product. isTemplate, or generate-from-template
# without an own ship, is silence. Show HN from boilerplate is silence.
# Pair of #40 (Show HN without tryable) and #46 (waitlist is not a ship).
# A product that happens to mention a PR/issue template stays; the
# GitHub template / cookiecutter starter does not.
TEMPLATE_RE = re.compile(
    r"(?i)(?:"
    r"\bisTemplate\"?\s*[:=]\s*\"?true\b"
    r"|\bis_template\"?\s*[:=]\s*\"?true\b"
    r"|\btemplateRepository\"?\s*[:=]"
    r"|\btemplate_repository\"?\s*[:=]"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+a\s+template\b"
    r"|\bgithub\s+template\s+repo(?:sitory)?\b"
    r"|\bgenerat(?:e|ed)\s+from(?:\s+a)?\s+template\b"
    r"|\bgenerate-from-template\b"
    r"|\bcreated\s+from(?:\s+a)?\s+template\b"
    r"|\binitial\s+commit\s+from(?:\s+a)?\s+template\b"
    r"|\buse\s+this\s+template\b"
    r"|\bboilerplate\s+(?:repo(?:sitory)?|project|app|code)\b"
    r"|\bthis\s+is\s+(?:just\s+)?boilerplate\b"
    r"|\bfrom\s+cookiecutter\b"
    r"|\bcookiecutter\s+template\b"
    r"|\brepo-szablon\b"
    r"|\bszablon\s+to\s+nie\s+produkt\b"
    r"|\bto\s+jest\s+szablon\b"
    r")"
)
# An archived or disabled repo is dead. Watch on a museum is silence.
# Do not launch a museum. Pair of #74 (private is not a website).
# A living public repo stays; a tombstone does not.
ARCHIVED_REPO_RE = re.compile(
    r"(?i)(?:"
    r"\bisArchived\"?\s*[:=]\s*\"?true\b"
    r"|\bis_archived\"?\s*[:=]\s*\"?true\b"
    r"|\bisDisabled\"?\s*[:=]\s*\"?true\b"
    r"|\bis_disabled\"?\s*[:=]\s*\"?true\b"
    r"|\barchived\"?\s*[:=]\s*\"?true\b"
    r"|\bdisabled\"?\s*[:=]\s*\"?true\b"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+archived\b"
    r"|\bthis\s+(?:repo(?:sitory)?|project)\s+is\s+disabled\b"
    r"|\barchived\s+(?:git(?:hub)?\s+)?repo(?:sitory)?\b"
    r"|\bdisabled\s+(?:git(?:hub)?\s+)?repo(?:sitory)?\b"
    r"|\brepo(?:sitory)?\s+is\s+(?:archived|disabled)\b"
    r"|\barchivedAt\"?\s*[:=]"
    r"|\barchived_at\"?\s*[:=]"
    r"|\bzarchiwizowan"
    r"|\bmartwe\s+repo\b"
    r"|\bnie\s+launchujemy\s+muzeum\b"
    r"|\blaunch\s+muzeum\b"
    r")"
)
# A default server splash is not a product. Welcome to nginx / Apache
# default / Caddy placeholder = cisza. Pair of #25 (broken site) and
# #157 (parked domain): here the box answered, the page is stock.
# A working nginx/Apache/Caddy config stays; the factory page does not.
SERVER_SPLASH_RE = re.compile(
    r"(?i)(?:"
    r"\bwelcome\s+to\s+nginx\b"
    r"|\bnginx\s+(?:default|welcome|test)\s+page\b"
    r"|\bit\s+works!\s+this\s+is\s+the\s+default\s+web\s+page\s+for\s+this\s+server\b"
    r"|\bapache2?(?:\s+\w+){0,3}\s+default\s+page\b"
    r"|\bapache2?\s+(?:http\s+server\s+)?(?:default|test)\s+page\b"
    r"|\btest\s+page\s+(?:for|powered\s+by).{0,40}\bapache\b"
    r"|\bthis\s+page\s+is\s+used\s+to\s+test\s+the\s+proper\s+operation\s+of\s+the\s+apache\b"
    r"|\bif\s+you\s+see\s+this\s+page,\s+the\s+nginx\s+web\s+server\s+is\s+successfully\s+installed\b"
    r"|\bcaddy\s+(?:default|placeholder|welcome)\s+page\b"
    r"|\bcaddy\s+works!?\b"
    r"|\bcongratulations,?\s+caddy\s+is\s+working\b"
    r"|\bcaddy\s+is\s+(?:up\s+and\s+running|working)\b"
    r"|\bserver\s+splash\b"
    r"|\bsplash\s+serwera\b"
    r"|\bdomy[sś]ln[aey]\s+stron[aey]\s+serwera\b"
    r"|\bstrona\s+domy[sś]lna\s+serwera\b"
    r")"
)
# A listed release asset that 404s/410s is not a ship. The file is on
# the list; download is gone. Silence. Do not promise a binary that
# is not there. Pair of empty release: empty tag vs listed corpse.
# A 401/403 login wall is a different gate. A generic dead link without
# an asset/download is not this gate.
DEAD_RELEASE_ASSET_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:asset|binary|file|download|plik)\s+"
    r"(?:on\s+(?:the\s+)?(?:release\s+)?list|na\s+li[sś]cie)\b"
    r".{0,48}\b(?:404|410|gone|martw)\b"
    r"|\b(?:404|410|gone)\b.{0,48}\b(?:asset|binary|file|download|plik)\s+"
    r"(?:on\s+(?:the\s+)?(?:release\s+)?list|na\s+li[sś]cie)\b"
    r"|\b(?:release\s+)?(?:asset|binary|download)(?:\s+url)?\s+"
    r"(?:is\s+|returned\s+|returns?\s+)?(?:404|410)\b"
    r"|\b(?:404|410)\s+(?:on|for|from)\s+(?:the\s+)?(?:release\s+)?(?:asset|binary|download|plik)\b"
    r"|\bbrowser_download(?:_url)?\s+(?:returned\s+|is\s+|returns?\s+)?(?:404|410)\b"
    r"|\bdead\s+(?:release\s+)?(?:asset|file|binary)\b"
    r"|\bmartw[yiae]\s+plik\b"
    r"|\bpobranie\s+(?:returned\s+)?(?:404|410)\b"
    r")"
)
# A calendar is not a ship. Coming Q3 / soon / on the roadmap without a
# tryable artifact is social silence. Changelog may keep the date.
# Pair of waitlist: mailing list vs calendar. "as soon as" is not vapor.
ROADMAP_RE = re.compile(
    r"(?i)(?:"
    r"\bon\s+(?:the|our|this)\s+roadmap\b"
    r"|\bcoming\s+(?:in\s+)?q[1-4]\b"
    r"|\bcoming\s+(?:this|next)\s+(?:quarter|year|month)\b"
    r"|\bcoming\s+20\d{2}\b"
    r"|\b(?:coming|shipping|launching|arriving|dropping|releasing|available)\s+soon\b"
    r"|(?:^|(?<=[.!?:]\s))soon(?:\s*[.!]|$)"
    r"|\bplanned\s+for\s+q[1-4]\b"
    r"|\bna\s+roadmap(?:ie)?\b"
    r"|\bw\s+roadmap(?:ie)?\b"
    r"|\bna\s+mapie\s+drogowej\b"
    r"|\bwkr[oó]tce\b"
    r"|\bplanowane\s+na\s+q[1-4]\b"
    r")"
)
# An event is not a ship. Webinar / meetup / calendar / join us Thursday is
# cisza, not an artifact. Changelog may keep the date. Pair of waitlist
# (#46, mailing list) and roadmap (#129, coming Q3). This is the date on
# the wall, not a tryable drop. "calendar year" is not an invite.
EVENT_NOT_A_SHIP = "event_not_a_ship"
EVENT_RE = re.compile(
    r"(?i)(?:"
    r"\bwebinars?\b"
    r"|\bmeet[- ]?ups?\b"
    r"|\bcalendars?\b(?!\s+year\b)"
    r"|\bkalendarz(?:e|a|u|owi|em|ach)?\b"
    r"|\bwydarzeni(?:e|a|u|em|om|ami|ach)\b"
    r"|\bjoin\s+us\s+(?:this\s+|next\s+)?"
    r"(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week|month)\b"
    r"|\bdo[lł][aą]cz(?:cie)?\s+(?:do\s+nas\s+)?(?:w\s+)?"
    r"(?:poniedzia[lł]ek|wtorek|[sś]rod[eę]|czwartek|pi[aą]tek)\b"
    r")"
)
# A calendar does not write for us. Holiday / repo birthday / happy Friday
# is silence, not a product. Neighbor of event (#138, meetup) and world
# commentary (#131, news of the day). This is the date as a greeting, not
# a tryable drop. "calendar year" and "shipped Friday" stay.
CALENDAR_FILLER_REASON = "calendar_filler"
CALENDAR_FILLER_RE = re.compile(
    r"(?i)(?:"
    r"\bhappy\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|holidays?)\b"
    r"|\bhappy\s+new\s+year\b"
    r"|\bmerry\s+christmas\b"
    r"|\bseason['’]?s\s+greetings\b"
    r"|\b(?:repo(?:sitory)?|project)\s+(?:birthday|anniversary)\b"
    r"|\bbirthday\s+of\s+(?:the\s+)?(?:repo(?:sitory)?|project)\b"
    r"|\b(?:repo(?:sitory)?|project)\s+turns\s+\d+\b"
    r"|\burodzin(?:y|om|ach)?\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\brocznic[aeyę]\s+(?:repo(?:zytorium)?|projektu)\b"
    r"|\bweso[lł]ych\s+[sś]wi[aą]t\b"
    r"|\bz\s+okazji\s+[sś]wi[aą]t\b"
    r"|\bmi[lł]ego\s+(?:pi[aą]tku|weekendu)\b"
    r"|\btgif\b"
    r"|\b[sś]wi[eę]t(?:a|o)\b"
    r")"
)
# A thank-you for a vanity counter is not an angle. "Thanks for N stars"
# / a follower milestone is silence, not product history. Neighbor of #56
# (dead stars are not a story) and #134 (a ranking dump is not an artifact).
# Here it is the thank-you, not the chart. "thanks for the issue" and
# "thanks for watching" stay with their own gates.
COUNTER_THANKS_REASON = "counter_thanks"
_COUNTER_TOTAL = r"(?:n|\d{1,3}(?:,\d{3})+|(?:\d+))(?:\.\d+)?[kmb]?"
_COUNTER_UNIT = (
    r"(?:github\s+)?(?:stars?|stargazers?|follows?(?!-?ups?\b|ing\b)|"
    r"followers?|watchers?|gwiazd(?:ek|ki|ka|k\u0105)?|obserwacj\w*|obserwuj\w*)"
)
COUNTER_THANKS_RE = re.compile(
    r"(?i)(?:"
    r"\bthanks?\s+(?:to\s+)?(?:everyone\s+)?for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bthank\s+you\s+(?:to\s+)?(?:everyone\s+)?for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bgrateful\s+for\s+"
    r"(?:all\s+)?(?:the\s+|our\s+|every\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?{_COUNTER_UNIT}\b"
    r"|\bdzi[eę]k\w*\s+za\s+(?:ka[zż]d\w*\s+)?"
    rf"(?:{_COUNTER_TOTAL}\s+)?(?:gwiazd(?:ek|ki|ka|k\u0105)?|obserwacj\w*|follow(?:y|ów)?)\b"
    r"|\bpodzi[eę]kowani\w*\s+za\s+(?:licznik|gwiazd|follow|obserw)"
    r"|\bmilestone\s+follow\b"
    r"|\b(?:star|follow(?:er)?)\s+milestone\b"
    rf"|\b{_COUNTER_TOTAL}\s+follow(?:er)?\s+milestone\b"
    r"|\b(?:hit|reached|crossed)\s+"
    rf"{_COUNTER_TOTAL}\s+{_COUNTER_UNIT}\b"
    r".{0,40}\b(?:thanks?|thank\s+you)\b"
    r")"
)
# Fog is not an angle. A subtweet / you-know-who / unnamed allusion
# is silence. Name the artifact or stay quiet. Neighbor of dunk (#116,
# mockery) and world commentary (#131, a take on headlines). Here it
# is the hint, not the dunk. "Unlike Loki" and a named difference stay.
FOG_REASON = "fog"
FOG_RE = re.compile(
    r"(?i)(?:"
    r"\bsubtweets?\b"
    r"|\bsubtweeting\b"
    r"|\byou[- ]know[- ]who\b"
    r"|\bif\s+you\s+know\s*,?\s+you\s+know\b"
    r"|\bthose\s+who\s+know\s*,?\s+know\b"
    r"|\bthey\s+know\s+who\s+they\s+are\b"
    r"|\biykyk\b"
    r"|\ba\s+certain\s+(?:someone|somebody|project|tool|repo|competitor|person)\b"
    r"|\b(?:we\s+)?(?:won['’]?t|do\s+not|don['’]?t)\s+name\s+names\b"
    r"|\bnot\s+naming\s+names\b"
    r"|\bunnamed\s+(?:competitor|project|tool|repo|someone)\b"
    r"|\bread(?:ing)?\s+between\s+the\s+lines\b"
    r"|\bhint\s+hint\b"
    r"|\baluzj[aąeęi]\b"
    r"|\bwiecie\s+kto\b"
    r"|\bnie\s+wymieniamy?\s+nazw"
    r"|\bpewien\s+(?:kto[sś]|projekt|narz[eę]dzie)\b"
    r"|\bmg[lł]a\b"
    r")"
)
# A founder journal is not an angle. Desk setup / tools I use / day in
# the life / morning routine is silence, not a product. Neighbor of
# hire/fundraise (#130, we are hiring) and event (#138, meetup). Here it
# is lifestyle, not a tryable drop. "setup.py" and "this morning we
# shipped" stay.
FOUNDER_JOURNAL_REASON = "founder_journal"
FOUNDER_JOURNAL_RE = re.compile(
    r"(?i)(?:"
    r"\bdesk\s+setups?\b"
    r"|\bdesk\s+tours?\b"
    r"|\boffice\s+tours?\b"
    r"|\bworkstation\s+setups?\b"
    r"|\bwhat(?:['’]?s| is)\s+on\s+(?:my|our)\s+desk\b"
    r"|\btools?\s+(?:i|we|they)\s+use[ds]?\b"
    r"|\bgear\s+(?:i|we)\s+use[ds]?\b"
    r"|\ba?\s*days?\s+in\s+(?:the|my|our|a)\s+life\b"
    r"|\bday[- ]in[- ]the[- ]life\b"
    r"|\bmorning\s+routines?\b"
    r"|\bmorning\s+rituals?\b"
    r"|\bfounder(?:['’]?s)?\s+(?:journal|diary|log)\b"
    r"|\bbuilder(?:['’]?s)?\s+(?:journal|diary)\b"
    r"|\bdziennik(?:u|iem|owi)?\s+za[lł]o[zż]yciel"
    r"|\bsetup\s+biurk"
    r"|\bbiurk(?:o|a)\s+(?:setup|tour)"
    r"|\bnarz[eę]dzi(?:a|e)\s+(?:kt[oó]r(?:e|ych)\s+)?u[zż]ywam\b"
    r"|\bnarz[eę]dzi(?:a|e)\s+(?:kt[oó]r(?:e|ych)\s+)?u[zż]ywamy\b"
    r"|\bmoje\s+narz[eę]dzi"
    r"|\bdzie[nń]\s+z\s+[zż]ycia\b"
    r"|\bporann[aąe]\s+rutyn"
    r"|\brutyna\s+porann"
    r")"
)
# A lead magnet is not an angle. Ebook / free guide / typeform for
# an email is silence, not tryable. Neighbor of waitlist (#46, join
# the list) and login gate (#126, artifact behind auth). Here it is
# the mail gate, not the waitlist. A user guide and email
# notifications stay.
LEAD_MAGNET_REASON = "lead_magnet"
LEAD_MAGNET_RE = re.compile(
    r"(?i)(?:"
    r"\blead[- ]magnets?\b"
    r"|\bebooks?\b"
    r"|\be[- ]books?\b"
    r"|\bfree\s+guides?\b"
    r"|\bfree\s+pdfs?\b"
    r"|\btypeforms?\b"
    r"|\bdownload\s+(?:the|our|my)\s+(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist|whitepaper)\b"
    r"|\bget\s+(?:the|our|my)\s+(?:free\s+)?(?:guide|ebook|e-book|pdf)\b"
    r"|\benter\s+your\s+e[- ]?mail\s+to\s+(?:download|unlock|get|receive)\s+"
    r"(?:the\s+|our\s+|my\s+)?(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist)\b"
    r"|\be[- ]?mail\s+to\s+(?:download|unlock|get|receive)\s+"
    r"(?:the\s+|our\s+|my\s+)?(?:free\s+)?(?:guide|ebook|e-book|pdf|checklist)\b"
    r"|\bswap\s+(?:your\s+)?e[- ]?mail\s+for\b"
    r"|\bgated\s+(?:pdf|content|guide|ebook|e-book)\b"
    r"|\bopt[- ]in\s+(?:form|pdf|guide|ebook)\b"
    r"|\bemail\s+gates?\b"
    r"|\bmail\s+gates?\b"
    r"|\bmagnet\s+za\s+mail"
    r"|\be[- ]?book\s+za\s+mail"
    r"|\bdarmow(?:y|e|a)\s+(?:przewodnik|ebook|e-book|pdf)\b"
    r"|\bza\s+maila\b"
    r"|\bbramk[aąę]\s+mail"
    r")"
)
# A logo reveal is not a ship. Rebrand / palette / moodboard / odsłona
# logo is cisza, not a product. Neighbor of founder journal (#146,
# lifestyle) and roadmap (#129, a calendar). Here it is the look, not
# a tryable drop. "logo intro", "outro-logo", and a README logo stay.
LOGO_REVEAL_NOT_A_SHIP = "logo_reveal_not_a_ship"
LOGO_REVEAL_RE = re.compile(
    r"(?i)(?:"
    r"\bre-?brands?(?:ing)?\b"
    r"|\bbrand\s+refresh(?:es)?\b"
    r"|\bnew\s+brands?\b"
    r"|\bvisual\s+identity\b"
    r"|\bbrand\s+identity\b"
    r"|\b(?:color|colour|brand|new)\s+palettes?\b"
    r"|\bpalet[aąęy]\b"
    r"|\bmood[- ]?boards?\b"
    r"|\blogo\s+reveals?\b"
    r"|\breveal(?:ing|s|ed)?\s+(?:the\s+|our\s+|a\s+)?(?:new\s+)?logos?\b"
    r"|\blogo\s+unveil(?:s|ed|ing)?\b"
    r"|\bunveil(?:ing|s|ed)?\s+(?:the\s+|our\s+|a\s+)?(?:new\s+)?logos?\b"
    r"|\bnew\s+logos?\b"
    r"|\blogo\s+drops?\b"
    r"|\blogo\s+redesigns?\b"
    r"|\bods[lł]on[aąęy]\s+logo\b"
    r"|\bods[lł]aniamy\s+logo\b"
    r"|\bods[lł]oni[eę]cie\s+logo\b"
    r"|\bnowe\s+logo\b"
    r"|\bnow[aą]\s+palet"
    r"|\bnowy\s+branding\b"
    r")"
)
# Artificial FOMO is not an angle. Only N spots / countdown /
# last chance is silence, not a product. Neighbor of bait (#114,
# a gesture) and waitlist (#46, a list). Here it is pressure.
FOMO_REASON = "fomo"
FOMO_RE = re.compile(
    r"(?i)(?:"
    r"\bfomo\b"
    r"|\blast\s+chances?\b"
    r"|\blast\s+calls?\b"
    r"|\bcount[- ]?downs?\b"
    r"|\bonly\s+(?:n|\d+)\s+(?:spots?|seats?|places?|slots?|tickets?)\b"
    r"|\bonly\s+(?:a\s+)?few\s+(?:spots?|seats?|places?|slots?)\b"
    r"|\blast\s+(?:n|\d+)\s+(?:spots?|seats?|places?|slots?)\b"
    r"|\blimited\s+(?:spots?|seats?|places?|slots?|tickets?)\b"
    r"|\b(?:spots?|seats?|places?|slots?)\s+(?:left|remaining)\b"
    r"|\blimited[- ]time\b"
    r"|\bending\s+soon\b"
    r"|\bdon['’]?t\s+miss\s+out\b"
    r"|\bwhile\s+supplies\s+last\b"
    r"|\bostatni[aea]\s+szans"
    r"|\btylko\s+(?:n|\d+)\s+miejsc"
    r"|\bostatni[ae]\s+miejsc"
    r"|\bodliczani"
    r")"
)
# A meme is not an angle. Drake / wojak / reaction image
# without a thing is silence. Neighbor of voice mix (#45)
# and ranking dump (#134, a vanity chart). Here it is the
# picture, not a product. A screenshot of the demo and
# "remember" stay. Costume is not a meme board.
MEME_REASON = "meme"
MEME_RE = re.compile(
    r"(?i)(?:"
    r"\bmemes?\b"
    r"|\bdrake\b"
    r"|\bhotline\s+bling\b"
    r"|\bwojaks?\b"
    r"|\bsoyjaks?\b"
    r"|\breaction\s+(?:images?|gifs?|memes?|pics?|pictures?)\b"
    r"|\bmeme\s+(?:templates?|formats?|dumps?|boards?|walls?)\b"
    r"|\btablic[aąęy]\s+z\s+mem"
    r"|\b(?:sciana|ściana)\s+mem"
    r"|\bmem(?:y|ów|ow|ami|em|ie|ach|om)\b"
    r")"
)
# A deck is not an artifact. Pitch / PDF slides / Notion one-pager
# without a clickable product is silence. Neighbor of Show HN without
# tryable (#40) and blog-as-Show (#122). Here it is slides, not a blog.
# A screenshot of the demo and "on deck" stay. Costume is not a pitch.
DECK_REASON = "deck_not_an_artifact"
DECK_RE = re.compile(
    r"(?i)(?:"
    r"\bpitch\s+decks?\b"
    r"|\binvestor\s+(?:decks?|pitches?)\b"
    r"|\bslide\s+decks?\b"
    r"|\bslide\s+pdfs?\b"
    r"|\bpdf\s+(?:of\s+)?(?:the\s+)?slides?\b"
    r"|\bpdf\s+slajd"
    r"|\bslajd(?:y|ów|ami|ach|om|em)?\b"
    r"|\bone[- ]pagers?\b"
    r"|\bnotion\s+(?:one[- ]pager|page|doc)\b"
    r"|\bpitch(?:es)?\s+(?:pdf|slides?|deck)\b"
    r"|\b(?:our|the|this)\s+pitch\b"
    r"|\bpitch\s+(?:for|to)\s+(?:investors?|vcs?|angels?)\b"
    r"|\b(?:our|the|this)\s+decks?\b"
    r"|\bspeakerdecks?\b"
    r"|\bslideshare\b"
    r"|\bgoogle\s+slides\b"
    r"|\bdeck\s+nie\s+jest\s+artefakt"
    r")"
)
# A linktree is not an artifact. Carrd / bio site / a list of links
# instead of a product is silence. Neighbor of CTA in DM / link in
# bio (#139) and trusted host (#76). Here it is a list page, not a
# CTA. "link in the README" and a product site stay.
LINKTREE_REASON = "linktree_not_an_artifact"
LINKTREE_RE = re.compile(
    r"(?i)(?:"
    r"\blinktrees?\b"
    r"|\blinktr\.ee\b"
    r"|\bcarrds?\b"
    r"|\bbio\s+sites?\b"
    r"|\bbiosites?\b"
    r"|\blista\s+link"
    r"|\blink\s+lists?\b"
    r"|\blists?\s+of\s+links?\b"
    r"|\blink\s+boards?\b"
    r"|\ball\s+my\s+links?\b"
    r"|\bmy\s+links?\s+page\b"
    r"|\blinks?\s+page\b"
    r"|\bstron[aąeęy]\s+z\s+link"
    r"|\btablic[aąęy]\s+link"
    r"|\bbeacons\.ai\b"
    r"|\blinktree\s+nie\s+jest\s+artefakt"
    r")"
)
# Press-release tone is not a social angle. We're excited / announcement /
# unveiling / delighted to share is kill or changelog, never HN/GitHub/X.
# Pair of seminar brand voice: we announced as a brand is also silence.
# "announce" past tense stays with seminar; the noun and the costume die here.
PRESS_RELEASE_REASON = "press_release_tone"
PRESS_RELEASE_RE = re.compile(
    r"(?i)(?:"
    r"\bwe(?:['’]re|\s+are)\s+(?:excited|delighted|pleased|proud|thrilled|humbled)\b"
    r"|\b(?:excited|delighted|pleased|proud|thrilled|humbled)\s+to\s+"
    r"(?:announce|announcing|share|unveil|introduce|present)\b"
    r"|\bannouncements?\b"
    r"|\bannouncing\b"
    r"|\bunveil(?:s|ed|ing)?\b"
    r"|\bdelighted\s+to\s+share\b"
    r"|\bpress[- ]release\b"
    r"|\bnotk[ai]\s+prasow"
    r"|\bgame[- ]changer\b"
    r"|\brevolutionary\b"
    r"|\bdisrupt(?:ing|s)?\s+the\b"
    r")"
)
# A superlative is a slogan, not a story. Revolutionary / world's first /
# AI-powered without a tryable GitHub artifact is silence. Proof or nothing.
SUPERLATIVE_RE = re.compile(
    r"(?i)\b(?:revolutionary|world'?s\s+first|world-first|ai[- ]powered)\b"
)
# Mocking another project is silence. Naming a predecessor and the difference,
# or saying it is worth helping them, is fine. Dunking is not.
DUNK_PHRASE_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:dunk(?:s|ing)?(?:\s+on)?|roast(?:s|ing)?|laugh(?:s|ing)?\s+at)\b|"
    r"\b(?:their|that|the\s+other)\s+"
    r"(?:project|tool|repo|competitor|predecessor|clone|alternative)\s+"
    r"(?:is\s+)?(?:trash|garbage|a\s+joke|dead|a\s+dumpster\s+fire|a\s+clown|a\s+toy|sucks)\b|"
    r"\b(?:that|their)\s+(?:trash|garbage|joke|dumpster[- ]fire|clown|toy)\b|"
    r"\b(?:trash|garbage|joke|dead|dumpster[- ]fire|clown|toy)\s+"
    r"(?:of\s+a\s+)?(?:project|tool|repo|competitor|predecessor|clone)\b"
    r")"
)
DUNK_NAMED_RE = re.compile(
    r"(?i)\b(?P<name>[A-Za-z][\w.-]*)\s+"
    r"(?:sucks|is\s+trash|is\s+garbage|is\s+a\s+joke|is\s+dead|"
    r"is\s+a\s+dumpster\s+fire|is\s+a\s+clown(?:\s+project)?|"
    r"is\s+a\s+toy(?:\s+project)?)\b"
)
# A worse clone is not an angle. Someone already did this better /
# we reinvented X / gorszy klon is changelog or silence. Help them
# or name the difference. Pair of dunk: mockery is silence; a
# worse clone is also silence. Issue #43.
WORSE_CLONE_REASON = "worse_clone"
WORSE_CLONE_RE = re.compile(
    r"(?i)(?:"
    r"\balready\s+(?:did|built|shipped|made|solved)\s+(?:this|it|that)\s+better\b|"
    r"\bsomeone\s+already\s+(?:did|built|shipped|made)\b|"
    r"\balready\s+exists?\s+(?:and\s+is\s+)?better\b|"
    r"\breinvent(?:ed|ing|s)?\b|"
    r"\bznowu\s+wymy[sś]l|"
    r"\bkto[sś]\s+ju[zż]\s+to\s+zrobi[lł]\s+lepiej\b|"
    r"\bju[zż]\s+to\s+zrobi[lł]\s+lepiej\b|"
    r"\bworse\s+clones?\b|"
    r"\bgorsz(?:y|ego|a|e)\s+klon|"
    r"\bjust\s+(?:another|a)\s+(?:\w+\s+)?clones?\b|"
    r"\byet\s+another\s+(?:\w+\s+)?clones?\b|"
    r"\banother\s+clone\s+of\b"
    r")"
)
_CLONE_BETTER_IDEA_RE = re.compile(
    r"(?i)(?:"
    r"\bthe\s+difference\s+is\b|"
    r"\bunlike\b|"
    r"\bworth\s+helping\b|"
    r"\bhelp(?:ing)?\s+them\b|"
    r"\bbetter\s+idea\b|"
    r"\bcompared\s+to\b|"
    r"\bpom[oó]c\b|"
    r"\blepsz[yea]\s+pomys"
    r")"
)
# A reply under someone else's post. Kind names a parent; a social URL
# is a thread to sit under, not a ship. This is wave theft, not dunk.
PARENT_FACT_KINDS: frozenset[str] = frozenset(
    {"parent", "parent_post", "in_reply_to", "reply_to"}
)
REPLY_SHAPE_RE = re.compile(
    r"(?i)(?:"
    r"\breply(?:ing)?\s+(?:under|to|on)\b|"
    r"\bin[- ]reply[- ]to\b|"
    r"\bcomment(?:ing)?\s+(?:under|on)\s+(?:this\s+)?(?:post|thread|tweet|item)\b|"
    r"\bpod\s+postem\b|"
    r"\bodpowied[zź]\s+pod\b"
    r")"
)
_SHIP_URL_IN_TEXT_RE = re.compile(
    r"https://github\.com/"
    r"(?!(?:gist|orgs|settings|users)/)"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+"
    r"(?:/(?:pull/\d+|issues/\d+|releases(?:/tag/[A-Za-z0-9._~-]+|/\d+))?)",
    re.I,
)
_DUNK_SUBJECT_STOP = frozenset(
    {
        "this",
        "it",
        "that",
        "the",
        "our",
        "my",
        "your",
        "we",
        "they",
        "install",
        "timeout",
        "demo",
        "build",
        "test",
        "post",
        "feed",
        "spike",
        "launch",
        "thread",
        "format",
        "account",
        "tool",
        "repo",
        "project",
        "clone",
        "hn",
        "api",
        "cli",
        "ci",
        "readme",
        "github",
        "python",
    }
)
COMMIT_NOISE_RE = re.compile(
    r"(?i)^\s*(?:chore|typo|lint|ci|wip|bump\s+(?:version|deps)|fix(?:es)?\s+tests|merge\s+branch)\b"
)
# A window of merged PRs is changelog, not a clickable product.
MERGED_PR_FACT_RE = re.compile(r"(?i)^merged\s+pr\s+#\d+")
# A week of only bot bumps is not a story. dependabot / renovate /
# github-actions in the look window = cisza społeczna. Changelog wolno.
# Pair of no-noise (#64): chore/typo vs author is a bot. A human feat
# next to a bump stays; a stack of only bots does not launch.
BOT_AUTHOR_RE = re.compile(
    r"(?i)(?:"
    r"\bdependabot(?:\[bot\])?\b|"
    r"\brenovate(?:\[bot\])?\b|"
    r"\bgithub-actions(?:\[bot\])?\b|"
    r"\b(?:from|by|author)\s+(?:dependabot|renovate|github-actions)(?:\[bot\])?\b"
    r")"
)
# A version tag / bump-from-X-to-Y release is not a launch. Diffs of
# versions are changelog. Do not Show HN a lockfile bump dressed as v1.2.3.
VERSION_DIFF_RE = re.compile(
    r"(?i)(?:"
    r"\bbump(?:s|ed|ing)?\s+(?:\S+\s+)?from\s+\S+\s+to\s+\S+\b|"
    r"\b(?:chore|build|ci)(?:\([^)]*\))?:\s*bump\b|"
    r"\bbump(?:s|ed|ing)?\s+(?:version|versions|deps|dependencies|lockfile)\b|"
    r"^released\s+v?\d+(?:\.\d+){1,3}\s*$|"
    r"^tag\s+v?\d+(?:\.\d+){1,3}\s*$|"
    r"\bversion\s+diff\b|"
    r"\bdiff(?:s|y)?\s+(?:wersji|wersja|version)\b|"
    r"\btydzie[nń]\s+samych\s+bump"
    r")"
)
# A Monday look without a ship/tryable or a real public excerpt is
# cisza społeczna, not a recap. Changelog stays in the repo. Pair of
# no-noise (#64): "weekly update" is not history.
WEEKLY_UPDATE_RE = re.compile(
    r"(?i)\b(?:"
    r"weekly\s+update|"
    r"weekly\s+recap|"
    r"week\s+in\s+review|"
    r"this\s+week'?s\s+(?:update|recap)|"
    r"aktualizacja\s+tygodniowa|"
    r"podsumowanie\s+tygodnia|"
    r"tygodniow(?:y|e|a)\s+(?:update|recap|podsumowanie)"
    r")\b"
)
# Pair of #134 (a ranking dump is not an artifact) and #85 (a week of
# bumps is not a story). "N stars" / a star ranking without install,
# issue, or life after the spike is changelog, not a launch. Workshop
# scores usage, not a corpse on the wall.
DEAD_STAR_COUNT_REASON = "dead_star_count"
_STAR_TOTAL = r"(?:n|\d{1,3}(?:,\d{3})+|(?:\d+))(?:\.\d+)?[kmb]?"
DEAD_STAR_COUNT_RE = re.compile(
    r"(?i)(?:"
    rf"\b{_STAR_TOTAL}\s*[\u2605\u2b50]|"
    rf"\b{_STAR_TOTAL}\s*stars?\b|"
    rf"\b{_STAR_TOTAL}\s*gwiazd(?:ek|ki|ka|k\u0105)?\b|"
    r"\b(?:github\s+)?stars?\s*[:=]\s*(?:n|\d)|"
    r"\bstargazers?\s*[:=]\s*(?:n|\d)|"
    r"\b(?:total|lifetime|dead)\s+stars?\b|"
    r"\bdead\s+(?:\d+[kmb]?\s*)?[\u2605\u2b50]|"
    r"\bmartw[eyaie]+\s+gwiazd|"
    r"\bstar\s+ranking\b|"
    r"\branking\s+(?:gwiazdek|gwiazd|stars?)\b|"
    rf"\bwe\s+(?:have|hit|reached|crossed)\s+{_STAR_TOTAL}\s*stars?\b"
    r")"
)
# Install, a public issue, or life after the spike. A README that merely
# names an install is not usage — see _is_readme_install_fact.
WORKSHOP_LIFE_RE = re.compile(
    r"(?i)(?:"
    r"\binstall(?:s|ed|ation|ing)?\b|"
    r"\bpip\s+install\b|"
    r"\bnpm\s+i(?:nstall)?\b|"
    r"\buv\s+(?:add|run|tool|pip)\b|"
    r"\bquickstart\b|"
    r"\bissues?\b|"
    r"\bissue\s+#\d+|"
    r"\blife\s+after\s+(?:the\s+)?spike\b|"
    r"\bafter\s+the\s+spike\b|"
    r"\bżycia?\s+po\s+(?:the\s+)?spike\b"
    r")"
)
SUBREDDIT_RE = re.compile(r"\br/[A-Za-z0-9_]+\b")
CINEMA_MISSING_PACKAGE_REASON = "cinema_missing_package"
# Cinema package is title+thumb / tytuł+obietnica, one message in 0.5s.
# The word title, kind=package, a poster, or a fair 1-3s hook is not this.
# Pair of #36 (fair hook) and #31 (named sub): a label is not the pair.
CINEMA_PACKAGE_RE = re.compile(
    r"(?i)(?:"
    r"\btitle\s*(?:plus|\+|and|/)\s*thumb(?:nail)?(?:\s+in\s+0\s*[,.]\s*5s)?\b|"
    r"\btitle\s+and\s+promise\b|"
    r"\btytu[lł]\s*(?:\+|i|oraz)\s*(?:obietnic\w*|miniatur\w*|thumb(?:nail)?)\b|"
    r"\bone\s+message\s+in\s+0\s*[,.]\s*5s\b|"
    r"\b0\s*[,.]\s*5s\s+(?:title|package|thumb|pair)\b|"
    r"\bpackage\s+(?:first|in\s+0\s*[,.]\s*5s)\b"
    r")"
)
# Cafe: starter pack onboarduje, custom feed trzyma. Artifact alone (#35)
# is reach without retention. A GitHub pack / news feed / empty X feed
# is not this costume. Pair of #35 (artifact, not vibe).
BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON = "bluesky_vibe_without_artifact"
BLUESKY_PACK_WITHOUT_FEED_REASON = "bluesky_pack_without_feed"
CAFE_PACK_RE = re.compile(
    r"(?i)(?:"
    r"\bstarter[- ]packs?\b|"
    r"\bniche[- ]packs?\b|"
    r"\b(?:bluesky|bsky)[- ]packs?\b|"
    r"\bpacks?\s+onboard|"
    r"\b20\s*[\u2013-]\s*50\s+active\s+accounts\b|"
    r"\b(?:about\s+)?(?:20|30|40|50)\s+active\s+accounts\b|"
    r"bsky\.app/starter-pack(?:-short)?/"
    r")"
)
CAFE_FEED_RE = re.compile(
    r"(?i)(?:"
    r"\bcustom[- ]feeds?\b|"
    r"\b(?:bluesky|bsky)[- ]feeds?\b|"
    r"\bfeeds?\s+retain|"
    r"\b2\s*[\u2013-]\s*3\s+custom\s+feeds\b|"
    r"app\.bsky\.feed\.generator|"
    r"bsky\.app/profile/[^/\s]+/feed/"
    r")"
)
FAIR_MISSING_HOOK_REASON = "fair_missing_hook"
# Fair hook is 1-3s picture+voice+text. The word hook, kind=hook, a loop,
# or a cinema 0.5s title+thumb is not a swipe hook. Pair of #59 (loop).
FAIR_HOOK_RE = re.compile(
    r"(?i)(?:"
    r"\bhook\s+(?:in\s+)?1\s*[\u2013\-]\s*3s\b|"
    r"\b1\s*[\u2013\-]\s*3s\s+hook\b|"
    r"\bhaczyk\s+(?:w\s+)?1\s*[\u2013\-]\s*3s\b|"
    r"\bfirst\s+(?:1\s*[\u2013\-]\s*3|2|3)s\b|"
    r"\bfirst\s+(?:one|two|three)\s+seconds?\b|"
    r"\bpicture\s+(?:plus|\+|and)\s+voice\s+(?:plus|\+|and)\s+text\b|"
    r"\bobraz\s*(?:\+|i|oraz)\s*g[lł]os\s*(?:\+|i|oraz)\s*tekst\b"
    r")"
)
# Fair loop is last-frame-into-first / rewatch. A tick loop, event loop,
# or "one loop per state.db" is not a Shorts cut. Pair of #36 (hook) and
# #42 (one CTA): here the cut must loop, and loop+ask is silence.
FAIR_LOOP_RE = re.compile(
    r"(?i)(?:"
    r"^\s*loop\s*$|"
    r"\blast\s+frames?\s+(?:in)?to\s+(?:the\s+)?first\b|"
    r"\bfirst\s+frames?\s+(?:from|into)\s+(?:the\s+)?last\b|"
    r"\bostatni[aeą]\s+klatk|"
    r"\brewatch(?:es|ing)?\b|"
    r"\b(?:video|shorts?|fair|cut|clip)\s+loops?\b|"
    r"\bloops?\s+(?:the\s+)?(?:cut|clip|video|short|fair)\b|"
    r"%\s*viewed|"
    r"\bviewed\s*>\s*100"
    r")",
    re.M,
)
# Spine is loop or one ask, not both. Subscribe / link-in-bio / swipe-up
# on a looping cut is silence. "Follow the README" is product copy.
FAIR_CTA_RE = re.compile(
    r"(?i)(?:"
    r"\bcta\b|"
    r"\bcall[- ]to[- ]action\b|"
    r"\bsubscribe\b|"
    r"\bsubskryb|"
    r"\blink\s+in\s+bio\b|"
    r"\bswipe\s+up\b|"
    r"\bsmash\s+(?:that\s+)?like\b|"
    r"\bfollow\s+(?:for\s+more|and\s+subscribe)\b|"
    r"\bone\s+ask\b|"
    r"\bzapisz\s+si[eę]\b|"
    r"\bcomment\s+(?:below|for)\b|"
    r"\bthanks?\s+for\s+(?:watching|tuning\s+in|viewing)\b|"
    r"\bthank\s+you\s+for\s+(?:watching|tuning\s+in|viewing)\b|"
    r"\bdzi[eę]k\w*\s+za\s+ogl[aą]d|"
    r"\boutro(?:[- ]logo)?\b|"
    r"\blogo[- ](?:outro|intro|end)\b|"
    r"\bend[- ]?cards?\b"
    r")"
)
# #42: cinema/fair end does not announce the end. Thanks-for-watching,
# like-and-subscribe, and an outro-logo are silence. One CTA is not those.
CINEMA_ANNOUNCES_END_REASON = "cinema_announces_end"
CINEMA_END_RE = re.compile(
    r"(?i)(?:"
    r"\bthanks?\s+for\s+(?:watching|tuning\s+in|viewing)\b|"
    r"\bthank\s+you\s+for\s+(?:watching|tuning\s+in|viewing)\b|"
    r"\bdzi[eę]k\w*\s+za\s+ogl[aą]d|"
    r"\blike\s*(?:and|&|,)\s*subscribe\b|"
    r"\blajk\s*(?:i|&)\s*subskryb|"
    r"\boutro(?:[- ]logo)?\b|"
    r"\blogo[- ](?:outro|intro|end)\b|"
    r"\bend[- ]?cards?\b"
    r")"
)
# A quotation mark is not a testimonial. No excerpt with a URL → no quotes.
# "users love" without a sourced excerpt is invented opinion → silence.
FEEDBACK_EXCERPT_KINDS: frozenset[str] = frozenset(
    {"excerpt", "issue_comment", "pull_comment"}
)
# A quote is only legal from a public GitHub issue/PR comment.
# Slack / mail / DM is a private channel, not an excerpt source.
_PUBLIC_ISSUE_URL_RE = re.compile(
    r"^https://github\.com/"
    r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:issues|pull)/\d+"
    r"(?:#(?:issuecomment-\d+|discussion_r\d+|pullrequestreview-\d+|issue-\d+))?$",
    re.I,
)
PRIVATE_CHANNEL_HOSTS: frozenset[str] = frozenset(
    {
        "slack.com",
        "slack-gov.com",
        "mail.google.com",
        "gmail.com",
        "outlook.live.com",
        "outlook.office.com",
        "outlook.office365.com",
    }
)
# A private conversation is not an angle. Slack / mail / DM dump
# is silence, even anonymized. Channel, not token. A Slack
# integration or a support inbox stays; a zrzut does not.
PRIVATE_CONVERSATION_RE = re.compile(
    r"(?:"
    r"\bslack(?:s|'s)?\s+(?:dump|thread|screenshot|message|msg|dm|export|chat|zrzut)\b|"
    r"\b(?:from|in|on|via)\s+(?:a\s+|an\s+)?(?:anon(?:ymi|imi)[sz]\w*\s+)?slack\b|"
    r"\bslack(?:a|u|iem|owi)\b|"
    r"\bzrzut\s+slack|"
    r"\bmailto:|"
    r"^(?:from|fwd|forwarded(?:\s+message)?):|"
    r"\b(?:from|in|on|forwarded|fwd)\s+(?:an?\s+)?(?:e-?mail|mail)s?\b|"
    r"\b(?:e-?mail|mail)s?\s+(?:dump|thread|screenshot|zrzut|export)\b|"
    r"\bzrzut\s+(?:e-?mail|mail)|"
    r"\bdirect[- ]messages?\b|"
    r"\b(?:in|from|via|on)\s+(?:a\s+|an\s+)?(?:anon(?:ymi|imi)[sz]\w*\s+)?dms?\b|"
    r"\bdm(?:s|a|em|ie|ów)?\s+(?:dump|thread|screenshot|zrzut|from|od)\b|"
    r"\bzrzut\s+dm|"
    r"\bdm(?:a|em|ie|ów)\b|"
    r"\bprivate(?:ly)?\s+(?:conversation|message|chat|thread|dm|mail|email|slack)\b|"
    r"\bprivately\s+(?:messaged|emailed|said|wrote)\b|"
    r"\bprywatn(?:a|ej|ą|e|y)\s+(?:rozmow\w*|wiadomo[sś][cć]\w*|konwers\w*|czat\w*)\b"
    r")",
    re.I | re.M,
)
# A secret is not an angle. Token / password / key in a fact or body
# is silence. No almost-redacted social copy. env / bearer / sk- /
# ghp_ / keychain are enough; this is not a bag of every vault.
SECRET_REASON = "secret"
SECRET_RE = re.compile(
    r"(?:"
    r"\b(?:env|keychain):[^\s]+|"
    r"\bbearer\s+[A-Za-z0-9._\-+/=]{8,}|"
    r"\bsk-[A-Za-z0-9][A-Za-z0-9_-]{12,}|"
    r"\bgh[pousr]_[A-Za-z0-9_]+|"
    r"\bgithub_pat_[A-Za-z0-9_]+|"
    r"\b(?:authorization|token|password|passwd|secret|api[_-]?key)\s*[:=]\s*\S+"
    r")",
    re.I,
)
# A world take is not a product angle. Politics / culture / news of the day
# without a repo artifact is silence. We say what we build, not headlines.
WORLD_COMMENTARY_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:hot|spicy)\s+take\s+on\s+(?:the\s+)?(?:news|headline|headlines|election|elections|politics)\b|"
    r"\bhot[- ]take\s+on\s+(?:the\s+)?(?:news|headline|headlines|election|politics)\b|"
    r"\bmy\s+(?:hot\s+)?take\s+on\s+(?:the\s+)?(?:news|headline|headlines|election|elections|politics)\b|"
    r"\bthoughts\s+on\s+(?:the\s+)?(?:news|headline|headlines|election|elections)\b|"
    r"\bwhat\s+i\s+think\s+(?:about|of)\s+(?:the\s+)?(?:news|headline|headlines|election)\b|"
    r"\bnews\s+of\s+the\s+day\b|"
    r"\btoday'?s\s+(?:news|headlines?|politics)\b|"
    r"\bbreaking\s+news\b|"
    r"\bheadline\s+(?:of\s+the\s+day|today|reaction|take)\b|"
    r"\breact(?:ion|ing)?\s+to\s+(?:the\s+)?(?:news|headline|headlines|election)\b|"
    r"\bcurrent\s+events?\b|"
    r"\bworld\s+(?:news|politics|affairs|events?)\b|"
    r"\bgeopolitic"
    r"|\bpolitic(?:s|al)\s+(?:brief|take|hot[- ]?take|commentary|hotline|news)\b"
    r"|\bcultur(?:al|e)\s+(?:brief|take|hot[- ]?take|commentary|news|wars?)\b"
    r"|\bop[- ]?ed\b"
    r"|\beditorial\s+(?:on|about)\b"
    r"|\bkomentarz\s+(?:\u015bwiata|swiata|dnia|polityczn|kulturaln)"
    r"|\bbrief\s+polityczn"
    r"|\bbrief\s+kulturaln"
    r"|\bnews\s+dnia\b"
    r"|\bwiadomo[sś][cć]i\s+dnia\b"
    r"|\bpolityk(?:a|i|ę)\s+(?:dnia|\u015bwiata|swiata)\b"
    r"|\bkultura\s+dnia\b"
    r"|\bfelieton\b"
    r"|\b(?:komentarz|brief|take)\s+(?:o\s+)?wybor"
    r"|\belection\s+(?:day|night|results?)\b"
    r"|\bpresidential\s+election\b"
    r")"
)
# A hire / round / offsite is not a product angle. We say what we build,
# not that we are hiring, raising, or flying the team somewhere.
# A job-application form or a funding README stays; a tablica ogłoszeń does not.
HIRE_FUNDRAISE_RE = re.compile(
    r"(?i)(?:"
    r"\bwe(?:'re| are)\s+hiring\b"
    r"|\bhiring\s+(?:for|a|an|our)\b"
    r"|\bhiring\s+(?:engineers?|designers?|founders?|interns?|pms?)\b"
    r"|\bjoin\s+(?:our|the)\s+(?:team|company)\b"
    r"|\bopen\s+(?:role|roles|position|positions)\b"
    r"|\bjob\s+board\b"
    r"|\bcareers?\s+page\b"
    r"|\bnow\s+hiring\b"
    r"|\bfundrais(?:e|ing)\b"
    r"|\braising\s+(?:a\s+)?(?:seed|pre[- ]?seed|series\s+[a-d]|round)\b"
    r"|\bclosed\s+(?:our\s+)?(?:seed|pre[- ]?seed|series\s+[a-d]|round)\b"
    r"|\b(?:seed|pre[- ]?seed|series\s+[a-d])\s+round\b"
    r"|\bfunding\s+round\b"
    r"|\bannounc(?:e|ing|ed)\s+(?:our\s+)?(?:seed|pre[- ]?seed|series\s+[a-d]|round|fundraise)\b"
    r"|\boffsite\b"
    r"|\bteam\s+offsite\b"
    r"|\bcompany\s+offsite\b"
    r"|\brekrutacj"
    r"|\bszuka(?:my|m)\s+(?:osoby|ludzi|inżynier|engineer|founders?)"
    r"|\botwart[aey]\s+stanowisk"
    r"|\btablic[aąe]\s+ogłoszeń"
    r"|\brund[aeyę]\s+(?:seed|pre[- ]?seed|seria\s+[a-d]|finansow)"
    r"|\bzbi[oó]rka\s+(?:na\s+)?rund"
    r"|\bpozysk(?:aliśmy|ujemy)\s+(?:rund|finansow|seed)"
    r"|\boffsite\s+(?:zespołu|firmy|team)"
    r"|\bwyjazd\s+(?:zespołu|firmowy|integracyjn)"
    r")"
)
# Source-available is not OSS. BUSL / Commons Clause / fair code / SSPL
# plus the word "open source" is a license lie. Silence, not a badge.
# Saying source-available is allowed. Honest denial is not a sticker.
SOURCE_AVAILABLE_LICENSE_RE = re.compile(
    r"(?i)(?:"
    r"\bbusl\b"
    r"|\bbusiness\s+source\s+licen[cs]e\b"
    r"|\bcommons\s+clause\b"
    r"|\bfair[\s-]?code\b"
    r"|\bsspl\b"
    r"|\bserver[\s-]+side\s+public\s+licen[cs]e\b"
    r"|\bsource-available\b"
    r"|\bsource\s+available\s+licen[cs]e\b"
    r")"
)
OPEN_SOURCE_CLAIM_RE = re.compile(
    r"(?i)(?:"
    r"\bopen[\s-]?source\b"
    r"|\bopensource\b"
    r"|\bfoss\b"
    r"|\boss\b"
    r"|\botwart(?:e|y|ego|ym|ą)\s+(?:oprogramowanie|kod(?:zie)?)\b"
    r"|\bkod(?:u|zie)?\s+otwart"
    r")"
)
NEGATED_OPEN_SOURCE_RE = re.compile(
    r"(?i)(?:"
    r"\bnot\s+(?:an?\s+)?open[\s-]?source\b"
    r"|\bisn(?:['’])?t\s+open[\s-]?source\b"
    r"|\baren(?:['’])?t\s+open[\s-]?source\b"
    r"|\bnot\s+(?:an?\s+)?(?:foss|oss)\b"
    r"|\bnie\s+(?:jest\s+|są\s+|wołamy\s+|nazywamy\s+)?open[\s-]?source\b"
    r"|\bto\s+nie\s+(?:jest\s+)?(?:oss|foss|open[\s-]?source)\b"
    r")"
)
NEGATED_SOURCE_AVAILABLE_RE = re.compile(
    r"(?i)(?:"
    r"\bnot\s+(?:an?\s+)?(?:busl|sspl|commons\s+clause|fair[\s-]?code|source-available)\b"
    r"|\bisn(?:['’])?t\s+(?:busl|sspl|commons\s+clause|fair[\s-]?code|source-available)\b"
    r"|\bnie\s+(?:jest\s+)?(?:busl|sspl|commons\s+clause|fair[\s-]?code|source-available)\b"
    r"|\bto\s+nie\s+(?:jest\s+)?(?:busl|sspl|commons\s+clause|fair[\s-]?code|source-available)\b"
    r")"
)
# A LICENSE file is the only honest proof for an OSS sticker.
# "MIT License" in a sentence is not a file. Drop the word, or stay silent.
LICENSE_FILE_NAME_RE = re.compile(r"(?i)^licen[cs]e(?:\.(?:md|txt|rst))?$")
LICENSE_FILE_RE = re.compile(
    r"(?:"
    r"(?<![A-Za-z])LICEN[CS]E(?:\.(?:md|txt|rst))?(?![A-Za-z])"
    r"|(?i:\blicen[cs]e\.(?:md|txt|rst)\b)"
    r"|(?i:\blicen[cs]e\s+file\b)"
    r"|(?i:\bplik(?:u)?\s+licen[cs]e\b)"
    r")"
)
_LICENSE_FAMILY_BEFORE_RE = re.compile(
    r"(?i)(?:mit|apache(?:-?\d+(?:\.\d+)?)?|bsd|gpl|lgpl|agpl|isc|mpl|"
    r"mozilla(?:\s+public)?|business\s+source|server[\s-]+side\s+public|"
    r"public|proprietary|commercial|dual|open[\s-]?source|"
    r"source[\s-]?available)\s+$"
)
QUOTE_MARKS = frozenset('"\u201c\u201d\u201e\u00ab\u00bb')
_QUOTED_SPAN_RE = re.compile(
    r'"([^"]{1,240})"|\u201c([^\u201d]{1,240})\u201d|\u201e([^\u201d]{1,240})\u201d|\u00ab([^\u00bb]{1,240})\u00bb'
)
INVENTED_OPINION_RE = re.compile(
    r"(?i)\b(?:users|user|customers|customer|people|everyone|they)\s+love\b|"
    r"\bloved\s+by\s+(?:users|customers|everyone|people)\b"
)
# Asking for a gesture is silence. A question from feedback is fine.
# Agree? / like if / comment one word / ↓ are bait, not an angle.
ENGAGEMENT_BAIT_RE = re.compile(
    r"(?i)(?:"
    r"\bagree\s*\?|"
    r"\b(?:like|upvote|rt|retweet)\s+if\b|"
    r"\bcomment\s+(?:just\s+)?(?:one|a)\s+word\b|"
    r"[\u2193\u2b07\U0001F447\U0001F53D]"
    r")"
)
# A contest is not an angle. Giveaway / raffle / RT to win /
# nagroda za follow is silence. This is not a product.
CONTEST_RE = re.compile(
    r"(?i)(?:"
    r"\bgive[- ]?aways?\b|"
    r"\braffles?\b|"
    r"\bsweepstakes?\b|"
    r"\bcontests?\b|"
    r"\bkonkurs(?:y|ie|u|ów)?\b|"
    r"\blosowa[nń](?:ie|ia|iu)\b|"
    r"\b(?:rt|retweet|repost|follow|star)\s+to\s+win\b|"
    r"\bwin\s+(?:if\s+you\s+)?(?:rt|retweet|repost|follow|star)\b|"
    r"\bprize\s+(?:for|if\s+you)\s+(?:a\s+)?(?:follow|rt|retweet|like|star)\b|"
    r"\bnagrod[aąęy]\s+za\s+(?:follow|obserw|rt|retweet|lajk|gwiazdk)|"
    r"\benter\s+to\s+win\b|"
    r"\bwygraj\b|"
    r"\bdo\s+wygrania\b"
    r")"
)
# A poll is not an angle. Poll / this or that / quiz /
# ankieta is silence. This is not a product.
POLL_RE = re.compile(
    r"(?i)(?:"
    r"\bpolls?\b|"
    r"\bquiz(?:zes)?\b|"
    r"\bankiet(?:a|y|ę|ą|cie|om|ami|ach)?\b|"
    r"\bthis\s+or\s+that\b|"
    r"\bthis-or-that\b|"
    r"\bto\s+czy\s+tamto\b|"
    r"\bto\s+albo\s+tamto\b"
    r")"
)
# A prompt dump or "I asked ChatGPT" is not an angle.
# Dump of a conversation with a model / as an AI = silence.
# HoM is not a model in the frame. Neighbor of #117: slogan vs kadr.
MODEL_HOSTS: frozenset[str] = frozenset(
    {
        "chat.openai.com",
        "chatgpt.com",
        "claude.ai",
        "gemini.google.com",
        "bard.google.com",
        "perplexity.ai",
        "copilot.microsoft.com",
        "grok.x.ai",
        "grok.com",
        "chat.mistral.ai",
    }
)
_MODEL_NAME = (
    r"(?:chat\s*gpt|chatgpt|gpt-?\d(?:\.\d+)?[a-z]?|gpt|"
    r"claude|gemini|copilot|grok|bard|perplexity|llm)"
)
_ASKED_MODEL = r"(?:(?:an?|the)\s+)?(?:" + _MODEL_NAME + r"|model)"
MODEL_IN_FRAME_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:i|we|they)\s+asked\s+" + _ASKED_MODEL + r"\b"
    r"|\basked\s+" + _ASKED_MODEL + r"\b"
    r"|\b(?:i|we)\s+(?:prompted|used)\s+" + _ASKED_MODEL + r"\b"
    r"|\bas\s+an?\s+ai(?:\s+language\s+model)?\b(?![- ]powered)"
    r"|\bas\s+a\s+(?:large\s+)?language\s+model\b"
    r"|\bas\s+(?:chat\s*gpt|chatgpt)\b"
    r"|\bi(?:['’]m|\s+am)\s+an?\s+ai\b(?![- ]powered)"
    r"|\bi(?:['’]m|\s+am)\s+a\s+(?:large\s+)?language\s+model\b"
    r"|\bi(?:['’]m|\s+am)\s+" + _MODEL_NAME + r"\b"
    r"|\b" + _MODEL_NAME + r"\s+(?:said|wrote|replied|answered|thinks|suggests|told)\b"
    r"|\baccording\s+to\s+" + _MODEL_NAME + r"\b"
    r"|\b(?:here'?s|here\s+is)\s+(?:the\s+|my\s+)?prompt\b"
    r"|\b(?:my|the|our)\s+" + _MODEL_NAME + r"\s+prompt\b"
    r"|\b" + _MODEL_NAME + r"\s+prompt\b"
    r"|\bprompt\s+(?:i\s+(?:used|gave|wrote)|dump|i\s+asked)\b"
    r"|(?:^|(?<=\n))\s*prompt\s*:"
    r"|\b" + _MODEL_NAME + r"\s+conversation\b"
    r"|\bconversation\s+with\s+(?:the\s+model|" + _MODEL_NAME + r")\b"
    r"|\bdump\s+(?:of\s+)?(?:the\s+)?(?:model|" + _MODEL_NAME + r")\b"
    r"|\byou\s+are\s+a\s+helpful\s+assistant\b"
    r"|\bsystem\s*:\s*you\s+are\b"
    r"|\bzapyt\w*\s+(?:chatgpt|(?:an?\s+|the\s+)?(?:model(?:u|em)?|llm))\b"
    r"|\bużył(?:em|am)\s+chatgpt\b"
    r"|\bpaste\s+(?:this\s+|the\s+|my\s+)?prompt\s+into\s+" + _MODEL_NAME + r"\b"
    r"|\brozmow[ayeę]\s+z\s+(?:chatgpt|claude|gemini|modelem)\b"
    r"|\bzrzut\s+rozmowy\s+z\s+modelem\b"
    r"|\bjako\s+ai\b(?![- ]powered)"
    r"|\bjako\s+model\s+j[eę]zykow"
    r"|\bwklei(?:łem|łam|am)\s+prompt\b"
    r"|\boto\s+(?:mój\s+)?prompt\b"
    r"|\bgenerated\s+by\s+(?:an?\s+ai|" + _MODEL_NAME + r")\b"
    r"|\bwritten\s+by\s+(?:an?\s+ai|" + _MODEL_NAME + r")\b"
    r")"
)
MODEL_DUMP_RE = re.compile(
    r"(?i)(?:^|\n)\s*(?:user|human)\s*:\s+\S.+\n\s*(?:assistant|chatgpt|claude|gemini|gpt)\s*:"
)
# A 1/n serial is not an angle. Numbering / thread / storm is silence.
# One post, not a serial. OS thread-safe / pthread is not a format.
THREAD_NUMBER_RE = re.compile(
    r"(?:"
    r"^\s*\d+\s*/|"
    r"\b\d+\s*/\s*n\b|"
    r"\b\d+\s*/\s*\d+\b"
    r")",
    re.I | re.M,
)
_ALWAYS_ON_RE = re.compile(r"(?i)\b24\s*/\s*7\b")
THREAD_WORD_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:tweet[- ]?)?storms?\b|"
    r"\bthreads?\b|"
    r"\bw[aą]t(?:ek|ku|kiem|kowi|ki|k[oó]w|kach|kom|kami)\b|"
    r"\U0001F9F5"
    r")"
)
_THREAD_TECH_RE = re.compile(
    r"(?i)(?:"
    r"\bpthreads?\b|"
    r"\bmultithread(?:ed|ing)?\b|"
    r"\bthread(?:s|ing|ed)?[- ](?:safe|safety|pool|local|sanitizer)\b|"
    r"\b(?:main|worker|os|background|ui|event|io|green|native|daemon)\s+threads?\b"
    r")"
)
# A wall of hashtags is not a costume. More than one-two tags, or a
# trailing tag tail, is silence. Court and agora are not an SEO catalog.
HASHTAG_RE = re.compile(r"(?<![A-Za-z0-9/])#([A-Za-z][A-Za-z0-9_]{1,39})\b")
_HASHTAG_TAIL_RE = re.compile(
    r"(?:^|\s)(?:#[A-Za-z][A-Za-z0-9_]{1,39}[\s,.;:!?]*)+$"
)
MAX_HASHTAGS = 2
# @login in a draft is a summon. Strip or silence. URLs and emails are not pings.
MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9/])@([A-Za-z0-9][A-Za-z0-9_-]{0,38})\b"
)
_STRIP_MENTION_RE = re.compile(
    r"(?<![A-Za-z0-9/])@([A-Za-z0-9][A-Za-z0-9_-]{0,38})\b\s*[:\-\u2013\u2014,.!?]*\s*"
)
# A number in the costume must already be a fact. Dress does not add
# "10x", "1M users", or benchmarks. No number in facts → no number in body.
METRIC_TOKEN_RE = re.compile(
    r"(?i)(?<![A-Za-z0-9])"
    r"(?:\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?)"
    r"(?:[kmbx×%])?"
    r"(?:\s+users)?"
    r"(?![A-Za-z0-9])"
)
BENCHMARK_WORD_RE = re.compile(r"(?i)\bbenchmarks?\b")
_URL_IN_TEXT_RE = re.compile(r"https?://\S+", re.I)

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
    require_loop: bool = False
    require_cafe_pack: bool = False
    require_cafe_feed: bool = False
    forbid_cta_with_loop: bool = False
    forbid_ship_claim: bool = False
    min_facts: int = 0
    allowed_story_kinds: frozenset[StoryKind] | None = None
    mismatch_verdict: Verdict = Verdict.KILL


ARENA_GATES: dict[ArenaId, ArenaGate] = {
    ArenaId.DISCORD: ArenaGate(
        reason="discord_pre_pmf",
        min_facts=2,
        allowed_story_kinds=frozenset({StoryKind.MAJOR}),
    ),
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
        forbid_ship_claim=True,
        min_facts=2,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.DECISION, StoryKind.FAILURE}
        ),
    ),
    ArenaId.YOUTUBE: ArenaGate(
        reason=CINEMA_MISSING_PACKAGE_REASON,
        require_package=True,
        allowed_story_kinds=frozenset(
            {StoryKind.MAJOR, StoryKind.HARD_ISSUE, StoryKind.FAILURE}
        ),
    ),
    ArenaId.SHORTS: ArenaGate(
        reason=FAIR_MISSING_HOOK_REASON,
        require_hook=True,
        require_loop=True,
        forbid_cta_with_loop=True,
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
        reason=BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON,
        require_ship_artifact=True,
        require_cafe_pack=True,
        require_cafe_feed=True,
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


def _normalized_host(host: str | None) -> str | None:
    value = (host or "").strip().rstrip(".").lower()
    if value.startswith("www."):
        value = value[4:]
    return value or None


def _host_allowed(host: str | None, names: frozenset[str]) -> bool:
    value = _normalized_host(host)
    if not value:
        return False
    return any(value == name or value.endswith("." + name) for name in names)


def _has_utm_farm_query(query: str) -> bool:
    if not query:
        return False
    keys = {key.lower() for key in parse_qs(query, keep_blank_values=True)}
    return any(key in _UTM_QUERY_KEYS or key.startswith("utm_") for key in keys)


def is_shortener_url(url: str | None) -> bool:
    """True for a known shortener host. A skracacz is not a tryable demo."""
    return _host_in(url, SHORTENER_HOSTS)


def is_tryable_artifact_url(url: str | None) -> bool:
    """True only for https on an already-allowlisted host.

    http://, javascript:, data:, and file: are silence, not almost-clickable.
    A shortener, a UTM-farm, or “kliknij tu” is silence even on github.com.
    """
    if not url or not isinstance(url, str):
        return False
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False
    if parsed.username is not None or parsed.password is not None:
        return False
    if _host_allowed(parsed.hostname, SHORTENER_HOSTS):
        return False
    if _has_utm_farm_query(parsed.query) or CLICK_HERE_RE.search(raw):
        return False
    return _host_allowed(parsed.hostname, TRYABLE_ARTIFACT_HOSTS)


def _http_host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return _normalized_host(parsed.hostname)


def _host_in(url: str | None, names: frozenset[str]) -> bool:
    return _host_allowed(_http_host(url), names)


def is_video_host_url(url: str | None) -> bool:
    """True for a YouTube/Vimeo/Loom URL. A film is not a tryable demo."""
    return _host_in(url, VIDEO_HOSTS)


def is_store_host_url(url: str | None) -> bool:
    """True for an App Store / Play / TestFlight URL. A store is not a tryable demo."""
    return _host_in(url, STORE_HOSTS)


def is_blog_host_url(url: str | None) -> bool:
    """True for a Medium / Substack / dev.to / hashnode URL. A blog is not a tryable demo."""
    return _host_in(url, BLOG_HOSTS)


def is_launch_host_url(url: str | None) -> bool:
    """True for a Product Hunt / BetaList URL. A launch board is not a tryable demo."""
    return _host_in(url, LAUNCH_HOSTS)


def is_news_host_url(url: str | None) -> bool:
    """True for a newspaper / TV / wire host. A headline is not a tryable demo."""
    return _host_in(url, NEWS_HOSTS)


def is_model_host_url(url: str | None) -> bool:
    """True for a ChatGPT / Claude / Gemini chat host. A model chat is not a product."""
    return _host_in(url, MODEL_HOSTS)


def news_urls_only(urls: tuple[str, ...] | list[str]) -> bool:
    """True when every artifact URL is a news clipping and none is a repo."""
    cleaned = [url.strip() for url in urls if url and url.strip()]
    if not cleaned:
        return False
    if any(is_ship_artifact_url(url) for url in cleaned):
        return False
    return all(is_news_host_url(url) for url in cleaned)


def is_deck_host_url(url: str | None) -> bool:
    """True for Notion / Speaker Deck / Slideshare / Pitch / Google Slides. A deck is not a tryable demo."""
    if _host_in(url, DECK_HOSTS):
        return True
    if not url:
        return False
    return bool(_GOOGLE_SLIDES_RE.fullmatch(url.strip().rstrip("/")))


def deck_urls_only(urls: tuple[str, ...] | list[str]) -> bool:
    """True when every artifact URL is a deck and none is a repo."""
    cleaned = [url.strip() for url in urls if url and url.strip()]
    if not cleaned:
        return False
    if any(is_ship_artifact_url(url) for url in cleaned):
        return False
    return all(is_deck_host_url(url) for url in cleaned)


def is_linktree_host_url(url: str | None) -> bool:
    """True for Linktree / Carrd / bio.site. A link board is not a tryable demo."""
    return _host_in(url, LINKTREE_HOSTS)


def linktree_urls_only(urls: tuple[str, ...] | list[str]) -> bool:
    """True when every artifact URL is a link board and none is a repo."""
    cleaned = [url.strip() for url in urls if url and url.strip()]
    if not cleaned:
        return False
    if any(is_ship_artifact_url(url) for url in cleaned):
        return False
    return all(is_linktree_host_url(url) for url in cleaned)


def is_ranking_host_url(url: str | None) -> bool:
    """True for HN / star-history / shields / stargazers. A chart is not a tryable demo."""
    if _host_in(url, RANKING_HOSTS):
        return True
    if not url:
        return False
    return bool(_GITHUB_VANITY_RE.fullmatch(url.strip().rstrip("/")))


def ranking_urls_only(urls: tuple[str, ...] | list[str]) -> bool:
    """True when every artifact URL is a ranking dump and none is a repo."""
    cleaned = [url.strip() for url in urls if url and url.strip()]
    if not cleaned:
        return False
    if any(is_ship_artifact_url(url) for url in cleaned):
        return False
    return all(is_ranking_host_url(url) for url in cleaned)


def looks_like_store_pitch(text: str) -> bool:
    return bool(STORE_PITCH_RE.search(text))


def looks_like_launch_pitch(text: str) -> bool:
    return bool(LAUNCH_PITCH_RE.search(text))


def looks_like_listicle_title(text: str) -> bool:
    """True for a listicle / clickbait / trailing-bang title. Not a Show HN."""
    title = text.strip()
    if title.lower().startswith("show hn:"):
        title = title.split(":", 1)[1].strip()
    if not title:
        return False
    if title.endswith("!"):
        return True
    return bool(LISTICLE_TITLE_RE.search(title))


def looks_like_shouty_title(text: str) -> bool:
    """True when the whole title is uppercase. One or two acronym words are allowed."""
    title = text.strip()
    if title.lower().startswith("show hn:"):
        title = title.split(":", 1)[1].strip()
    if not title:
        return False
    words = [word for word in title.split() if any(ch.isalpha() for ch in word)]
    if len(words) <= 2:
        return False
    letters = [ch for ch in title if ch.isalpha()]
    if not letters:
        return False
    return all(ch.isupper() for ch in letters)


def looks_like_emoji_title(text: str) -> bool:
    """True when the title wears emoji. Seminar and workshop are not a fair."""
    title = text.strip()
    if title.lower().startswith("show hn:"):
        title = title.split(":", 1)[1].strip()
    return bool(title and _EMOJI_RE.search(title))


# Costume language. Seminar/workshop dress English (OSS seminar). Letter/court
# take language from the profile (audience). A Polish Show HN or an English
# letter to a Polish audience is silence on that channel.
_POLISH_MARKERS = (
    "ą", "ć", "ę", "ł", "ń", "ó", "ś", "ź", "ż",
    "Ą", "Ć", "Ę", "Ł", "Ń", "Ó", "Ś", "Ź", "Ż",
)
_POLISH_WORD_RE = re.compile(
    r"(?i)(?<![A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])"
    r"(?:"
    r"i|oraz|orazże|ale|lecz|jednak|ponieważ|dlatego|któr(?:y|a|e|ych|emu|ym)|"
    r"jest|są|był|była|było|będzie|może|można|trzeba|nie|tak|"
    r"dla|od|do|na|po|przy|przez|bez|nad|pod|za|ze|we|ku|"
    r"ten|ta|to|te|tego|tej|tych|tym|tymi|"
    r"jak|gdy|kiedy|jeśli|jeżeli|że|czy|żeby|"
    r"lokaln(?:y|a|e|ych)|kąt|kostium|cisza|brief|szkic|"
    r"wydaliśmy|wystartowaliśmy|uruchomiliśmy|"
    r"działa|działają|działać|"
    r"projekt|narzędzie|wersja|"
    r"możliwe|nowy|nowa|nowe|"
    r"polski|polska|polskie|polską|polskiego"
    r")"
    r"(?![A-Za-zĄĆĘŁŃÓŚŹŻąćęłńóśźż])"
)
_ENGLISH_WORD_RE = re.compile(
    r"(?i)(?<![A-Za-z])"
    r"(?:"
    r"the|and|or|but|with|from|this|that|these|those|"
    r"is|are|was|were|be|been|being|"
    r"for|not|you|your|our|we|they|their|"
    r"can|will|just|into|about|over|under|"
    r"local|tick|scores|briefs|emits|draft|"
    r"shipped|launched|working|quickstart|"
    r"strangers|click|run|demo|today"
    r")"
    r"(?![A-Za-z])"
)
_POLISH_AUDIENCE_RE = re.compile(
    r"(?i)\b(?:"
    r"pl|pol|polski|polska|polskie|polską|polskiego|"
    r"poland|polish|pl-pl|pl_pl"
    r")\b"
)
_ENGLISH_AUDIENCE_RE = re.compile(
    r"(?i)\b(?:"
    r"en|eng|english|en-us|en_us|en-gb|en_gb|"
    r"builders?|customers?|developers?|devs?|"
    r"users?|founders?|engineers?"
    r")\b"
)
ENGLISH_COSTUME_ARENAS: frozenset[ArenaId] = frozenset({ArenaId.HN, ArenaId.GITHUB})
PROFILE_LANGUAGE_ARENAS: frozenset[ArenaId] = frozenset(
    {ArenaId.LINKEDIN, ArenaId.NEWSLETTER}
)


def _letters_only(text: str) -> str:
    return "".join(ch for ch in text if ch.isalpha())


def _has_polish_marker(text: str) -> bool:
    return any(mark in text for mark in _POLISH_MARKERS)


def looks_like_polish(text: str) -> bool:
    """True when copy wears Polish letters or Polish function words."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    if not _letters_only(cleaned):
        return False
    if _has_polish_marker(cleaned):
        return True
    return bool(_POLISH_WORD_RE.search(cleaned))


def looks_like_english(text: str) -> bool:
    """True when copy is Latin letters without Polish dress."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    letters = _letters_only(cleaned)
    if not letters:
        return False
    if looks_like_polish(cleaned):
        return False
    if any(ord(ch) > 127 for ch in letters):
        return False
    return True


def profile_language(audience: str | None, voice: str | None = None) -> str | None:
    """pl or en from the profile. Ambiguous audience is silence, not a guess."""
    blob = " ".join(part for part in (audience, voice) if part)
    if not blob.strip():
        return None
    polish = bool(_POLISH_AUDIENCE_RE.search(blob) or looks_like_polish(blob))
    english = bool(_ENGLISH_AUDIENCE_RE.search(blob) or looks_like_english(blob))
    if polish and not english:
        return "pl"
    if english and not polish:
        return "en"
    return None


def costume_language_reason(
    arena: ArenaId | str | None,
    text: str,
    *,
    audience: str | None = None,
    voice: str | None = None,
) -> str | None:
    """Silence when the costume wears the wrong language.

    Show HN / GitHub dress English. Letter / court take the profile language.
    Missing profile language on letter/court is silence, not a guess.
    """
    if arena is None:
        return None
    key = arena if isinstance(arena, ArenaId) else ArenaId(arena)
    cleaned = text or ""
    if not _letters_only(_URL_IN_TEXT_RE.sub(" ", cleaned)):
        return None
    if key in ENGLISH_COSTUME_ARENAS:
        if looks_like_english(cleaned) and not looks_like_polish(cleaned):
            return None
        return "costume_language"
    if key in PROFILE_LANGUAGE_ARENAS:
        wanted = profile_language(audience, voice)
        if wanted is None:
            return "costume_language"
        if wanted == "pl":
            return None if looks_like_polish(cleaned) else "costume_language"
        if wanted == "en":
            return None if looks_like_english(cleaned) else "costume_language"
        return "costume_language"
    return None


# Hard arena limits. Overflow is silence, not a mid-word clip.
X_REPLY_LIMIT = 280
LINKEDIN_FOLD = 210
# One HN line, not a blog. Prefix + title stay on a single screen line.
HN_TITLE_LIMIT = 72
HN_TITLE_PREFIX = "Show HN: "


def _one_line(text: str) -> str:
    return " ".join(text.split())


def show_hn_title_text(text: str) -> str:
    """Bare title after an optional Show HN: prefix. Empty is silence."""
    title = _one_line(text)
    if title.lower().startswith("show hn:"):
        title = title.split(":", 1)[1].strip()
    return title


def looks_like_hn_title_overflow(text: str) -> bool:
    """True when a Show HN title is longer than one line or a blog."""
    title = show_hn_title_text(text)
    if not title:
        return True
    if "\n" in text.strip():
        return True
    return len(f"{HN_TITLE_PREFIX}{title}") > HN_TITLE_LIMIT


# Show HN writes as a person. Backstory and nick come from
# BrandProfile.maintainer, first person. "We at Product announced"
# is silence on seminar. Pair of #32/#51 (dress HN as a human).
SEMINAR_BRAND_VOICE_REASON = "seminar_brand_voice"
SEMINAR_BRAND_VOICE_RE = re.compile(
    r"(?i)(?:"
    r"\bwe\s+at\s+(?:the\s+)?(?:company|product|brand|startup|[A-Za-z][\w.-]{1,40})\s+announced\b|"
    r"\bwe\s+announced\b|"
    r"\bour\s+(?:team|company|product|brand)\s+announced\b|"
    r"\bthe\s+company\s+announced\b|"
    r"\bnasz(?:a|ej)?\s+(?:zesp[oó]ł|marka|produkt)\b|"
    r"\bogłaszamy\b"
    r")"
)
SEMINAR_FIRST_PERSON_RE = re.compile(
    r"(?i)(?:"
    r"\bI\s+(?:built|wrote|made|shipped|struggled|wanted|needed|ran|use|used)\b|"
    r"\bI['’]m\b|"
    r"\bI\s+am\b"
    r")"
)


def looks_like_brand_voice(text: str) -> bool:
    """True for We at Product / we announced. Seminar is a person, not a brand."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(SEMINAR_BRAND_VOICE_RE.search(cleaned))


def looks_like_seminar_first_person(text: str) -> bool:
    """True for I built / I struggled. Show HN backstory is first person."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(SEMINAR_FIRST_PERSON_RE.search(cleaned))


def seminar_reason(text: str) -> str | None:
    """Silence when seminar would speak as a brand, not the maintainer."""
    if looks_like_brand_voice(text):
        return SEMINAR_BRAND_VOICE_REASON
    return None


def looks_like_x_overflow(text: str, url: str | None = None) -> bool:
    """True when the agora body will not fit in 280. URL sits on its own line."""
    hook = _one_line(text)
    if not hook:
        return True
    proof = (url or "").strip()
    if proof:
        return len(hook) + 1 + len(proof) > X_REPLY_LIMIT
    return len(hook) > X_REPLY_LIMIT


def looks_like_linkedin_fold_overflow(text: str) -> bool:
    """True when the court insight will not win the ~210-char fold."""
    insight = _one_line(text)
    if not insight:
        return True
    return len(insight) > LINKEDIN_FOLD


# Court is not a launch channel. claims_ship / Show HN / "just shipped"
# energy is github/hn. LinkedIn without insight from the work is silence.
# Pair of #33 (fold without pitch) and #26 (launch window): here the
# channel never carries launch, also outside the window.
COURT_NOT_A_LAUNCH_REASON = "court_not_a_launch"
COURT_LAUNCH_RE = re.compile(
    r"(?i)(?:"
    r"\bshow\s+hn\b|"
    r"\b(?:we|i)\s+(?:just\s+)?(?:shipped|launched|released|announce|announcing|introducing)\b|"
    r"\bjust\s+(?:shipped|launched|released)\b|"
    r"\bwłaśnie\s+(?:wypuścili|wydali|uruchomili)|"
    r"\bwypuściliśmy\b|"
    r"\bwydaliśmy\b"
    r")"
)
COURT_PITCH_RE = re.compile(
    r"(?i)^\s*(?:(?:we|i)\s+)?(?:just\s+)?(?:shipped|launched|announcing|introducing)\b|"
    r"^\s*(?:excited to|proud to|please to|try (?:it|this|ours?)\b|sign up|click here)"
)


def looks_like_court_launch(text: str) -> bool:
    """True for Show HN / just-shipped energy. Court is not a launch channel."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(COURT_LAUNCH_RE.search(cleaned))


def has_court_insight(text: str) -> bool:
    """True when a non-pitch, non-URL line can win the court fold."""
    for line in (text or "").splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if _URL_IN_TEXT_RE.search(cleaned):
            continue
        if looks_like_court_launch(cleaned) or COURT_PITCH_RE.search(cleaned):
            continue
        if looks_like_linkedin_fold_overflow(cleaned):
            continue
        if len(cleaned) >= MIN_FACT_CHARS:
            return True
    return False


def court_reason(text: str, *, claims_ship: bool = False) -> str | None:
    """Silence when court would carry launch, or has no insight from the work."""
    if claims_ship or looks_like_court_launch(text):
        return COURT_NOT_A_LAUNCH_REASON
    if not has_court_insight(text):
        return "court_not_ready"
    return None


# Empty tavern is silence. A public invite without the help/show/contribute/
# lounge split, or without ~10 builders, is not a costume. Pair of #38
# (decisions stay on GitHub) and #52 (durable Q&A is Discussions).
EMPTY_TAVERN_REASON = "discord_pre_pmf"
TAVERN_INTENT_RE = re.compile(
    r"(?i)(?="
    r".*\bhelp\b)(?=.*\bshow\b)(?=.*\bcontribute\b)(?=.*\blounge\b)"
)
TAVERN_SEED_RE = re.compile(
    r"(?i)(?:"
    r"~?\s*10\s+builders?|"
    r"about\s+10\s+builders?|"
    r"seed(?:ed)?\s+(?:about\s+)?10\s+builders?|"
    r"ok\.\s*10\s+builder\u00f3w|"
    r"oko\u0142o\s+10\s+builder"
    r")"
)
TAVERN_INVITE_RE = re.compile(
    r"(?i)(?:"
    r"\b(?:public\s+)?invite\b|"
    r"\bzaproszen|"
    r"discord\.gg/|"
    r"discord\.com/invite/"
    r")"
)


def looks_like_tavern_invite(text: str) -> bool:
    """True for a public Discord invite. Empty tavern is not a costume."""
    cleaned = text or ""
    return bool(TAVERN_INVITE_RE.search(cleaned))


def has_tavern_intent_split(text: str) -> bool:
    """True when help / show / contribute / lounge are all named."""
    return bool(TAVERN_INTENT_RE.search(text or ""))


def has_tavern_seed(text: str) -> bool:
    """True when ~10 builders are already in the room."""
    return bool(TAVERN_SEED_RE.search(text or ""))


def tavern_reason(text: str) -> str | None:
    """Silence when Discord would invite into an empty tavern."""
    if not has_tavern_intent_split(text) or not has_tavern_seed(text):
        return EMPTY_TAVERN_REASON
    return None


def has_cafe_pack(text: str) -> bool:
    """True when facts name a Bluesky starter / niche pack."""
    return bool(CAFE_PACK_RE.search(text or ""))


def has_cafe_feed(text: str) -> bool:
    """True when facts name a Bluesky custom feed."""
    return bool(CAFE_FEED_RE.search(text or ""))


def cafe_reason(text: str) -> str | None:
    """Silence when Bluesky would post without pack and feed. Artifact is not enough."""
    if not has_cafe_pack(text) or not has_cafe_feed(text):
        return BLUESKY_PACK_WITHOUT_FEED_REASON
    return None


def cafe_artifact_reason(
    urls: tuple[str, ...] | list[str] = (),
    *,
    extra: str = "",
) -> str | None:
    """Silence when Bluesky would post without a repo/demo/release URL. Vibe is not enough."""
    found = [str(url).strip() for url in urls if url and str(url).strip()]
    if any(is_ship_artifact_url(url) for url in found):
        return None
    for match in _URL_IN_TEXT_RE.finditer(extra or ""):
        if is_ship_artifact_url(match.group(0).rstrip(".,);")):
            return None
    return BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON


# Letter gives first, then maybe asks. Subscribe / our launch without a
# concrete gift for the reader is silence. Recs are adjacent (sąsiad),
# not a crush. Pair of #30/#51 (owned list, dress letter).
LETTER_ASK_WITHOUT_GIFT_REASON = "letter_ask_without_gift"
LETTER_ASK_RE = re.compile(
    r"(?i)(?:"
    r"\bsubscribe\b|"
    r"\bsubskryb|"
    r"\bjoin\s+(?:the|our)\s+(?:list|newsletter|letter)\b|"
    r"\bsign\s+up\s+(?:for|to)\b|"
    r"\bour\s+launch\b|"
    r"\bjoin\s+(?:the|our)\s+launch\b|"
    r"\bnasz(?:a|ej)?\s+launch\b|"
    r"\bzapisz\s+si[eę]\b"
    r")"
)
LETTER_CRUSH_RE = re.compile(
    r"(?i)(?:"
    r"\bcrush(?:es|ing)?\s+(?:the\s+)?(?:competitor|competition)s?\b|"
    r"\bkill(?:s|ing)?\s+(?:the\s+)?(?:competitor|competition)s?\b|"
    r"\bdestroy(?:s|ing)?\s+(?:the\s+)?(?:competitor|competition)s?\b|"
    r"\beat\s+(?:their|the)\s+lunch\b|"
    r"\bzdus\w*\s+konkurenc|"
    r"\bkonkurenc\w*\s+do\s+zdusz"
    r")"
)


def looks_like_letter_ask(text: str) -> bool:
    """True for subscribe / our launch. An ask is not a gift."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(LETTER_ASK_RE.search(cleaned))


def looks_like_letter_crush(text: str) -> bool:
    """True for crush-the-competitor recs. A neighbor is not a kill."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(LETTER_CRUSH_RE.search(cleaned))


def has_letter_gift(text: str) -> bool:
    """True when a non-ask, non-crush line is concrete for the reader."""
    for line in (text or "").splitlines():
        cleaned = _URL_IN_TEXT_RE.sub(" ", line).strip()
        if not cleaned:
            continue
        if looks_like_letter_ask(cleaned) or looks_like_letter_crush(cleaned):
            continue
        if len(cleaned) >= MIN_FACT_CHARS:
            return True
    return False


# Letter dresses from BrandProfile (display_name / maintainer), not "we" /
# "the team". A given name without a surname is silence on the letter.
# Pair of #30/#45 (owned list, named editor).
LETTER_WITHOUT_SURNAME_REASON = "letter_without_surname"
LETTER_TEAM_VOICE_RE = re.compile(
    r"(?i)(?:"
    r"\bwe\b|"
    r"\bour\s+team\b|"
    r"\bthe\s+team\b|"
    r"\bzespo(?:l|łu|łem|le|[łl])\b|"
    r"\bmy\s+(?:w|z|od)\b"
    r")"
)
# Two capitalized name tokens: letters, optional hyphen/apostrophe inside.
# "Mikolaj" / a GitHub login is not a surname. "Mikolaj Nowak" is.
# "From Mikolaj" / "My App" are not a named editor.
_LETTER_NAME_TOKEN = (
    r"[A-ZÀ-ÖØ-ÞĄĆĘŁŃÓŚŹŻ][A-Za-zÀ-ÖØ-öø-ÿĄĆĘŁŃÓŚŹŻąćęłńóśźż''-]{1,40}"
)
LETTER_SURNAME_RE = re.compile(rf"\b({_LETTER_NAME_TOKEN})\s+({_LETTER_NAME_TOKEN})\b")
_LETTER_NAME_STOP = frozenset(
    {
        "from",
        "signed",
        "dear",
        "hello",
        "hi",
        "best",
        "thanks",
        "thank",
        "regards",
        "the",
        "our",
        "my",
        "we",
        "team",
        "app",
        "local",
        "tick",
    }
)


def looks_like_letter_team_voice(text: str) -> bool:
    """True for we / the team. A letter is one named editor, not a chorus."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(LETTER_TEAM_VOICE_RE.search(cleaned))


def has_letter_surname(text: str) -> bool:
    """True when copy carries First Last from the profile, not a lone given name."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    for match in LETTER_SURNAME_RE.finditer(cleaned):
        first, last = match.group(1).casefold(), match.group(2).casefold()
        if first in _LETTER_NAME_STOP or last in _LETTER_NAME_STOP:
            continue
        return True
    return False


def letter_reason(text: str) -> str | None:
    """Silence when the letter only asks, asks first, recs crush, or has no surname."""
    if looks_like_letter_crush(text):
        return LETTER_ASK_WITHOUT_GIFT_REASON
    first: str | None = None
    for line in (text or "").splitlines():
        cleaned = _URL_IN_TEXT_RE.sub(" ", line).strip()
        if len(cleaned) < MIN_FACT_CHARS:
            continue
        if looks_like_letter_ask(cleaned) or looks_like_letter_crush(cleaned):
            if first is None:
                return LETTER_ASK_WITHOUT_GIFT_REASON
            continue
        first = cleaned
    if first is None:
        return LETTER_ASK_WITHOUT_GIFT_REASON
    if looks_like_letter_team_voice(text) or not has_letter_surname(text):
        return LETTER_WITHOUT_SURNAME_REASON
    return None


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


def looks_like_bot_author(text: str) -> bool:
    """True when a fact names dependabot / renovate / github-actions."""
    if not text or not text.strip():
        return False
    return bool(BOT_AUTHOR_RE.search(text))


def looks_like_version_diff(text: str) -> bool:
    """True for bump-from-X-to-Y / Released v1.2.3. Version diffs are not a launch."""
    if not text or not text.strip():
        return False
    return bool(VERSION_DIFF_RE.search(text))


def _is_readme_install_fact(text: str) -> bool:
    stripped = text.strip().casefold()
    return stripped.startswith("readme has an install") or stripped.startswith("readme has a")


def _is_human_merge(text: str) -> bool:
    return looks_like_merged_pr_fact(text) and not looks_like_bot_author(text)


def looks_like_bot_bump_week(
    texts: tuple[str, ...] | list[str],
    *,
    kinds: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True when the look's merges are only bots, or the window is only version diffs.

    A human feat next to a bump stays. A week of dependabot / renovate /
    github-actions, or a version tag without a human merge, is changelog.
    When release/pull/tag kinds exist, ignore README/description — a stale
    one-liner is not a story next to a version diff.
    """
    meat = [item.strip() for item in texts if item and item.strip()]
    if not meat:
        return False
    if kinds is not None and len(tuple(kinds)) == len(tuple(texts)):
        structured: list[str] = []
        for kind, text in zip(kinds, texts, strict=False):
            label = str(kind or "").strip().lower()
            line = str(text or "").strip()
            if not line:
                continue
            if label in {"release", "tag", "pull"}:
                structured.append(line)
        if structured:
            meat = structured
    story = [item for item in meat if not _is_readme_install_fact(item)]
    if not story:
        return False
    if any(_is_human_merge(item) for item in story):
        return False
    leftover = [
        item
        for item in story
        if not (
            looks_like_bot_author(item)
            or looks_like_version_diff(item)
            or looks_like_commit_noise(item)
            or looks_like_merged_pr_fact(item)
        )
    ]
    if leftover:
        return False
    # A dependabot mention in product copy is not a look window.
    # Need a bot merge or a version tag / bump-from-X-to-Y.
    return any(
        (looks_like_merged_pr_fact(item) and looks_like_bot_author(item)) or looks_like_version_diff(item)
        for item in story
    )


def looks_like_weekly_update(text: str) -> bool:
    """True for 'weekly update' / recap copy. A cadence label is not history."""
    if not text or not text.strip():
        return False
    return bool(WEEKLY_UPDATE_RE.search(text))


def looks_like_dead_star_count(text: str) -> bool:
    """True for 'N stars' / a star ranking. A star ask after a try stays."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    if not DEAD_STAR_COUNT_RE.search(cleaned):
        return False
    # "star the repo after you try it" is an ask, not a corpse count.
    if re.search(r"(?i)\bstar\s+the\s+repo\b", cleaned) and not DEAD_STAR_COUNT_RE.search(
        re.sub(r"(?i)\bstar\s+the\s+repo\b", " ", cleaned)
    ):
        return False
    return True


def has_workshop_life(text: str) -> bool:
    """True for install, a public issue, or life after the spike."""
    if not text or not text.strip():
        return False
    if _is_readme_install_fact(text):
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    # "ranking without installs" is a corpse, not usage.
    cleaned = re.sub(
        r"(?i)\b(?:without|no|bez|brak)\s+(?:an?\s+|any\s+)?"
        r"(?:install(?:s|ed|ation|ing)?|instalacj\w*|issue(?:s)?)\b",
        " ",
        cleaned,
    )
    return bool(WORKSHOP_LIFE_RE.search(cleaned))


def looks_like_dead_star_story(
    texts: tuple[str, ...] | list[str],
    *,
    kinds: tuple[str, ...] | list[str] | None = None,
) -> bool:
    """True when the look is a star count / ranking without usage after the spike.

    A human feat, an install, a public issue, or life after the spike stays.
    A README that merely names an install is not usage.
    """
    meat = [item.strip() for item in texts if item and item.strip()]
    if not meat:
        return False
    if kinds is not None and len(tuple(kinds)) == len(tuple(texts)):
        structured: list[str] = []
        for kind, text in zip(kinds, texts, strict=False):
            label = str(kind or "").strip().lower()
            line = str(text or "").strip()
            if not line:
                continue
            if label in {"release", "tag", "pull", "issue", "issue_comment"}:
                structured.append(line)
        if structured:
            meat = structured
    story = [item for item in meat if not _is_readme_install_fact(item)]
    if not story:
        return False
    if any(has_workshop_life(item) for item in story):
        return False
    leftover = [
        item
        for item in story
        if not (
            looks_like_dead_star_count(item)
            or looks_like_ranking_dump(item)
            or looks_like_commit_noise(item)
        )
    ]
    if leftover:
        return False
    return any(looks_like_dead_star_count(item) for item in story)


def has_real_feedback(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> bool:
    """True when a public GitHub issue/PR excerpt is in the brief."""
    return bool(feedback_excerpt_texts(facts))


def has_monday_history(
    *,
    tryable: bool,
    artifact_urls: tuple[str, ...] | list[str] = (),
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]] = (),
) -> bool:
    """Ship/tryable or a real public excerpt. Otherwise the Monday look is empty."""
    if tryable:
        return True
    if any(is_ship_artifact_url(url) for url in artifact_urls if url):
        return True
    return has_real_feedback(facts)


def looks_like_monday_without_history(
    *,
    story_kind: StoryKind | str | None = None,
    preferred_arena: ArenaId | str | None = None,
    tryable: bool = False,
    artifact_urls: tuple[str, ...] | list[str] = (),
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]] = (),
    blob: str = "",
) -> bool:
    """Monday look / weekly update with no ship and no real feedback."""
    if has_monday_history(tryable=tryable, artifact_urls=artifact_urls, facts=facts):
        return False
    kind = story_kind if isinstance(story_kind, StoryKind) or story_kind is None else StoryKind(story_kind)
    arena = preferred_arena
    if isinstance(preferred_arena, str) and preferred_arena:
        try:
            arena = ArenaId(preferred_arena)
        except ValueError:
            arena = preferred_arena
    if kind is StoryKind.MAJOR or arena is ArenaId.NEWSLETTER or looks_like_weekly_update(blob):
        return True
    return False


def looks_like_waitlist(text: str) -> bool:
    """True for a waitlist / coming soon / join-the-list page. That is not a ship."""
    if not text or not text.strip():
        return False
    return bool(WAITLIST_RE.search(text))


def looks_like_pending_ci(text: str) -> bool:
    """True for pending / yellow CI. Unknown is silence, not a ship or a fail."""
    if not text or not text.strip():
        return False
    return bool(PENDING_CI_RE.search(text))


def looks_like_failed_ci(text: str) -> bool:
    """True for failed / red CI. A red default branch is not tryable."""
    if not text or not text.strip():
        return False
    return bool(FAILED_CI_RE.search(text))


def looks_like_prerelease(text: str) -> bool:
    """True for a GitHub draft / prerelease / RC / beta. That is not a ship."""
    if not text or not text.strip():
        return False
    return bool(PRERELEASE_RE.search(text))


def looks_like_login_gate(text: str) -> bool:
    """True for a login wall / HEAD-GET 401/403. A stranger must run it without logging in."""
    if not text or not text.strip():
        return False
    return bool(LOGIN_GATE_RE.search(text))


def looks_like_shortener(text: str) -> bool:
    """True for a shortener host or skracacz talk. Not click-and-run."""
    if not text or not text.strip():
        return False
    if SHORTENER_TALK_RE.search(text):
        return True
    return any(is_shortener_url(match.group(0)) for match in _URL_IN_TEXT_RE.finditer(text))


def looks_like_utm_farm(text: str) -> bool:
    """True for utm_* / click-id tracking on the artifact. A farm is not a demo."""
    if not text or not text.strip():
        return False
    if UTM_FARM_RE.search(text):
        return True
    return any(_has_utm_farm_query(urlparse(match.group(0)).query) for match in _URL_IN_TEXT_RE.finditer(text))


def looks_like_click_here(text: str) -> bool:
    """True for click here / kliknij tu. A bait phrase is not a tryable URL."""
    if not text or not text.strip():
        return False
    return bool(CLICK_HERE_RE.search(text))


def looks_like_dead_link(text: str) -> bool:
    """True for a generic HEAD/GET 404/410 corpse. A stranger cannot click a dead link."""
    if not text or not text.strip():
        return False
    return bool(DEAD_LINK_RE.search(text))


def looks_like_dead_tls(text: str) -> bool:
    """True for a cert error / mixed content / rejected HTTPS. Do not click the warning."""
    if not text or not text.strip():
        return False
    return bool(DEAD_TLS_RE.search(text))


def looks_like_issues_disabled(text: str) -> bool:
    """True when the issue tracker is off. No camp, no Show HN, no social angle."""
    if not text or not text.strip():
        return False
    return bool(ISSUES_DISABLED_RE.search(text))


def looks_like_fork(text: str) -> bool:
    """True when the repo is a GitHub fork. A copy is not a website."""
    if not text or not text.strip():
        return False
    return bool(FORK_RE.search(text))


def looks_like_empty_repo(text: str) -> bool:
    """True when there is no tree or no README. An empty repo is not a website."""
    if not text or not text.strip():
        return False
    return bool(EMPTY_REPO_RE.search(text))


def looks_like_private_repo(text: str) -> bool:
    """True when the repo is private. A locked tree is not a website."""
    if not text or not text.strip():
        return False
    return bool(PRIVATE_REPO_RE.search(text))


def looks_like_template(text: str) -> bool:
    """True for isTemplate / generate-from-template / boilerplate. A template is not a product."""
    if not text or not text.strip():
        return False
    return bool(TEMPLATE_RE.search(text))


def looks_like_archived_repo(text: str) -> bool:
    """True when the repo is archived or disabled. A museum is not a launch."""
    if not text or not text.strip():
        return False
    return bool(ARCHIVED_REPO_RE.search(text))


def looks_like_server_splash(text: str) -> bool:
    """True for Welcome to nginx / Apache default / Caddy placeholder. A splash is not a product."""
    if not text or not text.strip():
        return False
    return bool(SERVER_SPLASH_RE.search(text))


def looks_like_dead_release_asset(text: str) -> bool:
    """True for a listed release asset whose download is 404/410. A missing file is not a ship."""
    if not text or not text.strip():
        return False
    return bool(DEAD_RELEASE_ASSET_RE.search(text))


def looks_like_roadmap(text: str) -> bool:
    """True for Coming Q3 / soon / on the roadmap. A calendar is not a ship."""
    if not text or not text.strip():
        return False
    return bool(ROADMAP_RE.search(text))


def looks_like_event(text: str) -> bool:
    """True for webinar / meetup / calendar / join us Thursday. Not a ship."""
    if not text or not text.strip():
        return False
    return bool(EVENT_RE.search(text))


def looks_like_calendar_filler(text: str) -> bool:
    """True for a holiday, repo birthday, or happy Friday. A calendar does not write."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(CALENDAR_FILLER_RE.search(cleaned))


def looks_like_counter_thanks(text: str) -> bool:
    """True for 'thanks for N stars' / a follower milestone. A thank-you is not an angle."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(COUNTER_THANKS_RE.search(cleaned))


def looks_like_fog(text: str) -> bool:
    """True for a subtweet / you-know-who / unnamed allusion. Name it or stay silent."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(FOG_RE.search(cleaned))


def looks_like_founder_journal(text: str) -> bool:
    """True for desk setup / tools I use / day in the life / morning routine. Lifestyle is not a product."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(FOUNDER_JOURNAL_RE.search(cleaned))


def looks_like_lead_magnet(text: str) -> bool:
    """True for ebook / free guide / typeform for an email. A mail gate is not tryable."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(LEAD_MAGNET_RE.search(cleaned))


def looks_like_logo_reveal(text: str) -> bool:
    """True for rebrand / palette / moodboard / logo reveal. A look is not a ship."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(LOGO_REVEAL_RE.search(cleaned))


def looks_like_fomo(text: str) -> bool:
    """True for only-N-spots / countdown / last chance. Pressure is not a product."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(FOMO_RE.search(cleaned))


def looks_like_meme(text: str) -> bool:
    """True for Drake / wojak / reaction image / a meme board. A picture is not a product."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(MEME_RE.search(cleaned))


def looks_like_deck(text: str) -> bool:
    """True for a pitch / PDF slides / Notion one-pager. A deck is not an artifact."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(DECK_RE.search(cleaned))


def looks_like_linktree(text: str) -> bool:
    """True for Linktree / Carrd / bio site / a list of links. A board is not an artifact."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(LINKTREE_RE.search(cleaned))


def looks_like_press_release(text: str) -> bool:
    """True for we're excited / announcement / unveiling / delighted to share."""
    if not text or not text.strip():
        return False
    return bool(PRESS_RELEASE_RE.search(text))


def looks_like_superlative(text: str) -> bool:
    """True for a slogan such as revolutionary / world's first / AI-powered."""
    return bool(SUPERLATIVE_RE.search(text))


def looks_like_dunk(text: str) -> bool:
    """True when copy mocks another project. Contrast or help is not a dunk."""
    if DUNK_PHRASE_RE.search(text):
        return True
    for match in DUNK_NAMED_RE.finditer(text):
        name = match.group("name")
        if len(name) > 1 and name.casefold() not in _DUNK_SUBJECT_STOP:
            return True
    return False


def looks_like_worse_clone(text: str) -> bool:
    """True when facts say someone already did this better, or we reinvented X."""
    if not text or not text.strip():
        return False
    if not WORSE_CLONE_RE.search(text):
        return False
    return not _CLONE_BETTER_IDEA_RE.search(text)


def is_parent_post_url(url: str | None) -> bool:
    """True for a social parent post. A ship artifact is not a foreign wave."""
    if not url or is_ship_artifact_url(url):
        return False
    host = _http_host(url)
    if not host:
        return False
    parsed = urlparse(url.strip())
    path = parsed.path or ""
    query = parsed.query or ""
    if host in {"x.com", "twitter.com"} or host.endswith(".twitter.com") or host.startswith("nitter."):
        return bool(re.search(r"/status/\d+", path))
    if host == "bsky.app":
        return bool(re.search(r"/profile/[^/]+/post/[^/]+", path))
    if host == "news.ycombinator.com":
        return path.rstrip("/") == "/item" and "id=" in query
    if host == "reddit.com" or host.endswith(".reddit.com"):
        return "/comments/" in path
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        return "/posts/" in path or "/feed/update/" in path
    return False


def looks_like_reply(text: str) -> bool:
    """True for reply-under / in-reply-to copy. The bare word 'reply' is not."""
    if not text or not text.strip():
        return False
    return bool(REPLY_SHAPE_RE.search(text))


def _github_repo_slug(url: str | None) -> str | None:
    if not is_ship_artifact_url(url):
        return None
    parts = [item for item in urlparse(url.strip()).path.split("/") if item]
    if len(parts) < 2:
        return None
    return f"{parts[0]}/{parts[1]}"


def _ship_urls_and_slugs(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    urls: list[str] = []
    slugs: list[str] = []
    for kind, text, url in facts:
        if _is_reply_fact(kind, text, url):
            continue
        candidates = [url] if url else []
        if text:
            candidates.extend(_SHIP_URL_IN_TEXT_RE.findall(text))
        for candidate in candidates:
            if not is_ship_artifact_url(candidate):
                continue
            cleaned = candidate.strip().rstrip("/")
            if cleaned not in urls:
                urls.append(cleaned)
            slug = _github_repo_slug(cleaned)
            if slug and slug not in slugs:
                slugs.append(slug)
    return tuple(urls), tuple(slugs)


def _is_reply_fact(kind: str, text: str, _url: str | None) -> bool:
    if kind.strip().lower() in PARENT_FACT_KINDS:
        return True
    return looks_like_reply(text)


def _parent_about_our_ship(
    _kind: str,
    text: str,
    url: str | None,
    ship_urls: tuple[str, ...] | list[str],
    ship_slugs: tuple[str, ...] | list[str],
) -> bool:
    """A social parent URL is not enough. The parent must be our watch/ship."""
    if not ship_slugs:
        return False
    if is_ship_artifact_url(url):
        slug = _github_repo_slug(url)
        if slug and slug in ship_slugs:
            return True
        cleaned = url.strip().rstrip("/")
        if any(cleaned == ship or cleaned.startswith(ship + "/") for ship in ship_urls):
            return True
        return False
    blob = text or ""
    folded = blob.casefold()
    for ship in ship_urls:
        if ship.casefold() in folded:
            return True
    for slug in ship_slugs:
        if re.search(rf"\b{re.escape(slug)}\b", blob, flags=re.I):
            return True
    return False


def looks_like_foreign_wave(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> bool:
    """True when a reply sits under a post that is not our watch/ship."""
    packed = tuple(facts)
    replies = [item for item in packed if _is_reply_fact(*item)]
    if not replies:
        return False
    ship_urls, ship_slugs = _ship_urls_and_slugs(packed)
    return any(
        not _parent_about_our_ship(kind, text, url, ship_urls, ship_slugs)
        for kind, text, url in replies
    )


# A reply under a parent URL (#27) needs one new thought. Echo of the
# parent, or a body that is only the link, is a dead RT — silence on agora.
# Pair of #27 (X does not get an empty feed) and #41 (ratio is the comment).
AGORA_NO_NEW_THOUGHT_REASON = "agora_no_new_thought"


def _fold_agora_thought(text: str) -> str:
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return " ".join(cleaned.split()).casefold()


def has_agora_thought(text: str) -> bool:
    """True when a non-URL line is long enough to be a new thought."""
    return len(_fold_agora_thought(text)) >= MIN_FACT_CHARS


def looks_like_agora_echo(thought: str, parent: str) -> bool:
    """True when the reply restates the parent instead of adding a thought."""
    folded = _fold_agora_thought(thought)
    other = _fold_agora_thought(parent)
    if not folded or not other:
        return False
    if folded == other:
        return True
    shorter, longer = (folded, other) if len(folded) <= len(other) else (other, folded)
    if len(shorter) < MIN_FACT_CHARS:
        return False
    return shorter in longer


def _agora_parent_facts(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> tuple[tuple[str, str, str | None], ...]:
    packed = tuple(facts)
    replies = [item for item in packed if _is_reply_fact(*item)]
    if replies:
        return tuple(replies)
    return tuple(
        item for item in packed if item[2] and is_parent_post_url(item[2])
    )


def has_parent_post(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> bool:
    """True when the brief names a parent-post URL. X is reply, not an original."""
    return bool(_agora_parent_facts(facts))


def agora_reason(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
    extra: str | None = None,
) -> str | None:
    """Silence when an X reply has no new thought: echo, link-only, or empty."""
    packed = tuple(facts)
    parents = _agora_parent_facts(packed)
    if not parents:
        return None
    parent_thoughts = tuple(
        _fold_agora_thought(text) for _kind, text, _url in parents if _fold_agora_thought(text)
    )

    def _is_new_thought(text: str) -> bool:
        folded = _fold_agora_thought(text)
        if len(folded) < MIN_FACT_CHARS:
            return False
        return not any(looks_like_agora_echo(folded, parent) for parent in parent_thoughts)

    if extra is not None:
        return None if _is_new_thought(extra) else AGORA_NO_NEW_THOUGHT_REASON
    for kind, text, url in packed:
        if _is_reply_fact(kind, text, url):
            continue
        if kind.strip().lower() == "artifact" or text.strip().casefold() == "ship artifact":
            continue
        if url and is_parent_post_url(url) and not _fold_agora_thought(text):
            continue
        if _is_new_thought(text):
            return None
    return AGORA_NO_NEW_THOUGHT_REASON


def looks_like_invented_opinion(text: str) -> bool:
    """True for unsourced praise such as 'users love'. Not a quote."""
    return bool(INVENTED_OPINION_RE.search(text))


def looks_like_engagement_bait(text: str) -> bool:
    """True when copy asks for a gesture. A feedback question is not bait."""
    return bool(ENGAGEMENT_BAIT_RE.search(text))


def looks_like_contest(text: str) -> bool:
    """True for a giveaway, raffle, RT-to-win, or prize-for-follow. Not a product."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(CONTEST_RE.search(cleaned))


def looks_like_poll(text: str) -> bool:
    """True for a poll, this-or-that, quiz, or ankieta. Not a product."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(POLL_RE.search(cleaned))


def looks_like_model_in_frame(text: str) -> bool:
    """True for a prompt dump, 'I asked ChatGPT', or 'as an AI'. HoM is not a model in the frame."""
    if not text or not text.strip():
        return False
    if any(is_model_host_url(match.group(0)) for match in _URL_IN_TEXT_RE.finditer(text)):
        return True
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    if MODEL_IN_FRAME_RE.search(cleaned):
        return True
    return bool(MODEL_DUMP_RE.search(cleaned))


def looks_like_thread(text: str) -> bool:
    """True for a 1/n serial, thread, or storm. One post, not a serial."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    numbered = _ALWAYS_ON_RE.sub(" ", cleaned)
    if THREAD_NUMBER_RE.search(numbered):
        return True
    leftover = _THREAD_TECH_RE.sub(" ", cleaned)
    return bool(THREAD_WORD_RE.search(leftover))


def looks_like_ranking_dump(text: str) -> bool:
    """True for HN front, a star counter, or a vanity chart. Not an artifact."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(RANKING_DUMP_RE.search(cleaned))


def looks_like_hashtag_wall(text: str) -> bool:
    """True when copy dumps tags or ends on a tag-only tail. One inline tag can stay."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    tags = HASHTAG_RE.findall(cleaned)
    if len(tags) > MAX_HASHTAGS:
        return True
    if not tags:
        return False
    for line in cleaned.splitlines():
        stripped = line.strip()
        if stripped and _HASHTAG_TAIL_RE.fullmatch(stripped):
            return True
    return False


def looks_like_person_mention(text: str) -> bool:
    """True when copy has @login outside a URL. A draft does not summon people."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(MENTION_RE.search(cleaned))


def is_public_issue_url(url: str | None) -> bool:
    """True for a public GitHub issue/PR comment URL. Slack / mail / DM is not."""
    cleaned = (url or "").strip().rstrip("/")
    return bool(_PUBLIC_ISSUE_URL_RE.fullmatch(cleaned))


def is_private_channel_url(url: str | None) -> bool:
    """True for a Slack / webmail host. A private channel is not an excerpt."""
    return _host_in(url, PRIVATE_CHANNEL_HOSTS)


def looks_like_private_conversation(text: str) -> bool:
    """True for a Slack / mail / DM dump. Anonymized still counts. Not a public issue."""
    if not text or not text.strip():
        return False
    if any(is_private_channel_url(match.group(0)) for match in _URL_IN_TEXT_RE.finditer(text)):
        return True
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(PRIVATE_CONVERSATION_RE.search(cleaned))


def looks_like_secret(text: str) -> bool:
    """True for a token, password, or key. Not a product. Fail closed."""
    if not text or not text.strip():
        return False
    return bool(SECRET_RE.search(text))


def looks_like_world_commentary(text: str) -> bool:
    """True for a political / cultural / news-of-the-day take. Not a product."""
    if not text or not text.strip():
        return False
    if any(is_news_host_url(match.group(0)) for match in _URL_IN_TEXT_RE.finditer(text)):
        return True
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(WORLD_COMMENTARY_RE.search(cleaned))


def looks_like_hire_fundraise(text: str) -> bool:
    """True for hire / a funding round / an offsite. Not a product. CMO is not a job board."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(HIRE_FUNDRAISE_RE.search(cleaned))


def looks_like_source_available_license(text: str) -> bool:
    """True for BUSL / Commons Clause / fair code / SSPL / source-available. Not OSS."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    remainder = NEGATED_SOURCE_AVAILABLE_RE.sub(" ", cleaned)
    return bool(SOURCE_AVAILABLE_LICENSE_RE.search(remainder))


def looks_like_open_source_claim(text: str) -> bool:
    """True when the text still claims OSS after honest denials are stripped."""
    if not text or not text.strip():
        return False
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    remainder = NEGATED_OPEN_SOURCE_RE.sub(" ", cleaned)
    return bool(OPEN_SOURCE_CLAIM_RE.search(remainder))


def looks_like_source_available_as_oss(text: str) -> bool:
    """Source-available license plus an OSS sticker. Silence, not a badge."""
    if not looks_like_source_available_license(text):
        return False
    return looks_like_open_source_claim(text)


def _url_points_at_license_file(url: str) -> bool:
    path = urlparse(url.strip()).path or ""
    name = path.rstrip("/").rsplit("/", 1)[-1]
    return bool(name and LICENSE_FILE_NAME_RE.fullmatch(name))


def looks_like_license_file(text: str) -> bool:
    """True when the text names a LICENSE file, not a license family."""
    if not text or not text.strip():
        return False
    if LICENSE_FILE_NAME_RE.fullmatch(text.strip()):
        return True
    if any(_url_points_at_license_file(match.group(0)) for match in _URL_IN_TEXT_RE.finditer(text)):
        return True
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    for match in LICENSE_FILE_RE.finditer(cleaned):
        if _LICENSE_FAMILY_BEFORE_RE.search(cleaned[: match.start()]):
            continue
        return True
    return False


def looks_like_open_source_without_license(text: str) -> bool:
    """OSS sticker without a LICENSE file. Drop the word, or stay silent."""
    if not looks_like_open_source_claim(text):
        return False
    return not looks_like_license_file(text)


def _strip_open_source_chunk(chunk: str) -> str:
    """Drop a positive OSS sticker. Honest denial stays."""
    kept: list[str] = []

    def _hold(match: re.Match[str]) -> str:
        kept.append(match.group(0))
        return f"\x00{len(kept) - 1}\x00"

    protected = NEGATED_OPEN_SOURCE_RE.sub(_hold, chunk)
    stripped = OPEN_SOURCE_CLAIM_RE.sub(" ", protected)
    for index, phrase in enumerate(kept):
        stripped = stripped.replace(f"\x00{index}\x00", phrase)
    return stripped


def strip_open_source_claim(text: str) -> str:
    """Drop an OSS sticker. Honest denial and URLs stay. Empty after strip is silence."""
    if not text or not looks_like_open_source_claim(text):
        return text
    parts: list[str] = []
    last = 0
    for match in _URL_IN_TEXT_RE.finditer(text):
        parts.append(_strip_open_source_chunk(text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_strip_open_source_chunk(text[last:]))
    cleaned = "".join(parts)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    cleaned = re.sub(r" +([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"[ \t]*[\u2014\u2013-][ \t]*(?=\n|$)", "", cleaned)
    return cleaned.strip(" \t,;:\u2014\u2013-")


def strip_person_mentions(text: str) -> str:
    """Drop @login summons. URLs stay. Empty after strip is silence."""
    parts: list[str] = []
    last = 0
    for match in _URL_IN_TEXT_RE.finditer(text):
        parts.append(_STRIP_MENTION_RE.sub("", text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(_STRIP_MENTION_RE.sub("", text[last:]))
    cleaned = "".join(parts)
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)
    cleaned = re.sub(r" *\n *", "\n", cleaned)
    return cleaned.strip()


def metric_tokens(text: str) -> frozenset[str]:
    """Claim numbers a costume may repeat: 10x, 1M users, 50%, 100k."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    found: set[str] = set()
    for match in METRIC_TOKEN_RE.finditer(cleaned):
        raw = match.group(0).replace(",", "").replace("×", "x")
        token = " ".join(raw.split()).casefold()
        if not token:
            continue
        found.add(token)
        if token.endswith(" users"):
            found.add(token[: -len(" users")])
    if BENCHMARK_WORD_RE.search(cleaned):
        found.add("benchmark")
    return frozenset(found)


def invented_metric_reason(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
    extra: str = "",
) -> str | None:
    """Silence when the costume grows a number the brief did not state."""
    if not extra or not extra.strip():
        return None
    allowed: set[str] = set()
    for _kind, text, url in facts:
        allowed.update(metric_tokens(text))
        if url:
            allowed.update(metric_tokens(url))
    if any(token not in allowed for token in metric_tokens(extra)):
        return "invented_metric"
    return None


def quoted_spans(text: str) -> tuple[str, ...]:
    """Quoted excerpts only. No excerpt — no quotation marks."""
    found: list[str] = []
    for match in _QUOTED_SPAN_RE.finditer(text):
        span = next((group for group in match.groups() if group), "")
        cleaned = span.strip()
        if cleaned:
            found.append(cleaned)
    return tuple(found)


def has_quote_mark(text: str) -> bool:
    return any(mark in text for mark in QUOTE_MARKS)


def is_feedback_excerpt_fact(kind: str, artifact_url: str | None) -> bool:
    """A quote needs an excerpt-shaped fact from a public GitHub issue/PR."""
    if kind.strip().lower() not in FEEDBACK_EXCERPT_KINDS:
        return False
    return is_public_issue_url(artifact_url)


def feedback_excerpt_texts(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
) -> tuple[str, ...]:
    """Texts that may legally be quoted: excerpt/comment + https URL."""
    found: list[str] = []
    for kind, text, url in facts:
        if not is_feedback_excerpt_fact(kind, url):
            continue
        cleaned = text.strip()
        if cleaned:
            found.append(cleaned)
    return tuple(found)


def quote_without_sourced_excerpt(
    text: str,
    excerpt_texts: tuple[str, ...] | list[str],
) -> bool:
    """True when a quotation mark appears without a matching excerpt+URL."""
    if not has_quote_mark(text):
        return False
    spans = quoted_spans(text)
    if not spans:
        return True
    haystacks = [item.casefold() for item in excerpt_texts if item and item.strip()]
    if not haystacks:
        return True
    for span in spans:
        needle = span.casefold()
        if not any(needle in hay for hay in haystacks):
            return True
    return False


def unquotable_reason(
    facts: tuple[tuple[str, str, str | None], ...] | list[tuple[str, str, str | None]],
    extra: str = "",
) -> str | None:
    """Silence reason when a quote, 'users love', a gesture ask, a contest, a poll, a prompt dump, a calendar greeting, a vanity thank-you, a subtweet, a founder journal, a lead magnet, artificial FOMO, a meme, a deck, a linktree, a 1/n serial, a ranking dump, a tag wall, a summon, a private conversation, a secret, a world take, a hire/round/offsite, a source-available OSS sticker, or a number is not in the brief."""
    packed = tuple(facts)
    excerpts = feedback_excerpt_texts(packed)
    operator_texts = [
        text for kind, text, url in packed if not is_feedback_excerpt_fact(kind, url)
    ]
    for _kind, text, url in packed:
        if looks_like_model_in_frame(text) or is_model_host_url(url):
            return "model_in_frame"
    if extra and (looks_like_model_in_frame(extra) or is_model_host_url(extra)):
        return "model_in_frame"
    for _kind, text, _url in packed:
        if looks_like_calendar_filler(text):
            return CALENDAR_FILLER_REASON
    if extra and looks_like_calendar_filler(extra):
        return CALENDAR_FILLER_REASON
    for _kind, text, _url in packed:
        if looks_like_counter_thanks(text):
            return COUNTER_THANKS_REASON
    if extra and looks_like_counter_thanks(extra):
        return COUNTER_THANKS_REASON
    for _kind, text, _url in packed:
        if looks_like_fog(text):
            return FOG_REASON
    if extra and looks_like_fog(extra):
        return FOG_REASON
    for _kind, text, _url in packed:
        if looks_like_founder_journal(text):
            return FOUNDER_JOURNAL_REASON
    if extra and looks_like_founder_journal(extra):
        return FOUNDER_JOURNAL_REASON
    for _kind, text, _url in packed:
        if looks_like_lead_magnet(text):
            return LEAD_MAGNET_REASON
    if extra and looks_like_lead_magnet(extra):
        return LEAD_MAGNET_REASON
    for _kind, text, _url in packed:
        if looks_like_fomo(text):
            return FOMO_REASON
    if extra and looks_like_fomo(extra):
        return FOMO_REASON
    for _kind, text, _url in packed:
        if looks_like_meme(text):
            return MEME_REASON
    if extra and looks_like_meme(extra):
        return MEME_REASON
    for _kind, text, _url in packed:
        if looks_like_deck(text):
            return DECK_REASON
    if extra and looks_like_deck(extra):
        return DECK_REASON
    for _kind, text, _url in packed:
        if looks_like_linktree(text):
            return LINKTREE_REASON
    if extra and looks_like_linktree(extra):
        return LINKTREE_REASON
    for _kind, text, url in packed:
        if looks_like_secret(text):
            return SECRET_REASON
    if extra and looks_like_secret(extra):
        return SECRET_REASON
    for _kind, text, url in packed:
        if looks_like_private_conversation(text) or is_private_channel_url(url):
            return "private_conversation"
    if extra and (
        looks_like_private_conversation(extra) or is_private_channel_url(extra)
    ):
        return "private_conversation"
    for _kind, text, url in packed:
        if looks_like_world_commentary(text) or is_news_host_url(url):
            return "world_commentary"
    if extra and (looks_like_world_commentary(extra) or is_news_host_url(extra)):
        return "world_commentary"
    for _kind, text, _url in packed:
        if looks_like_hire_fundraise(text):
            return "hire_fundraise"
    if extra and looks_like_hire_fundraise(extra):
        return "hire_fundraise"
    blob = "\n".join((*operator_texts, extra) if extra else operator_texts)
    if looks_like_source_available_as_oss(blob):
        return "source_available_not_oss"
    if looks_like_foreign_wave(packed):
        return "foreign_wave"
    if extra and looks_like_foreign_wave((*packed, ("signal", extra, None))):
        return "foreign_wave"
    if any(looks_like_invented_opinion(text) for text in operator_texts):
        return "invented_opinion"
    if extra and looks_like_invented_opinion(extra):
        if not any(looks_like_invented_opinion(item) for item in excerpts):
            return "invented_opinion"
    if any(looks_like_engagement_bait(text) for text in operator_texts):
        return "engagement_bait"
    if extra and looks_like_engagement_bait(extra):
        return "engagement_bait"
    if any(looks_like_contest(text) for text in operator_texts):
        return "contest"
    if extra and looks_like_contest(extra):
        return "contest"
    if any(looks_like_poll(text) for text in operator_texts):
        return "poll"
    if extra and looks_like_poll(extra):
        return "poll"
    if any(looks_like_thread(text) for text in operator_texts):
        return "thread"
    if extra and looks_like_thread(extra):
        return "thread"
    if any(looks_like_ranking_dump(text) for text in operator_texts):
        return "ranking_not_an_artifact"
    if extra and looks_like_ranking_dump(extra):
        return "ranking_not_an_artifact"
    if any(looks_like_hashtag_wall(text) for text in operator_texts):
        return "hashtag_wall"
    if extra and looks_like_hashtag_wall(extra):
        return "hashtag_wall"
    if any(looks_like_person_mention(text) for text in operator_texts):
        return "person_mention"
    if extra and looks_like_person_mention(extra):
        return "person_mention"
    blob = "\n".join((*operator_texts, extra) if extra else operator_texts)
    if quote_without_sourced_excerpt(blob, excerpts):
        return "quote_without_excerpt"
    if extra:
        metric = invented_metric_reason(packed, extra)
        if metric:
            return metric
    return None


def has_named_subreddit(text: str) -> bool:
    return bool(SUBREDDIT_RE.search(text))


# Village without disclosure is spam. A named room (#31) is not enough.
# Native self-post, say it's ours, repo at the bottom or first comment.
# Pair of #49 (disclose) and #31 (named room).
REDDIT_NO_ROOM_REASON = "reddit_no_room"
REDDIT_NO_DISCLOSURE_REASON = "reddit_no_disclosure"
REDDIT_UNDISCLOSED_RE = re.compile(r"(?i)\bbez\s+ujawnien")
REDDIT_DISCLOSE_RE = re.compile(
    r"(?i)(?:"
    r"\bdisclos(?:e|ure|ing)\b|"
    r"\bujawni(?:am|amy|enie|ć)\b|"
    r"\bthis is (?:my|our|mine)\b|"
    r"\bI (?:built|wrote|made|shipped)\b|"
    r"\bmy (?:project|tool|repo|app)\b|"
    r"\bour (?:project|tool|repo|app)\b|"
    r"\bI['’]m the (?:author|maintainer|dev)\b|"
    r"\baffiliated\b|"
    r"\bto nasze\b|"
    r"\bto m[oó]j(?:e)?\b"
    r")"
)


def looks_like_reddit_disclose(text: str) -> bool:
    """True for I built / this is my project / disclose. Affiliation must be said."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    if REDDIT_UNDISCLOSED_RE.search(cleaned):
        return False
    return bool(REDDIT_DISCLOSE_RE.search(cleaned))


def has_reddit_repo(text: str) -> bool:
    """True when a ship artifact URL can sit at the bottom or first comment."""
    for match in _URL_IN_TEXT_RE.finditer(text or ""):
        url = match.group(0).rstrip(").,;]")
        if is_ship_artifact_url(url):
            return True
    return False


def reddit_reason(text: str) -> str | None:
    """Silence when village would post without a named room, disclosure, or repo."""
    if not has_named_subreddit(text):
        return REDDIT_NO_ROOM_REASON
    if not looks_like_reddit_disclose(text) or not has_reddit_repo(text):
        return REDDIT_NO_DISCLOSURE_REASON
    return None


def has_cinema_package(text: str) -> bool:
    """True when the cut names title+thumb / tytuł+obietnica in 0.5s. A label is not."""
    return bool(CINEMA_PACKAGE_RE.search(text or ""))


def cinema_package_reason(text: str) -> str | None:
    """Silence on a cinema cut without the title+promise pair. kind=package is not proof."""
    if has_cinema_package(text):
        return None
    return CINEMA_MISSING_PACKAGE_REASON


def has_fair_hook(text: str) -> bool:
    """True when the cut names a 1-3s picture+voice+text hook. A label is not."""
    return bool(FAIR_HOOK_RE.search(text or ""))


def fair_hook_reason(text: str) -> str | None:
    """Silence on a fair cut without a 1-3s hook. kind=hook is not proof."""
    if has_fair_hook(text):
        return None
    return FAIR_MISSING_HOOK_REASON


def has_fair_loop(text: str) -> bool:
    """True when the cut names last-frame-into-first / rewatch. A tick loop is not."""
    return bool(FAIR_LOOP_RE.search(text))


def looks_like_fair_cta(text: str) -> bool:
    """True for subscribe / link-in-bio / swipe-up / CTA on a fair cut."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text)
    return bool(FAIR_CTA_RE.search(cleaned))


def looks_like_cinema_end(text: str) -> bool:
    """True for thanks-for-watching / subscribe / outro-logo. Cinema does not announce the end."""
    cleaned = _URL_IN_TEXT_RE.sub(" ", text or "")
    return bool(CINEMA_END_RE.search(cleaned))


def cinema_end_reason(text: str) -> str | None:
    """Silence when cinema would thank, ask to subscribe, roll an outro-logo,
    or go out without the title+promise pair. A labeled package is not the pair.
    """
    if looks_like_cinema_end(text):
        return CINEMA_ANNOUNCES_END_REASON
    return cinema_package_reason(text)


def fair_loop_reason(text: str, *, kinds: Iterable[str] = ()) -> str | None:
    """Silence on a fair cut without a loop, or with CTA and loop together."""
    named = {kind.strip().lower() for kind in kinds if kind and kind.strip()}
    looped = "loop" in named or has_fair_loop(text)
    if not looped:
        return "fair_missing_loop"
    if looks_like_fair_cta(text):
        return "fair_cta_with_loop"
    return None


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
    "BLOG_HOSTS",
    "BOT_AUTHOR_RE",
    "CANON_URL",
    "COMMIT_NOISE_RE",
    "COURT_LAUNCH_RE",
    "COURT_NOT_A_LAUNCH_REASON",
    "COURT_PITCH_RE",
    "DUNK_NAMED_RE",
    "DUNK_PHRASE_RE",
    "WORSE_CLONE_REASON",
    "WORSE_CLONE_RE",
    "EMPTY_TAVERN_REASON",
    "AGORA_NO_NEW_THOUGHT_REASON",
    "BLUESKY_PACK_WITHOUT_FEED_REASON",
    "BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON",
    "LETTER_ASK_WITHOUT_GIFT_REASON",
    "LETTER_ASK_RE",
    "LETTER_CRUSH_RE",
    "LETTER_WITHOUT_SURNAME_REASON",
    "LETTER_TEAM_VOICE_RE",
    "LETTER_SURNAME_RE",
    "SEMINAR_BRAND_VOICE_REASON",
    "SEMINAR_BRAND_VOICE_RE",
    "SEMINAR_FIRST_PERSON_RE",
    "CAFE_FEED_RE",
    "CAFE_PACK_RE",
    "CINEMA_ANNOUNCES_END_REASON",
    "CINEMA_END_RE",
    "CINEMA_MISSING_PACKAGE_REASON",
    "CONTEST_RE",
    "FAIR_CTA_RE",
    "FAIR_HOOK_RE",
    "FAIR_LOOP_RE",
    "FAIR_MISSING_HOOK_REASON",
    "POLL_RE",
    "THREAD_NUMBER_RE",
    "THREAD_WORD_RE",
    "ENGAGEMENT_BAIT_RE",
    "HASHTAG_RE",
    "HIRE_FUNDRAISE_RE",
    "HN_CAMP_REASON",
    "HN_STORY_KINDS",
    "HN_TITLE_LIMIT",
    "HN_TITLE_PREFIX",
    "LAUNCH_HOSTS",
    "LIVING_STACK_REASON",
    "LINKEDIN_FOLD",
    "LAUNCH_PITCH_RE",
    "NEGATED_OPEN_SOURCE_RE",
    "NEGATED_SOURCE_AVAILABLE_RE",
    "OPEN_SOURCE_CLAIM_RE",
    "MAX_HASHTAGS",
    "MENTION_RE",
    "FEEDBACK_EXCERPT_KINDS",
    "INVENTED_OPINION_RE",
    "LICENSE_FILE_NAME_RE",
    "LICENSE_FILE_RE",
    "LISTICLE_TITLE_RE",
    "DEAD_LINK_RE",
    "DEAD_TLS_REASON",
    "DEAD_TLS_RE",
    "DEAD_RELEASE_ASSET_RE",
    "DEAD_STAR_COUNT_RE",
    "DEAD_STAR_COUNT_REASON",
    "WORKSHOP_LIFE_RE",
    "ISSUES_DISABLED_RE",
    "FORK_RE",
    "EMPTY_REPO_RE",
    "PRIVATE_REPO_RE",
    "TEMPLATE_RE",
    "ARCHIVED_REPO_RE",
    "LOGIN_GATE_RE",
    "SERVER_SPLASH_RE",
    "METRIC_TOKEN_RE",
    "MERGED_PR_FACT_RE",
    "VERSION_DIFF_RE",
    "WEEKLY_UPDATE_RE",
    "MIN_FACT_CHARS",
    "MIN_SOCIAL_FACTS",
    "MODEL_DUMP_RE",
    "MODEL_HOSTS",
    "MODEL_IN_FRAME_RE",
    "NEWS_HOSTS",
    "NEWSLETTER_STORY_KINDS",
    "PRESS_RELEASE_REASON",
    "PRESS_RELEASE_RE",
    "PRIMARY_ARENAS",
    "PRIVATE_CHANNEL_HOSTS",
    "PRIVATE_CONVERSATION_RE",
    "SECRET_REASON",
    "SECRET_RE",
    "QUOTE_MARKS",
    "RANKING_DUMP_RE",
    "RANKING_HOSTS",
    "REDDIT_DISCLOSE_RE",
    "REDDIT_NO_DISCLOSURE_REASON",
    "REDDIT_NO_ROOM_REASON",
    "ROADMAP_RE",
    "EVENT_NOT_A_SHIP",
    "EVENT_RE",
    "CALENDAR_FILLER_REASON",
    "CALENDAR_FILLER_RE",
    "COUNTER_THANKS_REASON",
    "COUNTER_THANKS_RE",
    "FOG_REASON",
    "FOG_RE",
    "FOUNDER_JOURNAL_REASON",
    "FOUNDER_JOURNAL_RE",
    "LEAD_MAGNET_REASON",
    "LEAD_MAGNET_RE",
    "FOMO_REASON",
    "FOMO_RE",
    "MEME_REASON",
    "MEME_RE",
    "DECK_REASON",
    "DECK_RE",
    "DECK_HOSTS",
    "LINKTREE_REASON",
    "LINKTREE_RE",
    "LINKTREE_HOSTS",
    "LOGO_REVEAL_NOT_A_SHIP",
    "LOGO_REVEAL_RE",
    "PENDING_CI_RE",
    "FAILED_CI_RE",
    "PRERELEASE_RE",
    "SHIP_ARTIFACT_RE",
    "SHORTENER_HOSTS",
    "SOCIAL_ARENAS",
    "STACK_ARENAS",
    "STACK_HOURS",
    "SOURCE_AVAILABLE_LICENSE_RE",
    "STORE_HOSTS",
    "STORE_PITCH_RE",
    "SUPERLATIVE_RE",
    "TRYABLE_ARTIFACT_HOSTS",
    "UTM_FARM_RE",
    "CLICK_HERE_RE",
    "VIDEO_HOSTS",
    "WORLD_COMMENTARY_RE",
    "StoryKind",
    "Verdict",
    "WORKSHOP_STORY_KINDS",
    "X_REPLY_LIMIT",
    "arena_gate",
    "arena_play",
    "choose_arena",
    "agora_reason",
    "cafe_artifact_reason",
    "cafe_reason",
    "cinema_end_reason",
    "cinema_package_reason",
    "court_reason",
    "feedback_excerpt_texts",
    "fair_hook_reason",
    "fair_loop_reason",
    "has_agora_thought",
    "has_parent_post",
    "has_cafe_feed",
    "has_cafe_pack",
    "has_cinema_package",
    "has_court_insight",
    "has_fair_hook",
    "has_fair_loop",
    "has_letter_gift",
    "has_letter_surname",
    "has_monday_history",
    "has_named_subreddit",
    "has_quote_mark",
    "has_reddit_repo",
    "has_real_feedback",
    "has_tavern_intent_split",
    "has_tavern_seed",
    "has_workshop_life",
    "deck_urls_only",
    "linktree_urls_only",
    "is_blog_host_url",
    "is_deck_host_url",
    "is_linktree_host_url",
    "is_feedback_excerpt_fact",
    "is_launch_host_url",
    "is_merge_log_texts",
    "is_model_host_url",
    "is_news_host_url",
    "is_primary_arena",
    "is_private_channel_url",
    "is_public_issue_url",
    "is_ranking_host_url",
    "is_ship_artifact_url",
    "is_shortener_url",
    "is_social_arena",
    "is_stack_arena",
    "is_store_host_url",
    "is_tryable_artifact_url",
    "invented_metric_reason",
    "is_video_host_url",
    "looks_like_agora_echo",
    "looks_like_bot_author",
    "looks_like_bot_bump_week",
    "looks_like_commit_noise",
    "looks_like_court_launch",
    "looks_like_dunk",
    "looks_like_worse_clone",
    "looks_like_foreign_wave",
    "looks_like_reply",
    "is_parent_post_url",
    "PARENT_FACT_KINDS",
    "REPLY_SHAPE_RE",
    "looks_like_contest",
    "looks_like_poll",
    "looks_like_model_in_frame",
    "looks_like_ranking_dump",
    "looks_like_thread",
    "looks_like_engagement_bait",
    "looks_like_cinema_end",
    "looks_like_fair_cta",
    "looks_like_hashtag_wall",
    "looks_like_hire_fundraise",
    "looks_like_license_file",
    "looks_like_open_source_claim",
    "looks_like_open_source_without_license",
    "looks_like_source_available_as_oss",
    "looks_like_source_available_license",
    "ranking_urls_only",
    "looks_like_invented_opinion",
    "looks_like_person_mention",
    "looks_like_private_conversation",
    "looks_like_secret",
    "looks_like_world_commentary",
    "metric_tokens",
    "news_urls_only",
    "looks_like_listicle_title",
    "looks_like_merged_pr_fact",
    "looks_like_monday_without_history",
    "looks_like_version_diff",
    "looks_like_weekly_update",
    "looks_like_press_release",
    "looks_like_shouty_title",
    "looks_like_emoji_title",
    "looks_like_hn_title_overflow",
    "looks_like_linkedin_fold_overflow",
    "looks_like_x_overflow",
    "looks_like_superlative",
    "looks_like_tavern_invite",
    "show_hn_title_text",
    "tavern_reason",
    "looks_like_store_pitch",
    "looks_like_launch_pitch",
    "looks_like_letter_ask",
    "looks_like_letter_crush",
    "looks_like_letter_team_voice",
    "letter_reason",
    "looks_like_brand_voice",
    "looks_like_reddit_disclose",
    "looks_like_seminar_first_person",
    "reddit_reason",
    "seminar_reason",
    "looks_like_dead_link",
    "looks_like_dead_tls",
    "looks_like_dead_release_asset",
    "looks_like_dead_star_count",
    "looks_like_dead_star_story",
    "looks_like_issues_disabled",
    "looks_like_fork",
    "looks_like_empty_repo",
    "looks_like_private_repo",
    "looks_like_template",
    "looks_like_archived_repo",
    "looks_like_login_gate",
    "looks_like_shortener",
    "looks_like_utm_farm",
    "looks_like_click_here",
    "looks_like_server_splash",
    "looks_like_roadmap",
    "looks_like_event",
    "looks_like_calendar_filler",
    "looks_like_counter_thanks",
    "looks_like_fog",
    "looks_like_founder_journal",
    "looks_like_lead_magnet",
    "looks_like_fomo",
    "looks_like_meme",
    "looks_like_deck",
    "looks_like_linktree",
    "looks_like_logo_reveal",
    "looks_like_pending_ci",
    "looks_like_failed_ci",
    "looks_like_prerelease",
    "looks_like_waitlist",
    "parse_arena",
    "parse_stack_arena",
    "parse_stack_clock",
    "hn_camp_reason",
    "is_hn_camp_arena",
    "living_stack_arena",
    "stack_costume_reason",
    "quote_without_sourced_excerpt",
    "quoted_spans",
    "strip_open_source_claim",
    "strip_person_mentions",
    "unquotable_reason",
]
