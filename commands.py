from __future__ import annotations

import json
from dataclasses import replace
from argparse import ArgumentParser, Namespace
from typing import Any

from .collector import collect_cards
from .config import BuildInPublicConfig, ConfigError, load_config
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
    cfg = load_config(getattr(args, "config", None))
    command = getattr(args, "build_in_public_command")
    if command == "validate":
        return validate(cfg)
    if command == "collect":
        return collect(cfg, bool(getattr(args, "live", False)), str(getattr(args, "source", "all")), int(getattr(args, "limit", 50)))
    if command == "render":
        return render(cfg, bool(getattr(args, "live", False)), str(getattr(args, "format", "all")))
    if command == "weekly-recap":
        return weekly_recap(cfg, bool(getattr(args, "live", False)), getattr(args, "week", None))
    raise ConfigError(f"unknown command: {command}")


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
