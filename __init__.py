from __future__ import annotations

from pathlib import Path

from . import commands


SKILLS = (
    ("build-card-capture", "Capture project activity as a build card."),
    ("build-card-to-x-post", "Render a short draft post from a build card."),
    ("build-card-to-thread", "Render a draft thread from a build card."),
    ("build-card-to-weekly-recap", "Render weekly recap items from build cards."),
    ("maintainer-narrative-policy", "Keep drafts grounded in maintainer narrative."),
)


def register(ctx):
    ctx.register_cli_command(
        "build-in-public",
        "Create draft-only build cards and narrative artifacts.",
        commands.setup_parser,
        commands.handle_cli,
        description="Draft-only build-in-public automation",
    )
    base = Path(__file__).parent / "skills"
    for name, description in SKILLS:
        ctx.register_skill(name, base / name / "SKILL.md", description=description)
    if hasattr(ctx, "register_hook"):
        ctx.register_hook("kanban_task_completed", commands.handle_kanban_task_completed)
