"""Result envelope shared by operator steps and adapters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

Request = Mapping[str, Any]
Result = dict[str, Any]


def result(
    *,
    status: str,
    ok: bool = True,
    mutated: bool = False,
    dry_run: bool | None = None,
    reason: str | None = None,
    **extra: Any,
) -> Result:
    out: Result = {"status": status, "ok": ok, "mutated": mutated}
    if dry_run is not None:
        out["dry_run"] = dry_run
    if reason is not None:
        out["reason"] = reason
    out.update(extra)
    return out


def ok(status: str = "ok", **extra: Any) -> Result:
    return result(status=status, ok=True, **extra)


def planned(**extra: Any) -> Result:
    return result(status="planned", ok=True, dry_run=True, mutated=False, **extra)


def noop(reason: str, **extra: Any) -> Result:
    return result(status="noop", ok=True, mutated=False, reason=reason, **extra)


def fail(
    reason: str,
    *,
    failure_class: str = "terminal",
    retry_safe: bool = False,
    mutated: bool = False,
    **extra: Any,
) -> Result:
    return result(
        status="failed",
        ok=False,
        mutated=mutated,
        reason=reason,
        failure_class=failure_class,
        retry_safe=retry_safe,
        **extra,
    )


def input_of(request: Request) -> dict[str, Any]:
    value = request.get("input")
    return dict(value) if isinstance(value, Mapping) else {}


def cfg_of(request: Request) -> dict[str, Any]:
    value = request.get("config")
    return dict(value) if isinstance(value, Mapping) else {}
