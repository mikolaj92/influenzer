"""Per-platform adapter process harness."""

from __future__ import annotations

from influenzer.adapters.base import AdapterRequest, AdapterResult, dry_run_publish, run_adapter
from influenzer.adapters.registry import ADAPTERS, get_adapter

__all__ = [
    "ADAPTERS",
    "AdapterRequest",
    "AdapterResult",
    "dry_run_publish",
    "get_adapter",
    "run_adapter",
]
