from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import date
from typing import Any


class CardError(ValueError):
    pass


@dataclass(frozen=True)
class Source:
    kind: str
    repo: str | None = None
    number: int | None = None
    url: str | None = None
    event_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "repo": self.repo,
            "number": self.number,
            "url": self.url,
            "event_id": self.event_id,
        }


@dataclass(frozen=True)
class Drafts:
    x_short: str = ""
    x_thread: list[str] = field(default_factory=list)
    weekly_recap_item: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "x_short": self.x_short,
            "x_thread": list(self.x_thread),
            "weekly_recap_item": self.weekly_recap_item,
        }


@dataclass(frozen=True)
class BuildCard:
    id: str
    project: str
    event: str
    post_type: str
    problem: str
    decision: str
    tradeoff: str
    before: str | None
    after: str | None
    open_question: str | None
    audience: str
    status: str
    created_at: str
    source: Source
    drafts: Drafts = field(default_factory=Drafts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "project": self.project,
            "event": self.event,
            "post_type": self.post_type,
            "problem": self.problem,
            "decision": self.decision,
            "tradeoff": self.tradeoff,
            "before": self.before,
            "after": self.after,
            "open_question": self.open_question,
            "audience": self.audience,
            "status": self.status,
            "created_at": self.created_at,
            "source": self.source.to_dict(),
            "drafts": self.drafts.to_dict(),
        }


def stable_id(source_kind: str, repo: str | None, event_kind: str, number_or_date: str, content: str) -> str:
    repo_slug = (repo or "manual").replace("/", "-").lower()
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()[:10]
    return f"{source_kind}-{repo_slug}-{event_kind}-{number_or_date}-{digest}"


def validate_card(data: dict[str, Any]) -> None:
    required = {
        "id",
        "project",
        "event",
        "post_type",
        "problem",
        "decision",
        "tradeoff",
        "audience",
        "status",
        "created_at",
        "source",
        "drafts",
    }
    extra = set(data) - (required | {"before", "after", "open_question"})
    missing = required - set(data)
    if missing:
        raise CardError(f"missing fields: {sorted(missing)}")
    if extra:
        raise CardError(f"unexpected fields: {sorted(extra)}")
    if data["status"] not in {"draft", "reviewed", "published-manual", "archived"}:
        raise CardError("unsupported status")
    if not isinstance(data["source"], dict) or not isinstance(data["drafts"], dict):
        raise CardError("source and drafts must be objects")
    for key in required - {"source", "drafts"}:
        if not isinstance(data[key], str):
            raise CardError(f"{key} must be a string")
    for key in ("before", "after", "open_question"):
        if key in data and data[key] is not None and not isinstance(data[key], str):
            raise CardError(f"{key} must be a string or null")
    source_keys = {"kind", "repo", "number", "url", "event_id"}
    if set(data["source"]) != source_keys:
        raise CardError("source has unsupported fields")
    if not isinstance(data["source"]["kind"], str):
        raise CardError("source.kind must be a string")
    for key in ("repo", "url", "event_id"):
        if data["source"][key] is not None and not isinstance(data["source"][key], str):
            raise CardError(f"source.{key} must be a string or null")
    if data["source"]["number"] is not None and not isinstance(data["source"]["number"], int):
        raise CardError("source.number must be an integer or null")
    draft_keys = {"x_short", "x_thread", "weekly_recap_item"}
    if set(data["drafts"]) != draft_keys:
        raise CardError("drafts has unsupported fields")
    if not isinstance(data["drafts"]["x_short"], str):
        raise CardError("drafts.x_short must be a string")
    if not isinstance(data["drafts"]["weekly_recap_item"], str):
        raise CardError("drafts.weekly_recap_item must be a string")
    if not isinstance(data["drafts"]["x_thread"], list) or not all(isinstance(item, str) for item in data["drafts"]["x_thread"]):
        raise CardError("drafts.x_thread must be a list of strings")


def new_card_from_event(event: dict[str, Any], audience: str) -> BuildCard:
    source = Source(
        kind=str(event.get("source_kind", "manual")),
        repo=event.get("repo"),
        number=event.get("number"),
        url=event.get("url"),
        event_id=event.get("event_id"),
    )
    project = str(event.get("project") or event.get("repo") or "project")
    event_name = str(event.get("event") or "progress")
    number_or_date = str(event.get("number") or event.get("date") or date.today().isoformat())
    content = "|".join(str(event.get(key, "")) for key in ("project", "event", "problem", "decision", "tradeoff"))
    card_id = stable_id(source.kind, source.repo, event_name, number_or_date, content)
    return BuildCard(
        id=card_id,
        project=project,
        event=event_name,
        post_type=str(event.get("post_type", "build-log")),
        problem=str(event.get("problem", "What changed?")),
        decision=str(event.get("decision", "Record the decision before publishing.")),
        tradeoff=str(event.get("tradeoff", "Tradeoff not captured yet.")),
        before=event.get("before"),
        after=event.get("after"),
        open_question=event.get("open_question"),
        audience=audience,
        status="draft",
        created_at=str(event.get("date") or date.today().isoformat()),
        source=source,
    )
