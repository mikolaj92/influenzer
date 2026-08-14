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
            "Do not flood originals into an empty feed. Not a hashtag catalog.",
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
            "Zero-click: insight in the post. No pitch in line one, no hashtag wall.",
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
            "Repo is the website. README one screen: one-liner → GIF → working quickstart. No shouty CAPS title, no emoji.",
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
            "Title starts with Show HN and a working demo. No waitlist, no blog-as-Show, no store-as-Show, no ranking dump, no listicle, no shouty CAPS, no emoji.",
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

WAITLIST_RE = re.compile(
    r"(?i)\b(?:waitlist|coming soon|join the (?:beta|waitlist)|landing page|no demo)\b"
)
PRESS_RELEASE_RE = re.compile(
    r"(?i)\b(?:excited to announce|humbled to announce|we are (?:excited|pleased|proud) to|"
    r"game[- ]changer|revolutionary|disrupt(?:ing|s)? the)\b"
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
SUBREDDIT_RE = re.compile(r"\br/[A-Za-z0-9_]+\b")
CINEMA_PACKAGE_RE = re.compile(r"(?i)\b(?:title|thumb(?:nail)?|package|poster|0\.5s)\b")
FAIR_HOOK_RE = re.compile(r"(?i)\b(?:hook|loop|1-3s|first (?:frame|second|3s))\b")
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


def _http_host(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def _host_in(url: str | None, names: frozenset[str]) -> bool:
    host = _http_host(url)
    if not host:
        return False
    return any(host == name or host.endswith("." + name) for name in names)


def is_video_host_url(url: str | None) -> bool:
    """True for a YouTube/Vimeo/Loom URL. A film is not a tryable demo."""
    return _host_in(url, VIDEO_HOSTS)


def is_store_host_url(url: str | None) -> bool:
    """True for an App Store / Play / TestFlight URL. A store is not a tryable demo."""
    return _host_in(url, STORE_HOSTS)


def is_blog_host_url(url: str | None) -> bool:
    """True for a Medium / Substack / dev.to / hashnode URL. A blog is not a tryable demo."""
    return _host_in(url, BLOG_HOSTS)


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
    """Silence reason when a quote, 'users love', a gesture ask, a contest, a 1/n serial, a ranking dump, a tag wall, a summon, a private conversation, or a number is not in the brief."""
    packed = tuple(facts)
    excerpts = feedback_excerpt_texts(packed)
    operator_texts = [
        text for kind, text, url in packed if not is_feedback_excerpt_fact(kind, url)
    ]
    for _kind, text, url in packed:
        if looks_like_private_conversation(text) or is_private_channel_url(url):
            return "private_conversation"
    if extra and (
        looks_like_private_conversation(extra) or is_private_channel_url(extra)
    ):
        return "private_conversation"
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
    "BLOG_HOSTS",
    "CANON_URL",
    "COMMIT_NOISE_RE",
    "DUNK_NAMED_RE",
    "DUNK_PHRASE_RE",
    "CONTEST_RE",
    "THREAD_NUMBER_RE",
    "THREAD_WORD_RE",
    "ENGAGEMENT_BAIT_RE",
    "HASHTAG_RE",
    "HN_STORY_KINDS",
    "MAX_HASHTAGS",
    "MENTION_RE",
    "FEEDBACK_EXCERPT_KINDS",
    "INVENTED_OPINION_RE",
    "LISTICLE_TITLE_RE",
    "METRIC_TOKEN_RE",
    "MERGED_PR_FACT_RE",
    "MIN_FACT_CHARS",
    "MIN_SOCIAL_FACTS",
    "NEWSLETTER_STORY_KINDS",
    "PRIVATE_CHANNEL_HOSTS",
    "PRIVATE_CONVERSATION_RE",
    "QUOTE_MARKS",
    "RANKING_DUMP_RE",
    "RANKING_HOSTS",
    "SHIP_ARTIFACT_RE",
    "SOCIAL_ARENAS",
    "STORE_HOSTS",
    "STORE_PITCH_RE",
    "SUPERLATIVE_RE",
    "VIDEO_HOSTS",
    "StoryKind",
    "Verdict",
    "WORKSHOP_STORY_KINDS",
    "arena_gate",
    "arena_play",
    "feedback_excerpt_texts",
    "has_cinema_package",
    "has_fair_hook",
    "has_named_subreddit",
    "has_quote_mark",
    "is_blog_host_url",
    "is_feedback_excerpt_fact",
    "is_merge_log_texts",
    "is_private_channel_url",
    "is_public_issue_url",
    "is_ranking_host_url",
    "is_ship_artifact_url",
    "is_social_arena",
    "is_store_host_url",
    "invented_metric_reason",
    "is_video_host_url",
    "looks_like_commit_noise",
    "looks_like_dunk",
    "looks_like_foreign_wave",
    "looks_like_reply",
    "is_parent_post_url",
    "PARENT_FACT_KINDS",
    "REPLY_SHAPE_RE",
    "looks_like_contest",
    "looks_like_ranking_dump",
    "looks_like_thread",
    "looks_like_engagement_bait",
    "looks_like_hashtag_wall",
    "ranking_urls_only",
    "looks_like_invented_opinion",
    "looks_like_person_mention",
    "looks_like_private_conversation",
    "metric_tokens",
    "looks_like_listicle_title",
    "looks_like_merged_pr_fact",
    "looks_like_press_release",
    "looks_like_shouty_title",
    "looks_like_emoji_title",
    "looks_like_superlative",
    "looks_like_store_pitch",
    "looks_like_waitlist",
    "parse_arena",
    "quote_without_sourced_excerpt",
    "quoted_spans",
    "strip_person_mentions",
    "unquotable_reason",
]
