"""Immutable domain records and pure transitions."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping

from commercial_disclosure import (
    PAID_UNDISCLOSED_REASON,
    has_disclosure_label,
    looks_like_paid_promotion,
    paid_disclosure_reason,
)


class DomainError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(data: Mapping[str, Any] | list[Any] | str | int | float | bool | None) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(data: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json(data).encode("utf-8")).hexdigest()


_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def require_slug(value: str, field_name: str = "slug") -> str:
    if not _SLUG_RE.fullmatch(value):
        raise DomainError(f"{field_name} must be a lowercase slug")
    return value


class CampaignKind(str, Enum):
    ORGANIC = "organic"
    PAID = "paid"


class CampaignStatus(str, Enum):
    DRAFT = "draft"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class AccountStatus(str, Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    REAUTH_REQUIRED = "reauth_required"
    DISABLED = "disabled"


class PlanStatus(str, Enum):
    PROPOSED = "proposed"
    AWAITING_POLICY = "awaiting_policy"
    APPROVED = "approved"
    HANDOFF_READY = "handoff_ready"
    HANDOFF_OPENED = "handoff_opened"
    SCHEDULED = "scheduled"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILED_SUCCEEDED = "reconciled_succeeded"
    RECONCILED_ABSENT = "reconciled_absent"
    PUBLISHED_CONFIRMED = "published_confirmed"
    CANCELLED = "cancelled"


class AttemptStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    CANCELLED = "cancelled"


class ContentStatus(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    READY = "ready"
    ARCHIVED = "archived"


PLATFORMS = frozenset({"x", "bluesky", "mastodon", "linkedin", "instagram", "facebook_pages"})
PROJECT_KINDS = frozenset({"app", "personal", "builder"})


@dataclass(frozen=True)
class BrandProfile:
    """Per-project voice/profile. Each app and the builder has its own."""

    project_id: str
    display_name: str
    voice: str
    audience: str
    maintainer: str
    tone: str = "builder"
    disclosures: tuple[str, ...] = ()
    revision: int = 1
    profile_hash: str = ""

    def with_hash(self) -> "BrandProfile":
        payload = {
            "project_id": self.project_id,
            "display_name": self.display_name,
            "voice": self.voice,
            "audience": self.audience,
            "maintainer": self.maintainer,
            "tone": self.tone,
            "disclosures": list(self.disclosures),
            "revision": self.revision,
        }
        return BrandProfile(
            project_id=self.project_id,
            display_name=self.display_name,
            voice=self.voice,
            audience=self.audience,
            maintainer=self.maintainer,
            tone=self.tone,
            disclosures=self.disclosures,
            revision=self.revision,
            profile_hash=content_hash(payload),
        )


@dataclass(frozen=True)
class Project:
    project_id: str
    slug: str
    name: str
    created_at: str
    brand: BrandProfile
    kind: str = "app"  # app | personal | builder

    @staticmethod
    def create(
        *,
        project_id: str,
        slug: str,
        name: str,
        display_name: str,
        voice: str,
        audience: str,
        maintainer: str,
        tone: str = "builder",
        kind: str = "app",
        disclosures: tuple[str, ...] = (),
        created_at: str | None = None,
    ) -> "Project":
        require_slug(slug)
        if kind not in PROJECT_KINDS:
            raise DomainError("kind must be app|personal|builder")
        brand = BrandProfile(
            project_id=project_id,
            display_name=display_name,
            voice=voice,
            audience=audience,
            maintainer=maintainer,
            tone=tone,
            disclosures=disclosures,
        ).with_hash()
        return Project(
            project_id=project_id,
            slug=slug,
            name=name,
            created_at=created_at or utc_now(),
            brand=brand,
            kind=kind,
        )


@dataclass(frozen=True)
class ContentRevision:
    project_id: str
    content_id: str
    revision_id: str
    body: str
    kind: str  # post | thread_draft | recap
    status: ContentStatus
    source: str
    source_digest: str
    created_at: str
    content_hash: str = ""

    def with_hash(self) -> "ContentRevision":
        payload = {
            "project_id": self.project_id,
            "content_id": self.content_id,
            "revision_id": self.revision_id,
            "body": self.body,
            "kind": self.kind,
            "status": self.status.value,
            "source": self.source,
            "source_digest": self.source_digest,
            "created_at": self.created_at,
        }
        return ContentRevision(
            project_id=self.project_id,
            content_id=self.content_id,
            revision_id=self.revision_id,
            body=self.body,
            kind=self.kind,
            status=self.status,
            source=self.source,
            source_digest=self.source_digest,
            created_at=self.created_at,
            content_hash=content_hash(payload),
        )


@dataclass(frozen=True)
class PlatformAccount:
    project_id: str
    account_id: str
    platform: str
    handle: str
    host: str | None
    credential_ref: str
    status: AccountStatus
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.platform not in PLATFORMS:
            raise DomainError(f"unsupported platform: {self.platform}")
        if not self.credential_ref.startswith(("env:", "keychain:")):
            raise DomainError("credential_ref must be env:NAME or keychain:SERVICE/ACCOUNT")


@dataclass(frozen=True)
class PolicyVersion:
    project_id: str
    policy_version_id: str
    account_ids: tuple[str, ...]  # empty = all project accounts
    actions: tuple[str, ...]
    content_kinds: tuple[str, ...]
    max_posts_per_day: int
    require_disclosures: bool
    policy_hash: str = ""

    def with_hash(self) -> "PolicyVersion":
        payload = {
            "project_id": self.project_id,
            "policy_version_id": self.policy_version_id,
            "account_ids": list(self.account_ids),
            "actions": list(self.actions),
            "content_kinds": list(self.content_kinds),
            "max_posts_per_day": self.max_posts_per_day,
            "require_disclosures": self.require_disclosures,
        }
        return PolicyVersion(
            project_id=self.project_id,
            policy_version_id=self.policy_version_id,
            account_ids=self.account_ids,
            actions=self.actions,
            content_kinds=self.content_kinds,
            max_posts_per_day=self.max_posts_per_day,
            require_disclosures=self.require_disclosures,
            policy_hash=content_hash(payload),
        )


@dataclass(frozen=True)
class PolicyActivationGrant:
    project_id: str
    grant_id: str
    policy_version_id: str
    policy_hash: str
    platform_account_id: str | None
    actions: tuple[str, ...]
    actor: str
    created_at: str
    expires_at: str | None
    revoked_at: str | None = None

    def is_active(self, now: str, action: str) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and now >= self.expires_at:
            return False
        return action in self.actions


@dataclass(frozen=True)
class PublishPlan:
    project_id: str
    plan_id: str
    content_revision_id: str
    content_hash: str
    platform_account_id: str
    platform: str
    body: str
    status: PlanStatus
    scheduled_at: str | None
    created_at: str
    operation_key: str


@dataclass(frozen=True)
class PublicationAttempt:
    project_id: str
    attempt_id: str
    plan_id: str
    operation_key: str
    status: AttemptStatus
    created_at: str
    provider_id: str | None = None
    provider_url: str | None = None
    failure_class: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class Campaign:
    project_id: str
    campaign_id: str
    kind: CampaignKind
    name: str
    status: CampaignStatus
    budget_amount: float | None = None
    budget_currency: str | None = None
    disclosures: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.kind is CampaignKind.PAID:
            if self.budget_amount is None or self.budget_currency is None:
                raise DomainError("paid campaign requires budget_amount and budget_currency")
            if not has_disclosure_label(self.disclosures):
                raise DomainError("paid campaign requires a disclosure label")


# Re-export the dependency-free commercial-disclosure gate from the domain
# boundary for host callers. Collection packages import it directly so they
# remain independent of Influenzer.

ACTIVE_ATTEMPT = frozenset({AttemptStatus.PENDING, AttemptStatus.RUNNING, AttemptStatus.UNKNOWN})

PARKED_DOMAIN_REASON = "parked_domain_not_a_site"
_PARKED_DOMAIN_RE = re.compile(
    r"\b(?:"
    r"(?:this\s+)?domain(?:\s+name)?\s+(?:is\s+|may\s+be\s+)?(?:parked|for\s+sale|available\s+for\s+sale)"
    r"|(?:[a-z0-9-]+\.)+[a-z]{2,63}\s+(?:is\s+|may\s+be\s+)?(?:parked|for\s+sale|available\s+for\s+sale)"
    r"|parked\s+domain(?:\s+page)?"
    r"|(?:buy|purchase)\s+(?:this\s+)?domain"
    r"|domain\s+parking"
    r"|(?:zaparkowana\s+domena|domena\s+(?:jest\s+)?(?:zaparkowana|na\s+sprzedaż)|kup\s+(?:tę\s+)?domenę)"
    r"|(?:registrar|rejestrator|host(?:ing)?(?:\s+(?:provider|company))?)(?:'s)?\s+(?:placeholder|parking(?:\s+page)?|coming\s+soon(?:\s+page)?)"
    r"|(?:placeholder|parking(?:\s+page)?|coming\s+soon(?:\s+page)?)\s+(?:from|by|od)\s+(?:your\s+|the\s+)?(?:registrar|rejestratora|host(?:ing)?(?:\s+(?:provider|company))?|hosta)"
    r")\b",
    re.IGNORECASE,
)


def looks_like_parked_domain(value: str | None) -> bool:
    """Whether explicit registrar/host parking copy masquerades as a website.

    An unqualified product "coming soon" belongs to the waitlist gate. This
    guard only treats it as domain parking when the host or registrar is named.
    """
    return isinstance(value, str) and bool(_PARKED_DOMAIN_RE.search(value))


def parked_domain_reason(value: str | None) -> str | None:
    return PARKED_DOMAIN_REASON if looks_like_parked_domain(value) else None


FOREIGN_OWNER = "foreign_owner"
_GITHUB_LOGIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")


def github_owner(repo_slug: str) -> str | None:
    """Owner half of owner/name. A bad slug is not an owner."""
    if not isinstance(repo_slug, str):
        return None
    slug = repo_slug.strip()
    if slug.count("/") != 1:
        return None
    owner, name = slug.split("/", 1)
    if not owner or not name:
        return None
    return owner


def our_github_login(value: str | None) -> str | None:
    """Maintainer login, or None. Empty or not a GitHub login is silence."""
    if not isinstance(value, str):
        return None
    login = value.strip()
    if not login or not _GITHUB_LOGIN_RE.fullmatch(login):
        return None
    return login


def foreign_owner_reason(repo_slug: str, maintainer: str | None) -> str | None:
    """Watch/ship only on our GitHub. Owner must match the project maintainer.

    Missing login, missing owner, or a mismatch is silence, not a launch.
    Helping someone else's repo is contribute, not our ship angle.
    """
    ours = our_github_login(maintainer)
    owner = github_owner(repo_slug)
    if ours is None or owner is None:
        return FOREIGN_OWNER
    if ours.casefold() != owner.casefold():
        return FOREIGN_OWNER
    return None


def assert_same_project(project_id: str, *owned_project_ids: str) -> None:
    for owned in owned_project_ids:
        if owned != project_id:
            raise DomainError("cross-project reference denied")


def transition_plan(plan: PublishPlan, to: PlanStatus) -> PublishPlan:
    allowed: dict[PlanStatus, frozenset[PlanStatus]] = {
        PlanStatus.PROPOSED: frozenset({PlanStatus.AWAITING_POLICY, PlanStatus.APPROVED, PlanStatus.FAILED}),
        PlanStatus.AWAITING_POLICY: frozenset({PlanStatus.APPROVED, PlanStatus.FAILED}),
        PlanStatus.APPROVED: frozenset({PlanStatus.SCHEDULED, PlanStatus.HANDOFF_READY, PlanStatus.FAILED}),
        PlanStatus.SCHEDULED: frozenset({PlanStatus.EXECUTING, PlanStatus.FAILED, PlanStatus.CANCELLED}),
        PlanStatus.EXECUTING: frozenset({PlanStatus.SUCCEEDED, PlanStatus.FAILED, PlanStatus.UNKNOWN}),
        PlanStatus.HANDOFF_READY: frozenset({PlanStatus.HANDOFF_OPENED, PlanStatus.PUBLISHED_CONFIRMED, PlanStatus.FAILED}),
        PlanStatus.HANDOFF_OPENED: frozenset({PlanStatus.PUBLISHED_CONFIRMED, PlanStatus.FAILED}),
        PlanStatus.UNKNOWN: frozenset(
            {PlanStatus.RECONCILED_SUCCEEDED, PlanStatus.RECONCILED_ABSENT, PlanStatus.FAILED}
        ),
        PlanStatus.FAILED: frozenset(),
        PlanStatus.SUCCEEDED: frozenset(),
        PlanStatus.RECONCILED_SUCCEEDED: frozenset(),
        PlanStatus.PUBLISHED_CONFIRMED: frozenset(),
        PlanStatus.RECONCILED_ABSENT: frozenset({PlanStatus.SCHEDULED, PlanStatus.FAILED}),
        PlanStatus.CANCELLED: frozenset(),
    }
    if to not in allowed.get(plan.status, frozenset()):
        raise DomainError(f"illegal plan transition {plan.status.value} -> {to.value}")
    return PublishPlan(
        project_id=plan.project_id,
        plan_id=plan.plan_id,
        content_revision_id=plan.content_revision_id,
        content_hash=plan.content_hash,
        platform_account_id=plan.platform_account_id,
        platform=plan.platform,
        body=plan.body,
        status=to,
        scheduled_at=plan.scheduled_at,
        created_at=plan.created_at,
        operation_key=plan.operation_key,
    )


def transition_attempt(attempt: PublicationAttempt, to: AttemptStatus, **extra: Any) -> PublicationAttempt:
    allowed: dict[AttemptStatus, frozenset[AttemptStatus]] = {
        AttemptStatus.PENDING: frozenset({AttemptStatus.RUNNING, AttemptStatus.CANCELLED}),
        AttemptStatus.RUNNING: frozenset(
            {AttemptStatus.SUCCEEDED, AttemptStatus.FAILED, AttemptStatus.UNKNOWN}
        ),
        AttemptStatus.UNKNOWN: frozenset(
            {AttemptStatus.SUCCEEDED, AttemptStatus.FAILED, AttemptStatus.CANCELLED}
        ),
        AttemptStatus.SUCCEEDED: frozenset(),
        AttemptStatus.FAILED: frozenset(),
        AttemptStatus.CANCELLED: frozenset(),
    }
    if to not in allowed.get(attempt.status, frozenset()):
        raise DomainError(f"illegal attempt transition {attempt.status.value} -> {to.value}")
    data = asdict(attempt)
    data["status"] = to
    data.update(extra)
    return PublicationAttempt(**data)
