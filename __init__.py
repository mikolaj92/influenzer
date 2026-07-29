from __future__ import annotations

from pathlib import Path

from influenzer import cli


SKILLS = (
    ("profile", "Manage one app or builder BrandProfile."),
    ("content", "Create project-scoped social content."),
    ("campaign", "Plan organic and paid campaigns without spend."),
    ("publish", "Inspect policy-gated publish plans."),
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
    for name, description in SKILLS:
        path = base / f"influenzer-{name}" / "SKILL.md"
        ctx.register_skill(f"influenzer-{name}", path, description=description)
