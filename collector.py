from __future__ import annotations

from pathlib import Path
from typing import Any

from .card import BuildCard, new_card_from_event
from .config import BuildInPublicConfig


def event_to_card(event: dict[str, Any], cfg: BuildInPublicConfig) -> BuildCard:
    return new_card_from_event(event, cfg.audience)


def manual_events(cfg: BuildInPublicConfig, limit: int) -> list[dict[str, Any]]:
    source = cfg.sources.manual
    if not source.enabled or not source.path:
        return []
    root = Path(source.path).expanduser()
    if not root.exists() or not root.is_dir():
        return []
    events: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.md"))[:limit]:
        text = path.read_text(encoding="utf-8")
        title = next((line.strip("# ").strip() for line in text.splitlines() if line.strip()), path.stem)
        events.append(
            {
                "source_kind": "manual",
                "event_id": path.stem,
                "project": title,
                "event": "manual-note",
                "problem": title,
                "decision": text.strip()[:400] or title,
                "tradeoff": "Manual note; review before publishing anywhere.",
            }
        )
    return events


def collect_cards(cfg: BuildInPublicConfig, source: str, limit: int) -> list[BuildCard]:
    events: list[dict[str, Any]] = []
    if source in {"manual", "all"}:
        events.extend(manual_events(cfg, limit))
    return [event_to_card(event, cfg) for event in events[:limit]]
