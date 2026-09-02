"""Provider-neutral bounded payload size helpers for acquisition blocks."""

from __future__ import annotations

import json

MAX_GH_LOOK_BYTES = 1 * 1024 * 1024
MAX_STATE_BYTES = 50 * 1024 * 1024


def payload_byte_size(blob: object) -> int:
    if blob is None:
        return 0
    if isinstance(blob, (bytes, bytearray)):
        return len(blob)
    if isinstance(blob, str):
        return len(blob.encode("utf-8"))
    try:
        return len(json.dumps(blob, ensure_ascii=False).encode("utf-8"))
    except (TypeError, ValueError, OverflowError):
        return MAX_STATE_BYTES + 1


def look_bytes_over_limit(blob: object, *, limit: int | None = None) -> bool:
    cap = MAX_GH_LOOK_BYTES if limit is None else limit
    return payload_byte_size(blob) > cap


def state_bytes_over_limit(blob: object) -> bool:
    return payload_byte_size(blob) > MAX_STATE_BYTES
