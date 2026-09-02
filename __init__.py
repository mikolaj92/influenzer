from __future__ import annotations

from pathlib import Path

from influenzer import cli


def _registered_skills() -> tuple[tuple[str, Path, str], ...]:
    base = Path(__file__).parent / "skills"
    registered: list[tuple[str, Path, str]] = []
    for path in sorted(base.glob("influenzer-*/SKILL.md")):
        name = path.parent.name
        description = next(
            (
                line.strip()
                for line in path.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.startswith("#")
            ),
            name,
        )
        registered.append((name, path, description))
    return tuple(registered)


def register(ctx):
    ctx.register_cli_command(
        "influenzer",
        "Operate social profiles for apps and builders.",
        cli.setup_parser,
        cli.handle_cli,
        description="Local multi-project social operator",
    )
    for name, path, description in _registered_skills():
        ctx.register_skill(name, path, description=description)
