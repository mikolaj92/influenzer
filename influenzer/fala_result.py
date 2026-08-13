"""Fala subprocess organ contract. Effectors never open runtime.db."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping


def write_fala_result(
    payload: Mapping[str, Any],
    *,
    env: Mapping[str, str] | None = None,
    reaction_kind: str = "hom.decision",
) -> Path | None:
    """Write result.json when the host injected FALA_EFFECTOR_OUTPUT_DIR.

    Does not import or embed a Fala host. Domain state stays in state.db.
    """
    source = os.environ if env is None else env
    output_dir = source.get("FALA_EFFECTOR_OUTPUT_DIR")
    if not output_dir:
        return None
    path = Path(output_dir) / "result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    wrapped = {
        "values": dict(payload),
        "associations": [],
        "reactions": [
            {
                "kind": reaction_kind,
                "media_type": "application/json",
                "value": payload.get("operator", dict(payload)),
            }
        ],
        "metadata": {
            "published": False,
            "mutated": bool(payload.get("mutated")),
        },
    }
    path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return path


__all__ = ["write_fala_result"]
