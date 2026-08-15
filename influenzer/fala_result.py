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
    The reaction dir is a journal: observation, not the owner of history.
    A pad there does not raise, does not roll back score/draft, and does
    not kill the organ or the always-on loop. Domain wins.
    """
    source = os.environ if env is None else env
    output_dir = source.get("FALA_EFFECTOR_OUTPUT_DIR")
    if not output_dir:
        return None
    path = Path(output_dir) / "result.json"
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
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(wrapped, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    except OSError:
        return None
    return path


__all__ = ["write_fala_result"]
