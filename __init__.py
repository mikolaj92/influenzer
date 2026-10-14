from __future__ import annotations

from pathlib import Path

from influenzer import cli


SKILLS = (
    ("profile", "Manage one Project BrandProfile at a time."),
    ("content", "Create project-scoped immutable content revisions."),
    ("campaign", "Plan organic and paid campaigns without spend."),
    ("publish", "Inspect policy-gated publish plans and scheduler intent."),
    (
        "hom",
        "I am Influenzer. I use this skill whenever I choose an angle, an arena, "
        "or whether to ship a post at all.",
    ),
    ("x", "Play X: replies in rising threads, not a posting calendar."),
    ("linkedin", "Play LinkedIn: dwell and the ICP graph, not likes."),
    ("youtube", "Play YouTube long-form: packaging, retention, and Suggested."),
    ("shorts", "Play Shorts, TikTok, and Reels: hooks, completion, and loops."),
    ("github", "Play GitHub: README conversion and star velocity in a window."),
    ("hn", "Play Hacker News: a tryable Show HN with human backstory."),
    ("reddit", "Play Reddit: one named subreddit with its own rules."),
    ("newsletter", "Play the newsletter: an owned list, habit, and recommendations."),
    ("discord", "Play Discord: co-op structure, not member count."),
    ("bluesky", "Play Bluesky: niche packs, custom feeds, and artifact URLs."),
)


def register(ctx):
    ctx.register_cli_command(
        "influenzer",
        "Operate social profiles for apps and builders.",
        cli.setup_parser,
        cli.handle_cli,
        description="Local multi-project social operator",
    )
    base = Path(__file__).parent / "skills"
    for suffix, description in SKILLS:
        name = f"influenzer-{suffix}"
        ctx.register_skill(name, base / name / "SKILL.md", description=description)
