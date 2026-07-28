from __future__ import annotations

import json
from dataclasses import replace
from argparse import ArgumentParser, Namespace
from pathlib import Path
from typing import Any

from .collector import collect_cards
from .config import BuildInPublicConfig, ConfigError, load_config, resolve_config_path
from .renderer import draft_for_card
from .storage import load_cards, write_card, write_draft, write_weekly


QUALIFIED_SKILLS = [
    "build-in-public:build-card-capture",
    "build-in-public:build-card-to-x-post",
    "build-in-public:build-card-to-thread",
    "build-in-public:build-card-to-weekly-recap",
    "build-in-public:maintainer-narrative-policy",
]


def setup_parser(parser: ArgumentParser) -> None:
    parser.add_argument("--config", default=None)
    subparsers = parser.add_subparsers(dest="build_in_public_command")
    subparsers.required = True
    init = subparsers.add_parser("init")
    init.add_argument("--force", action="store_true")
    init.add_argument("--notes-dir", default="./notes")
    init.add_argument("--output-dir", default="./output")
    init.add_argument("--no-sample", action="store_true")
    subparsers.add_parser("validate")
    collect = subparsers.add_parser("collect")
    collect.add_argument("--live", action="store_true")
    collect.add_argument("--source", choices=["github", "kanban", "manual", "all"], default="all")
    collect.add_argument("--since", default=None)
    collect.add_argument("--limit", type=int, default=50)
    render = subparsers.add_parser("render")
    render.add_argument("--live", action="store_true")
    render.add_argument("--format", choices=["json", "markdown", "all"], default="all")
    weekly = subparsers.add_parser("weekly-recap")
    weekly.add_argument("--live", action="store_true")
    weekly.add_argument("--week", default=None)


def handle_cli(args: Namespace) -> int:
    try:
        result = run_from_args(args)
    except ConfigError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, indent=2, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def run_from_args(args: Namespace) -> dict[str, Any]:
    command = getattr(args, "build_in_public_command")
    if command == "init":
        return init_project(
            getattr(args, "config", None),
            str(getattr(args, "notes_dir", "./notes")),
            str(getattr(args, "output_dir", "./output")),
            bool(getattr(args, "force", False)),
            not bool(getattr(args, "no_sample", False)),
        )
    cfg = load_config(getattr(args, "config", None))
    if command == "validate":
        return validate(cfg)
    if command == "collect":
        return collect(cfg, bool(getattr(args, "live", False)), str(getattr(args, "source", "all")), int(getattr(args, "limit", 50)))
    if command == "render":
        return render(cfg, bool(getattr(args, "live", False)), str(getattr(args, "format", "all")))
    if command == "weekly-recap":
        return weekly_recap(cfg, bool(getattr(args, "live", False)), getattr(args, "week", None))
    raise ConfigError(f"unknown command: {command}")


def init_project(config_path: str | None, notes_dir: str, output_dir: str, force: bool, sample: bool) -> dict[str, Any]:
    target = resolve_config_path(config_path)
    if target.exists() and not force:
        raise ConfigError(f"config already exists: {target}; pass --force to overwrite")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(starter_config(notes_dir, output_dir), encoding="utf-8")
    created = [str(target)]
    if sample:
        note_path = Path(notes_dir).expanduser() / "demo.md"
        note_path.mkdir(parents=True, exist_ok=True) if note_path.suffix == "" else note_path.parent.mkdir(parents=True, exist_ok=True)
        if force or not note_path.exists():
            note_path.write_text(sample_note(), encoding="utf-8")
        created.append(str(note_path))
    config_arg = str(target)
    return {
        "ok": True,
        "config": config_arg,
        "created": created,
        "next_commands": [
            f"hermes build-in-public --config {config_arg} validate",
            f"hermes build-in-public --config {config_arg} collect --source manual --live",
            f"hermes build-in-public --config {config_arg} render --format all --live",
            f"hermes build-in-public --config {config_arg} weekly-recap --live",
        ],
        "safety": [
            "draft-only output",
            "local files only",
            "no social publishing",
            "social credential keys are rejected",
        ],
    }


def starter_config(notes_dir: str, output_dir: str) -> str:
    return "\n".join([
        "version: 1",
        "output_mode: draft-only",
        f"output_dir: {output_dir}",
        "maintainer: maintainer",
        "audience: OSS maintainers and builders",
        "sources:",
        "  github:",
        "    enabled: false",
        "    repos: []",
        "  kanban:",
        "    enabled: false",
        "  manual:",
        "    enabled: true",
        f"    path: {notes_dir}",
        "redaction:",
        "  enabled: true",
        "publish:",
        "  enabled: false",
        "",
    ])


def sample_note() -> str:
    return "\n".join([
        "# Demo Project",
        "",
        "Shipped a smaller onboarding path for a local-only build-in-public workflow.",
        "",
        "Problem: new users could not see value without setting up real integrations.",
        "Decision: start with one manual note and render local draft artifacts.",
        "Tradeoff: this demo is intentionally draft-only and should be reviewed before posting anywhere.",
        "",
    ])


def validate(cfg: BuildInPublicConfig) -> dict[str, Any]:
    return {
        "ok": True,
        "output_mode": cfg.output_mode,
        "output_dir": cfg.output_dir,
        "publish_enabled": False,
        "skills": QUALIFIED_SKILLS,
    }


def collect(cfg: BuildInPublicConfig, live_flag: bool, source: str, limit: int) -> dict[str, Any]:
    cards = collect_cards(cfg, source, limit)
    write = cfg.should_write(live_flag)
    paths = [str(write_card(cfg.output_path(), card)) for card in cards] if write else []
    return {
        "ok": True,
        "effective_write": write,
        "source": source,
        "count": len(cards),
        "planned_ids": [card.id for card in cards],
        "written": paths,
    }


def render(cfg: BuildInPublicConfig, live_flag: bool, format_name: str) -> dict[str, Any]:
    cards = load_cards(cfg.output_path()) if (cfg.output_path() / "cards").exists() else []
    write = cfg.should_write(live_flag)
    paths: list[str] = []
    rendered = []
    for card in cards:
        hydrated = card if card.drafts.x_short else replace(card, drafts=draft_for_card(card))
        rendered.append(hydrated.id)
        if write and format_name in {"markdown", "all"}:
            paths.append(str(write_draft(cfg.output_path(), hydrated)))
        if write and format_name in {"json", "all"}:
            paths.append(str(write_card(cfg.output_path(), hydrated)))
    return {"ok": True, "effective_write": write, "count": len(cards), "rendered_ids": rendered, "written": paths}


def weekly_recap(cfg: BuildInPublicConfig, live_flag: bool, week: str | None) -> dict[str, Any]:
    cards = load_cards(cfg.output_path()) if (cfg.output_path() / "cards").exists() else []
    write = cfg.should_write(live_flag)
    path = str(write_weekly(cfg.output_path(), cards, week)) if write else None
    return {"ok": True, "effective_write": write, "count": len(cards), "written": path}


def handle_kanban_task_completed(**kwargs: Any) -> None:
    _ = kwargs
    return None
