"""Dry-run-first adapter request/result contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from influenzer.domain import PAID_UNDISCLOSED_REASON, paid_disclosure_reason
from influenzer.envelope import fail, planned, result


@dataclass(frozen=True)
class AdapterRequest:
    platform: str
    project_id: str
    account_id: str
    body: str
    operation_key: str
    dry_run: bool = True
    host: str | None = None
    media: tuple[str, ...] = ()
    credential_ref: str | None = None


AdapterResult = dict[str, Any]
Handler = Callable[[AdapterRequest], AdapterResult]


def dry_run_publish(request: AdapterRequest, *, planned_id: str | None = None) -> AdapterResult:
    if not request.dry_run:
        return fail("live path requires explicit platform handler", failure_class="terminal")
    return planned(
        platform=request.platform,
        project_id=request.project_id,
        account_id=request.account_id,
        operation_key=request.operation_key,
        planned_id=planned_id or f"dryrun:{request.platform}:{request.operation_key}",
        body_chars=len(request.body),
        media_count=len(request.media),
    )


def run_adapter(handler: Handler, request: AdapterRequest) -> AdapterResult:
    if paid_disclosure_reason(request.body):
        return fail(PAID_UNDISCLOSED_REASON, failure_class="terminal")
    if request.dry_run:
        # Harness guarantees no secret material is required for dry-run.
        safe = AdapterRequest(
            platform=request.platform,
            project_id=request.project_id,
            account_id=request.account_id,
            body=request.body,
            operation_key=request.operation_key,
            dry_run=True,
            host=request.host,
            media=request.media,
            credential_ref=None,
        )
        out = handler(safe)
    else:
        out = handler(request)
    if not isinstance(out, Mapping):
        return fail("adapter returned non-object", failure_class="terminal")
    data = dict(out)
    if "status" not in data or "ok" not in data or "mutated" not in data:
        return fail("adapter envelope incomplete", failure_class="terminal", raw_status=data.get("status"))
    if request.dry_run and data.get("mutated") is True:
        return fail("dry-run adapter claimed mutation", failure_class="terminal")
    if request.dry_run:
        data.setdefault("dry_run", True)
    return result(**data) if set(data) - {"status", "ok", "mutated", "dry_run", "reason"} else dict(data)
