"""Pure, fail-closed authorization for live organic publication."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from .domain import (
    ContentRevision,
    PAID_UNDISCLOSED_REASON,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    paid_disclosure_reason,
)


@dataclass(frozen=True)
class PolicyDecision:
    """Authorization result; no evaluator call mutates state."""

    allowed: bool
    reason: str

    @property
    def ok(self) -> bool:
        return self.allowed

    def __bool__(self) -> bool:
        return self.allowed


def _deny(reason: str) -> PolicyDecision:
    return PolicyDecision(False, reason)


def _allow() -> PolicyDecision:
    return PolicyDecision(True, "allowed")


def _utc(value: datetime | str | None) -> datetime | None:
    """Parse an aware timestamp. Naive/malformed values fail closed."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return None
        return value.astimezone(timezone.utc)
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(timezone.utc)


def policy_hash(policy: PolicyVersion) -> str:
    """Compute the canonical hash, never trusting a serialized hash field."""
    return policy.with_hash().policy_hash


def _value(request: Mapping[str, Any] | None, key: str, value: Any) -> Any:
    return request[key] if request is not None and key in request else value


def _has_disclosure(value: Sequence[str] | str | None) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray)):
        return any(isinstance(item, str) and item.strip() for item in value)
    return False


def evaluate_policy(
    policy: PolicyVersion,
    grant: PolicyActivationGrant | None,
    *,
    project_id: str | None = None,
    account_id: str | None = None,
    content_hash: str | None = None,
    content_kind: str | None = None,
    body: str | None = None,
    action: str = "publish",
    disclosures: Sequence[str] | str | None = (),
    live_intent: bool = False,
    scheduler: bool = False,
    scheduler_live_enabled: bool = False,
    posts_today: int = 0,
    now: datetime | str | None = None,
    expected_content_hash: str | None = None,
    account: PlatformAccount | None = None,
    content: ContentRevision | None = None,
    request: Mapping[str, Any] | None = None,
) -> PolicyDecision:
    """Evaluate one live publish request without I/O or mutation.

    A one-shot command must pass ``live_intent=True``. For a scheduler call,
    set ``scheduler=True``; the CLI live flag is then deliberately ignored and
    only the durable ``scheduler_live_enabled`` setting is authoritative.
    ``expected_content_hash`` is the hash captured by the plan/reservation.
    ``now`` is required and injectable so expiry and rate decisions are stable.
    A request mapping is supported for boundary callers and cannot relax any
    checks.
    """
    project_id = _value(request, "project_id", project_id)
    account_id = _value(request, "account_id", account_id)
    content_hash = _value(request, "content_hash", content_hash)
    content_kind = _value(request, "content_kind", content_kind)
    body = _value(request, "body", body)
    action = _value(request, "action", action)
    disclosures = _value(request, "disclosures", disclosures)
    live_intent = _value(request, "live_intent", live_intent)
    scheduler = _value(request, "scheduler", scheduler)
    scheduler_live_enabled = _value(request, "scheduler_live_enabled", scheduler_live_enabled)
    posts_today = _value(request, "posts_today", posts_today)
    now = _value(request, "now", now)
    expected_content_hash = _value(request, "expected_content_hash", expected_content_hash)

    if not isinstance(policy, PolicyVersion) or not isinstance(
        grant, (PolicyActivationGrant, type(None))
    ):
        return _deny("invalid_policy_input")
    if not all(isinstance(v, str) and v for v in (project_id, account_id, content_hash, content_kind, action)):
        return _deny("missing_binding")
    if body is not None and not isinstance(body, str):
        return _deny("invalid_content")
    if not all(isinstance(v, bool) for v in (live_intent, scheduler, scheduler_live_enabled)):
        return _deny("invalid_live_intent")
    if not isinstance(posts_today, int) or isinstance(posts_today, bool) or posts_today < 0:
        return _deny("invalid_rate_count")
    moment = _utc(now)
    if moment is None:
        return _deny("invalid_clock")

    if project_id != policy.project_id:
        return _deny("project_mismatch")
    if account is not None:
        if not isinstance(account, PlatformAccount):
            return _deny("invalid_account")
        if account.project_id != project_id or account.account_id != account_id:
            return _deny("account_mismatch")
        if account.status.value != "connected":
            return _deny("account_not_connected")
    if content is not None:
        if not isinstance(content, ContentRevision):
            return _deny("invalid_content")
        if (
            content.project_id != project_id
            or content.content_hash != content_hash
            or content.kind != content_kind
        ):
            return _deny("content_mismatch")
    if expected_content_hash is not None and expected_content_hash != content_hash:
        return _deny("stale_content_hash")

    # A policy must be explicitly hash-bound; recomputing protects against a
    # tampered or stale persisted policy_hash.
    try:
        canonical_hash = policy_hash(policy)
    except Exception:
        return _deny("invalid_policy")
    if not policy.policy_hash or policy.policy_hash != canonical_hash:
        return _deny("stale_policy_hash")

    if grant is None:
        return _deny("grant_required")
    if grant.project_id != project_id:
        return _deny("grant_project_mismatch")
    if grant.policy_version_id != policy.policy_version_id:
        return _deny("grant_policy_mismatch")
    if grant.policy_hash != canonical_hash:
        return _deny("grant_policy_hash_mismatch")
    if grant.platform_account_id is not None and grant.platform_account_id != account_id:
        return _deny("grant_account_mismatch")
    if not isinstance(grant.actions, tuple) or action not in grant.actions:
        return _deny("grant_action_denied")
    created = _utc(grant.created_at)
    if created is None:
        return _deny("invalid_grant_created_at")
    if moment < created:
        return _deny("grant_not_yet_active")
    if grant.revoked_at is not None:
        return _deny("grant_revoked")
    if grant.expires_at is not None:
        expires = _utc(grant.expires_at)
        if expires is None:
            return _deny("invalid_grant_expiry")
        if moment >= expires:
            return _deny("grant_expired")

    if not isinstance(policy.account_ids, tuple) or (
        policy.account_ids and account_id not in policy.account_ids
    ):
        return _deny("policy_account_denied")
    if not isinstance(policy.actions, tuple) or action not in policy.actions:
        return _deny("policy_action_denied")
    if not isinstance(policy.content_kinds, tuple) or content_kind not in policy.content_kinds:
        return _deny("content_kind_denied")
    if (
        not isinstance(policy.max_posts_per_day, int)
        or isinstance(policy.max_posts_per_day, bool)
        or policy.max_posts_per_day < 0
    ):
        return _deny("invalid_policy_rate")
    if posts_today >= policy.max_posts_per_day:
        return _deny("daily_rate_exceeded")
    if policy.require_disclosures and not _has_disclosure(disclosures):
        return _deny("disclosure_required")
    copy = content.body if content is not None else body
    if paid_disclosure_reason(copy):
        return _deny(PAID_UNDISCLOSED_REASON)

    # A scheduler's CLI invocation may contain --live, but it is never enough.
    if scheduler:
        if not scheduler_live_enabled:
            return _deny("scheduler_live_disabled")
    elif not live_intent:
        return _deny("live_intent_required")

    return _allow()


# Explicit aliases keep the pure decision API discoverable without introducing
# alternate product or legacy namespaces.
decide_publish = evaluate_policy
evaluate = evaluate_policy

__all__ = [
    "PolicyDecision",
    "decide_publish",
    "evaluate",
    "evaluate_policy",
    "policy_hash",
]
