from __future__ import annotations

from .card import BuildCard, Drafts
from .redaction import redact_text


def draft_for_card(card: BuildCard) -> Drafts:
    project = redact_text(card.project)
    problem = redact_text(card.problem)
    decision = redact_text(card.decision)
    tradeoff = redact_text(card.tradeoff)
    short = f"Building {project}: {problem} → {decision}. Tradeoff: {tradeoff}"
    thread = [
        f"Build log for {project}",
        f"Problem: {problem}",
        f"Decision: {decision}",
        f"Tradeoff: {tradeoff}",
    ]
    weekly = f"{project}: {decision} ({tradeoff})"
    return Drafts(x_short=short[:280], x_thread=thread, weekly_recap_item=weekly)


def markdown_for_card(card: BuildCard) -> str:
    drafts = card.drafts if card.drafts.x_short else draft_for_card(card)
    thread = "\n".join(f"- {item}" for item in drafts.x_thread)
    return "\n".join(
        [
            f"# {card.project}",
            "",
            f"Status: {card.status}",
            f"Event: {card.event}",
            "",
            "## Short draft",
            drafts.x_short,
            "",
            "## Thread draft",
            thread,
            "",
            "## Weekly recap item",
            drafts.weekly_recap_item,
            "",
        ]
    )
