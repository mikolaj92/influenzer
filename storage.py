from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

from .card import BuildCard, Drafts, Source, validate_card
from .renderer import draft_for_card, markdown_for_card


def ensure_dirs(output_dir: Path) -> None:
    for name in ("cards", "drafts", "weekly"):
        (output_dir / name).mkdir(parents=True, exist_ok=True)


def write_card(output_dir: Path, card: BuildCard) -> Path:
    ensure_dirs(output_dir)
    drafts = card.drafts if card.drafts.x_short else draft_for_card(card)
    hydrated = replace(card, drafts=drafts)
    data = hydrated.to_dict()
    validate_card(data)
    path = output_dir / "cards" / f"{card.id}.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def write_draft(output_dir: Path, card: BuildCard) -> Path:
    ensure_dirs(output_dir)
    path = output_dir / "drafts" / f"{card.id}.md"
    path.write_text(markdown_for_card(card), encoding="utf-8")
    return path


def load_cards(output_dir: Path) -> list[BuildCard]:
    cards: list[BuildCard] = []
    for path in sorted((output_dir / "cards").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        validate_card(data)
        source = Source(**data["source"])
        drafts = Drafts(**data["drafts"])
        cards.append(
            BuildCard(
                id=data["id"],
                project=data["project"],
                event=data["event"],
                post_type=data["post_type"],
                problem=data["problem"],
                decision=data["decision"],
                tradeoff=data["tradeoff"],
                before=data.get("before"),
                after=data.get("after"),
                open_question=data.get("open_question"),
                audience=data["audience"],
                status=data["status"],
                created_at=data["created_at"],
                source=source,
                drafts=drafts,
            )
        )
    return cards


def write_weekly(output_dir: Path, cards: list[BuildCard], week: str | None = None) -> Path:
    ensure_dirs(output_dir)
    week_id = week or f"{date.today().isocalendar().year}-W{date.today().isocalendar().week:02d}"
    lines = [f"# Weekly OSS build recap {week_id}", ""]
    for card in cards:
        drafts = card.drafts if card.drafts.weekly_recap_item else draft_for_card(card)
        lines.append(f"- {drafts.weekly_recap_item}")
    path = output_dir / "weekly" / f"{week_id}.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
