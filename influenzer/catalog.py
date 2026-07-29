"""Explicit allowlist for Influenzer effectors."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from importlib import import_module
from typing import Any, Callable


@dataclass(frozen=True)
class EffectorEntry:
    name: str
    handler_ref: str
    description: str


# This list is intentionally tiny until real domain handlers are added.  A
# manifest may only select a handler named here; dotted imports are never
# accepted directly from untrusted input.
EFFECTORS: tuple[EffectorEntry, ...] = (
    EffectorEntry("noop", "influenzer.effector.noop", "Do nothing."),
    EffectorEntry("echo", "influenzer.effector.echo", "Return the request payload."),
)

_BY_NAME = {entry.name: entry for entry in EFFECTORS}


def list_effectors() -> list[dict[str, str]]:
    return [asdict(entry) for entry in EFFECTORS]


def resolve(name: str) -> Callable[[dict[str, Any]], Any]:
    """Resolve an allowlisted process-local handler by name."""

    if not isinstance(name, str) or name not in _BY_NAME:
        raise ValueError("unknown handler")
    module_name, separator, attribute = _BY_NAME[name].handler_ref.rpartition(".")
    if not separator:
        raise ValueError("malformed handler reference")
    try:
        handler = getattr(import_module(module_name), attribute)
    except (ImportError, AttributeError) as exc:
        raise ValueError("handler unavailable") from exc
    if not callable(handler):
        raise TypeError("handler is not callable")
    return handler


def entry_for(name: str) -> EffectorEntry | None:
    return _BY_NAME.get(name)


__all__ = ["EFFECTORS", "EffectorEntry", "entry_for", "list_effectors", "resolve"]
