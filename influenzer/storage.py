"""Host-owned SQLite persistence and content-addressed artifacts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Iterator, Mapping

from .domain import (
    BrandProfile, Campaign, CampaignKind, CampaignStatus, ContentRevision, ContentStatus,
    PlatformAccount, PolicyActivationGrant, PolicyVersion, Project, PublishPlan,
    PublicationAttempt, AccountStatus, PlanStatus, AttemptStatus,
)
from .domain import content_hash
from .hom import Brief, Draft, Score, brief_to_mapping, parse_facts_json
from .migrations import MigrationError, migrate
from .playbook import ArenaId, StoryKind, Verdict


class StorageError(RuntimeError):
    """Base class for persistence failures."""


class ArtifactCorruptionError(StorageError):
    """An artifact's bytes no longer match its content address."""


STATE_UNUSABLE = "state_unusable"
_SQLITE_HEADER = b"SQLite format 3\x00"


class StateUnusable(StorageError):
    """Existing state.db is bad or not writable.

    Do not wipe. Do not replace it with an empty CMO. Recovery is a human.
    """


class CrossProjectError(StorageError):
    """A relationship attempts to cross a project boundary."""


class UnboundSqlError(StorageError):
    """SQL was assembled from inbound text instead of bind parameters."""


_SQL_DML = re.compile(r"\b(SELECT|INSERT|UPDATE|DELETE)\b", re.IGNORECASE)
_SQL_MUTATION = re.compile(r"\b(DROP|ALTER|ATTACH|DETACH)\b", re.IGNORECASE)
_SQL_COMMENT = re.compile(r"(--|/\*)")
_SQL_STACKED = re.compile(
    r";\s*(SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|PRAGMA|CREATE)\b",
    re.IGNORECASE,
)
_SQL_QUOTED = re.compile(r"'([^']*)'")
_STATIC_SQL_LITERALS = frozenset({"", "now", "hold", "pending", "processed", "schema_version"})


def _quoted_literal_is_inbound(literal: str) -> bool:
    """True for a quoted value that looks like a slug, excerpt, or JSON payload."""
    if literal in _STATIC_SQL_LITERALS:
        return False
    if "/" in literal or any(ch in literal for ch in "{}[]"):
        return True
    if any(ch.isspace() for ch in literal):
        return True
    return len(literal) > 80


def sql_has_inbound_literal(sql: str) -> bool:
    """True when inbound text was spliced into a DML string instead of bound."""
    if not isinstance(sql, str) or not _SQL_DML.search(sql):
        return False
    if _SQL_MUTATION.search(sql) or _SQL_COMMENT.search(sql) or _SQL_STACKED.search(sql):
        return True
    if "{" in sql or "[" in sql:
        return True
    return any(_quoted_literal_is_inbound(literal) for literal in _SQL_QUOTED.findall(sql))


def reject_unbound_sql(sql: Any) -> None:
    """Fail closed when a DML string looks spliced instead of bound."""
    if sql_has_inbound_literal(sql if isinstance(sql, str) else ""):
        raise UnboundSqlError("sql must use bind parameters")


def is_state_unusable(exc: BaseException | None) -> bool:
    """True for a bad or readonly existing state.db. Missing is not this."""
    return isinstance(exc, StateUnusable)


def _sqlite_uri(path: Path, *, mode: str) -> str:
    return f"{path.resolve().as_uri()}?mode={mode}"


def _looks_like_sqlite(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            return handle.read(len(_SQLITE_HEADER)) == _SQLITE_HEADER
    except OSError:
        return False


def _writable_file(path: Path) -> bool:
    try:
        return os.access(path, os.W_OK) and bool(path.stat().st_mode & 0o222)
    except OSError:
        return False


class _BindOnlyConnection:
    """sqlite3 connection that refuses inbound text spliced into SQL."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def execute(self, sql: str, parameters: Any = ()) -> sqlite3.Cursor:
        reject_unbound_sql(sql)
        return self._conn.execute(sql, parameters)

    def executemany(self, sql: str, seq_of_parameters: Any) -> sqlite3.Cursor:
        reject_unbound_sql(sql)
        return self._conn.executemany(sql, seq_of_parameters)

    def executescript(self, sql: str) -> sqlite3.Cursor:
        reject_unbound_sql(sql)
        return self._conn.executescript(sql)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._conn, name)


def _json(value: Any) -> str:
    if is_dataclass(value):
        value = asdict(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=lambda x: x.value if hasattr(x, "value") else str(x))


def _enum(value: Any) -> str:
    return value.value if hasattr(value, "value") else str(value)


class ArtifactStore:
    """Immutable SHA-256 files below ``artifacts/sha256``."""

    def __init__(self, root: str | os.PathLike[str]):
        self.root = Path(root) / "sha256"
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, data: bytes, *, media_type: str = "application/octet-stream") -> dict[str, Any]:
        digest = hashlib.sha256(data).hexdigest()
        target = self.root / digest
        if target.exists():
            if target.read_bytes() != data:
                raise ArtifactCorruptionError(f"artifact hash collision or corruption: {digest}")
        else:
            temporary = target.with_name(f".{digest}.tmp-{os.getpid()}")
            temporary.write_bytes(data)
            os.replace(temporary, target)
        return {"digest": digest, "media_type": media_type, "byte_size": len(data), "uri": target.as_uri()}

    def verify(self, digest: str) -> bytes:
        target = self.root / digest
        if not target.is_file():
            raise FileNotFoundError(target)
        data = target.read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ArtifactCorruptionError(f"artifact hash mismatch: {digest}")
        return data


class StateRepository:
    """Small typed repository over the host-owned ``state.db``."""

    def __init__(self, db_path: str | os.PathLike[str], *, artifact_root: str | os.PathLike[str] | None = None):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.artifacts = ArtifactStore(artifact_root or self.db_path.parent / "artifacts")
        raw = sqlite3.connect(self.db_path, timeout=30, isolation_level=None)
        raw.row_factory = sqlite3.Row
        self.conn = _BindOnlyConnection(raw)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 30000")
        self.conn.execute("PRAGMA journal_mode = WAL")
        migrate(raw)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "StateRepository":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.conn.execute("BEGIN IMMEDIATE")
        try:
            yield self.conn
        except Exception:
            self.conn.rollback()
            raise
        else:
            self.conn.commit()

    def _event(self, project_id: str, event_type: str, payload: Any, *, conn: sqlite3.Connection) -> None:
        conn.execute(
            "INSERT INTO domain_events(project_id,event_type,payload_json,created_at) VALUES(?,?,?,datetime('now'))",
            (project_id, event_type, _json(payload)),
        )

    def events(self, project_id: str | None = None) -> list[sqlite3.Row]:
        if project_id is None:
            return list(self.conn.execute("SELECT * FROM domain_events ORDER BY event_id"))
        return list(self.conn.execute("SELECT * FROM domain_events WHERE project_id=? ORDER BY event_id", (project_id,)))

    def record_github_scan(self, project_id: str, repo_slug: str, *, scanned_at: str) -> None:
        """Append a github.scanned domain event for this project+repo. No new table."""
        with self.transaction() as c:
            self._require_project(c, project_id)
            self._event(
                project_id,
                "github.scanned",
                {"repo": repo_slug, "scanned_at": scanned_at},
                conn=c,
            )

    def set_hom_watch(self, project_id: str, repo_slug: str, *, created_at: str) -> None:
        """Persist the singleton declared watch (one project, one repo)."""
        with self.transaction() as c:
            self._require_project(c, project_id)
            c.execute(
                """
                INSERT INTO hom_watch(id, project_id, repo_slug, created_at)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    project_id=excluded.project_id,
                    repo_slug=excluded.repo_slug,
                    created_at=excluded.created_at
                """,
                (project_id, repo_slug, created_at),
            )
            self._event(project_id, "watch.set", {"repo": repo_slug}, conn=c)

    def get_hom_watch(self) -> dict[str, str] | None:
        """Return the declared watch, or None. v1 is one project → one repo."""
        row = self.conn.execute(
            "SELECT project_id, repo_slug, created_at FROM hom_watch WHERE id=1"
        ).fetchone()
        if row is None:
            return None
        return {
            "project_id": row["project_id"],
            "repo": row["repo_slug"],
            "created_at": row["created_at"],
        }

    def save_project(self, project: Project, *, event_type: str = "project.created", event_payload: Any | None = None) -> None:
        if project.brand.project_id != project.project_id:
            raise CrossProjectError("brand profile belongs to another project")
        with self.transaction() as c:
            c.execute("INSERT INTO projects VALUES (?,?,?,?,?)", (project.project_id, project.slug, project.name, project.kind, project.created_at))
            b = project.brand
            c.execute("INSERT INTO brand_profiles VALUES (?,?,?,?,?,?,?,?,?)", (b.project_id,b.display_name,b.voice,b.audience,b.maintainer,b.tone,_json(b.disclosures),b.revision,b.profile_hash))
            self._event(project.project_id, event_type, event_payload if event_payload is not None else project, conn=c)

    def get_project(self, project_id: str) -> Project | None:
        row = self.conn.execute("SELECT * FROM projects WHERE project_id=?", (project_id,)).fetchone()
        if row is None: return None
        b = self.conn.execute("SELECT * FROM brand_profiles WHERE project_id=?", (project_id,)).fetchone()
        if b is None: raise StorageError(f"project {project_id} has no brand profile")
        brand = BrandProfile(project_id=project_id, display_name=b["display_name"], voice=b["voice"], audience=b["audience"], maintainer=b["maintainer"], tone=b["tone"], disclosures=tuple(json.loads(b["disclosures_json"])), revision=b["revision"], profile_hash=b["profile_hash"])
        return Project(project_id=row["project_id"], slug=row["slug"], name=row["name"], created_at=row["created_at"], brand=brand, kind=row["kind"])

    def save_brand_profile(self, brand: BrandProfile, *, event_type: str = "brand_profile.saved") -> None:
        with self.transaction() as c:
            self._require_project(c, brand.project_id)
            c.execute("INSERT OR REPLACE INTO brand_profiles VALUES (?,?,?,?,?,?,?,?,?)", (brand.project_id,brand.display_name,brand.voice,brand.audience,brand.maintainer,brand.tone,_json(brand.disclosures),brand.revision,brand.profile_hash))
            self._event(brand.project_id, event_type, brand, conn=c)

    def save_content_revision(self, revision: ContentRevision, *, event_type: str = "content_revision.created") -> None:
        with self.transaction() as c:
            self._require_project(c, revision.project_id)
            c.execute("INSERT INTO content_revisions VALUES (?,?,?,?,?,?,?,?,?,?)", (revision.project_id,revision.content_id,revision.revision_id,revision.body,revision.kind,_enum(revision.status),revision.source,revision.source_digest,revision.created_at,revision.content_hash))
            self._event(revision.project_id, event_type, revision, conn=c)

    def save_account(self, account: PlatformAccount, *, event_type: str = "account.saved") -> None:
        with self.transaction() as c:
            self._require_project(c, account.project_id)
            c.execute("INSERT INTO platform_accounts VALUES (?,?,?,?,?,?,?,?)", (account.project_id,account.account_id,account.platform,account.handle,account.host,account.credential_ref,_enum(account.status),_json(account.capabilities)))
            self._event(account.project_id, event_type, account, conn=c)

    def list_accounts(self, project_id: str | None = None) -> list[PlatformAccount]:
        if project_id is None:
            rows = self.conn.execute("SELECT * FROM platform_accounts ORDER BY project_id, account_id")
        else:
            rows = self.conn.execute(
                "SELECT * FROM platform_accounts WHERE project_id=? ORDER BY account_id",
                (project_id,),
            )
        return [
            PlatformAccount(
                project_id=row["project_id"],
                account_id=row["account_id"],
                platform=row["platform"],
                handle=row["handle"],
                host=row["host"],
                credential_ref=row["credential_ref"],
                status=AccountStatus(row["status"]),
                capabilities=tuple(json.loads(row["capabilities_json"] or "[]")),
            )
            for row in rows
        ]

    def get_account(self, project_id: str, account_id: str) -> PlatformAccount | None:
        row = self.conn.execute(
            "SELECT * FROM platform_accounts WHERE project_id=? AND account_id=?",
            (project_id, account_id),
        ).fetchone()
        if row is None:
            return None
        return PlatformAccount(
            project_id=row["project_id"],
            account_id=row["account_id"],
            platform=row["platform"],
            handle=row["handle"],
            host=row["host"],
            credential_ref=row["credential_ref"],
            status=AccountStatus(row["status"]),
            capabilities=tuple(json.loads(row["capabilities_json"] or "[]")),
        )

    def get_policy(self, project_id: str, policy_version_id: str) -> PolicyVersion | None:
        row = self.conn.execute(
            "SELECT * FROM policy_versions WHERE project_id=? AND policy_version_id=?",
            (project_id, policy_version_id),
        ).fetchone()
        if row is None:
            return None
        return PolicyVersion(
            project_id=row["project_id"],
            policy_version_id=row["policy_version_id"],
            account_ids=tuple(json.loads(row["account_ids_json"] or "[]")),
            actions=tuple(json.loads(row["actions_json"] or "[]")),
            content_kinds=tuple(json.loads(row["content_kinds_json"] or "[]")),
            max_posts_per_day=int(row["max_posts_per_day"]),
            require_disclosures=bool(row["require_disclosures"]),
            policy_hash=row["policy_hash"],
        )

    def save_policy(self, policy: PolicyVersion, *, event_type: str = "policy.created") -> None:
        with self.transaction() as c:
            self._require_project(c, policy.project_id)
            for account_id in policy.account_ids:
                account = c.execute(
                    "SELECT project_id FROM platform_accounts WHERE account_id=?",
                    (account_id,),
                ).fetchone()
                if account is None:
                    raise StorageError(f"unknown policy account: {account_id}")
                if account["project_id"] != policy.project_id:
                    raise CrossProjectError("policy account belongs to another project")
            c.execute(
                "INSERT INTO policy_versions VALUES (?,?,?,?,?,?,?,?)",
                (
                    policy.project_id,
                    policy.policy_version_id,
                    _json(policy.account_ids),
                    _json(policy.actions),
                    _json(policy.content_kinds),
                    policy.max_posts_per_day,
                    int(policy.require_disclosures),
                    policy.policy_hash,
                ),
            )
            self._event(policy.project_id, event_type, policy, conn=c)

    def save_grant(self, grant: PolicyActivationGrant, *, event_type: str = "grant.created") -> None:
        with self.transaction() as c:
            self._require_project(c, grant.project_id)
            policy = c.execute(
                "SELECT policy_hash, account_ids_json, actions_json FROM policy_versions WHERE project_id=? AND policy_version_id=?",
                (grant.project_id, grant.policy_version_id),
            ).fetchone()
            if policy is None or policy["policy_hash"] != grant.policy_hash:
                raise StorageError("grant policy hash does not match policy version")
            allowed_actions = tuple(json.loads(policy["actions_json"] or "[]"))
            if not grant.actions:
                raise StorageError("grant requires at least one action")
            for action in grant.actions:
                if action not in allowed_actions:
                    raise StorageError(f"grant action not allowed by policy: {action}")
            if grant.platform_account_id is not None:
                account = c.execute(
                    "SELECT project_id FROM platform_accounts WHERE account_id=?",
                    (grant.platform_account_id,),
                ).fetchone()
                if account is None:
                    raise StorageError(f"unknown grant account: {grant.platform_account_id}")
                if account["project_id"] != grant.project_id:
                    raise CrossProjectError("grant account belongs to another project")
                allowed = tuple(json.loads(policy["account_ids_json"] or "[]"))
                if allowed and grant.platform_account_id not in allowed:
                    raise StorageError("grant account not allowed by policy")
            c.execute(
                "INSERT INTO policy_activation_grants VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    grant.project_id,
                    grant.grant_id,
                    grant.policy_version_id,
                    grant.policy_hash,
                    grant.platform_account_id,
                    _json(grant.actions),
                    grant.actor,
                    grant.created_at,
                    grant.expires_at,
                    grant.revoked_at,
                ),
            )
            self._event(grant.project_id, event_type, grant, conn=c)

    def save_campaign(self, campaign: Campaign, *, event_type: str = "campaign.saved") -> None:
        campaign.validate()
        with self.transaction() as c:
            self._require_project(c, campaign.project_id)
            c.execute("INSERT INTO campaigns VALUES (?,?,?,?,?,?,?,?)", (campaign.project_id,campaign.campaign_id,_enum(campaign.kind),campaign.name,_enum(campaign.status),campaign.budget_amount,campaign.budget_currency,_json(campaign.disclosures)))
            self._event(campaign.project_id, event_type, campaign, conn=c)

    def save_plan(self, plan: PublishPlan, *, event_type: str = "plan.saved") -> None:
        with self.transaction() as c:
            self._require_project(c, plan.project_id)
            account = c.execute("SELECT project_id,platform FROM platform_accounts WHERE account_id=?", (plan.platform_account_id,)).fetchone()
            revision = c.execute("SELECT project_id,content_hash FROM content_revisions WHERE revision_id=?", (plan.content_revision_id,)).fetchone()
            if account is None or revision is None or account["project_id"] != plan.project_id or revision["project_id"] != plan.project_id:
                raise CrossProjectError("plan references another project")
            if account["platform"] != plan.platform:
                raise StorageError("plan platform does not match account")
            if revision["content_hash"] != plan.content_hash:
                raise StorageError("plan content hash does not match revision")
            c.execute("INSERT INTO publish_plans VALUES (?,?,?,?,?,?,?,?,?,?,?)", (plan.project_id,plan.plan_id,plan.content_revision_id,plan.content_hash,plan.platform_account_id,plan.platform,plan.body,_enum(plan.status),plan.scheduled_at,plan.created_at,plan.operation_key))
            self._event(plan.project_id, event_type, plan, conn=c)
    def get_plan(self, project_id: str, plan_id: str) -> PublishPlan | None:
        row = self.conn.execute(
            "SELECT * FROM publish_plans WHERE project_id=? AND plan_id=?",
            (project_id, plan_id),
        ).fetchone()
        if row is None:
            return None
        return PublishPlan(
            project_id=row["project_id"],
            plan_id=row["plan_id"],
            content_revision_id=row["content_revision_id"],
            content_hash=row["content_hash"],
            platform_account_id=row["platform_account_id"],
            platform=row["platform"],
            body=row["body"],
            status=PlanStatus(row["status"]),
            scheduled_at=row["scheduled_at"],
            created_at=row["created_at"],
            operation_key=row["operation_key"],
        )


    def save_attempt(self, attempt: PublicationAttempt, *, event_type: str = "attempt.saved") -> None:
        with self.transaction() as c:
            self._require_project(c, attempt.project_id)
            plan = c.execute("SELECT project_id,operation_key FROM publish_plans WHERE project_id=? AND plan_id=?", (attempt.project_id, attempt.plan_id)).fetchone()
            if plan is None or plan["operation_key"] != attempt.operation_key:
                raise CrossProjectError("attempt references another project or operation")
            c.execute("INSERT INTO publication_attempts VALUES (?,?,?,?,?,?,?,?,?,?)", (attempt.project_id,attempt.attempt_id,attempt.plan_id,attempt.operation_key,_enum(attempt.status),attempt.created_at,attempt.provider_id,attempt.provider_url,attempt.failure_class,attempt.reason))
            self._event(attempt.project_id, event_type, attempt, conn=c)


    def reserve_attempt(
        self,
        plan: PublishPlan,
        attempt: PublicationAttempt,
        *,
        expected_plan_status: PlanStatus = PlanStatus.SCHEDULED,
    ) -> None:
        """Atomically claim a scheduled plan and insert a PENDING attempt."""
        if attempt.status is not AttemptStatus.PENDING:
            raise StorageError("reserve_attempt requires PENDING attempt")
        if plan.status is not PlanStatus.EXECUTING:
            raise StorageError("reserve_attempt requires plan already transitioned to EXECUTING in memory")
        if attempt.plan_id != plan.plan_id or attempt.project_id != plan.project_id:
            raise CrossProjectError("attempt/plan project mismatch")
        if attempt.operation_key != plan.operation_key:
            raise StorageError("attempt operation_key must match plan")
        with self.transaction() as c:
            row = c.execute(
                "SELECT status, operation_key FROM publish_plans WHERE project_id=? AND plan_id=?",
                (plan.project_id, plan.plan_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown plan: {plan.plan_id}")
            if row["status"] != _enum(expected_plan_status):
                raise StorageError(
                    f"plan reserve CAS failed: expected {expected_plan_status.value}, found {row['status']}"
                )
            if row["operation_key"] != plan.operation_key:
                raise StorageError("plan operation_key mismatch during reserve")
            c.execute(
                "UPDATE publish_plans SET status=? WHERE project_id=? AND plan_id=? AND status=?",
                (_enum(PlanStatus.EXECUTING), plan.project_id, plan.plan_id, _enum(expected_plan_status)),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise StorageError("plan reserve CAS update raced")
            c.execute(
                "INSERT INTO publication_attempts VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    attempt.project_id,
                    attempt.attempt_id,
                    attempt.plan_id,
                    attempt.operation_key,
                    _enum(AttemptStatus.PENDING),
                    attempt.created_at,
                    attempt.provider_id,
                    attempt.provider_url,
                    attempt.failure_class,
                    attempt.reason,
                ),
            )
            self._event(plan.project_id, "plan.status_changed", plan, conn=c)
            self._event(attempt.project_id, "attempt.reserved", attempt, conn=c)

    def update_plan_status(
        self,
        plan: PublishPlan,
        *,
        expected_status: PlanStatus,
        event_type: str = "plan.status_changed",
    ) -> None:
        with self.transaction() as c:
            row = c.execute(
                "SELECT status FROM publish_plans WHERE project_id=? AND plan_id=?",
                (plan.project_id, plan.plan_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown plan: {plan.plan_id}")
            if row["status"] != _enum(expected_status):
                raise StorageError(
                    f"plan status CAS failed: expected {expected_status.value}, found {row['status']}"
                )
            c.execute(
                "UPDATE publish_plans SET status=? WHERE project_id=? AND plan_id=? AND status=?",
                (_enum(plan.status), plan.project_id, plan.plan_id, _enum(expected_status)),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise StorageError("plan status CAS update raced")
            self._event(plan.project_id, event_type, plan, conn=c)
    def update_plan_status_with_receipt(
        self,
        plan: PublishPlan,
        *,
        expected_status: PlanStatus,
        receipt_id: str,
        receipt_status: str,
        receipt_payload: Mapping[str, Any],
        created_at: str,
        event_type: str,
    ) -> None:
        """CAS a plan and record its receipt in the same transaction."""
        with self.transaction() as c:
            row = c.execute(
                "SELECT status FROM publish_plans WHERE project_id=? AND plan_id=?",
                (plan.project_id, plan.plan_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown plan: {plan.plan_id}")
            if row["status"] != _enum(expected_status):
                raise StorageError(
                    f"plan status CAS failed: expected {expected_status.value}, found {row['status']}"
                )
            try:
                c.execute(
                    "INSERT INTO receipts VALUES (?,?,?,?,?,?,?)",
                    (plan.project_id, receipt_id, plan.plan_id, None, receipt_status, _json(receipt_payload), created_at),
                )
            except sqlite3.IntegrityError as exc:
                raise StorageError(f"receipt already exists: {receipt_id}") from exc
            c.execute(
                "UPDATE publish_plans SET status=? WHERE project_id=? AND plan_id=? AND status=?",
                (_enum(plan.status), plan.project_id, plan.plan_id, _enum(expected_status)),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise StorageError("plan status CAS update raced")
            self._event(plan.project_id, event_type, plan, conn=c)
            self._event(plan.project_id, "receipt.recorded", {"receipt_id": receipt_id, "status": receipt_status}, conn=c)


    def update_attempt_status(
        self,
        attempt: PublicationAttempt,
        *,
        expected_status: AttemptStatus,
        event_type: str = "attempt.status_changed",
    ) -> None:
        with self.transaction() as c:
            row = c.execute(
                "SELECT status FROM publication_attempts WHERE project_id=? AND attempt_id=?",
                (attempt.project_id, attempt.attempt_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown attempt: {attempt.attempt_id}")
            if row["status"] != _enum(expected_status):
                raise StorageError(
                    f"attempt status CAS failed: expected {expected_status.value}, found {row['status']}"
                )
            c.execute(
                """
                UPDATE publication_attempts
                SET status=?, provider_id=?, provider_url=?, failure_class=?, reason=?
                WHERE project_id=? AND attempt_id=? AND status=?
                """,
                (
                    _enum(attempt.status),
                    attempt.provider_id,
                    attempt.provider_url,
                    attempt.failure_class,
                    attempt.reason,
                    attempt.project_id,
                    attempt.attempt_id,
                    _enum(expected_status),
                ),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise StorageError("attempt status CAS update raced")
            self._event(attempt.project_id, event_type, attempt, conn=c)

    def save_brief(self, brief: Brief, *, event_type: str = "brief.ingested") -> None:
        with self.transaction() as c:
            self._require_project(c, brief.project_id)
            c.execute(
                "INSERT INTO briefs VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    brief.project_id,
                    brief.brief_id,
                    _json(brief_to_mapping(brief)["facts"]),
                    brief.story_kind.value,
                    int(brief.claims_ship),
                    int(brief.tryable),
                    None if brief.preferred_arena is None else brief.preferred_arena.value,
                    brief.source,
                    brief.status,
                    brief.created_at,
                ),
            )
            self._event(brief.project_id, event_type, brief_to_mapping(brief), conn=c)

    def get_brief(self, project_id: str, brief_id: str) -> Brief | None:
        row = self.conn.execute(
            "SELECT * FROM briefs WHERE project_id=? AND brief_id=?",
            (project_id, brief_id),
        ).fetchone()
        if row is None:
            return None
        return self._brief_from_row(row)

    def list_pending_briefs(self, project_id: str | None = None) -> list[Brief]:
        if project_id is None:
            rows = self.conn.execute(
                "SELECT * FROM briefs WHERE status='pending' ORDER BY created_at, brief_id"
            )
        else:
            rows = self.conn.execute(
                "SELECT * FROM briefs WHERE status='pending' AND project_id=? ORDER BY created_at, brief_id",
                (project_id,),
            )
        return [self._brief_from_row(row) for row in rows]

    def list_briefs(self, project_id: str) -> list[Brief]:
        rows = self.conn.execute(
            "SELECT * FROM briefs WHERE project_id=? ORDER BY created_at, brief_id",
            (project_id,),
        )
        return [self._brief_from_row(row) for row in rows]

    def list_operator_drafts(
        self,
        project_id: str | None = None,
        *,
        include_held: bool = False,
    ) -> list[Draft]:
        """Open drafts by default. Held (gate veto) rows stay in the table."""
        if include_held and project_id is None:
            rows = self.conn.execute(
                "SELECT * FROM operator_drafts ORDER BY created_at, draft_id"
            )
        elif include_held:
            rows = self.conn.execute(
                "SELECT * FROM operator_drafts WHERE project_id=? ORDER BY created_at, draft_id",
                (project_id,),
            )
        elif project_id is None:
            rows = self.conn.execute(
                "SELECT * FROM operator_drafts WHERE coalesce(gate_verdict, '') != ? "
                "ORDER BY created_at, draft_id",
                ("hold",),
            )
        else:
            rows = self.conn.execute(
                "SELECT * FROM operator_drafts WHERE project_id=? AND coalesce(gate_verdict, '') != ? "
                "ORDER BY created_at, draft_id",
                (project_id, "hold"),
            )
        return [self._draft_from_row(row) for row in rows]

    def get_operator_score(self, project_id: str, brief_id: str) -> Score | None:
        row = self.conn.execute(
            "SELECT * FROM operator_scores WHERE project_id=? AND brief_id=?",
            (project_id, brief_id),
        ).fetchone()
        if row is None:
            return None
        arena = None if not row["arena"] else ArenaId(row["arena"])
        return Score(
            brief_id=row["brief_id"],
            verdict=Verdict(row["verdict"]),
            reason=row["reason"],
            arena=arena,
            angle=row["angle"],
            wave_checklist=tuple(json.loads(row["wave_checklist_json"] or "[]")),
            canon_url=row["canon_url"],
            score_hash=row["score_hash"],
        )

    def get_operator_draft(self, project_id: str, brief_id: str) -> Draft | None:
        row = self.conn.execute(
            "SELECT * FROM operator_drafts WHERE project_id=? AND brief_id=?",
            (project_id, brief_id),
        ).fetchone()
        if row is None:
            return None
        return self._draft_from_row(row)

    def _draft_from_row(self, row: sqlite3.Row) -> Draft:
        return Draft(
            project_id=row["project_id"],
            brief_id=row["brief_id"],
            draft_id=row["draft_id"],
            arena=ArenaId(row["arena"]),
            costume=row["costume"],
            angle=row["angle"],
            body=row["body"],
            wave_checklist=tuple(json.loads(row["wave_checklist_json"] or "[]")),
            canon_url=row["canon_url"],
            created_at=row["created_at"],
            content_hash=row["content_hash"],
        )

    def persist_operator_decision(
        self,
        brief: Brief,
        score: Score,
        draft: Draft | None,
        *,
        revision: ContentRevision | None = None,
        now: str,
    ) -> None:
        """Atomically record score, optional draft/revision, and mark the brief processed."""
        with self.transaction() as c:
            self._require_project(c, brief.project_id)
            row = c.execute(
                "SELECT status FROM briefs WHERE project_id=? AND brief_id=?",
                (brief.project_id, brief.brief_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown brief: {brief.brief_id}")
            if row["status"] != "pending":
                raise StorageError(f"brief already processed: {brief.brief_id}")
            c.execute(
                "INSERT INTO operator_scores VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    brief.project_id,
                    brief.brief_id,
                    score.verdict.value,
                    score.reason,
                    None if score.arena is None else score.arena.value,
                    score.angle,
                    _json(score.wave_checklist),
                    score.canon_url,
                    score.score_hash,
                    now,
                ),
            )
            if draft is not None:
                c.execute(
                    "INSERT INTO operator_drafts("
                    "project_id, brief_id, draft_id, arena, costume, angle, body, "
                    "wave_checklist_json, canon_url, content_hash, created_at"
                    ") VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        draft.project_id,
                        draft.brief_id,
                        draft.draft_id,
                        draft.arena.value,
                        draft.costume,
                        draft.angle,
                        draft.body,
                        _json(draft.wave_checklist),
                        draft.canon_url,
                        draft.content_hash,
                        draft.created_at,
                    ),
                )
            if revision is not None:
                if revision.project_id != brief.project_id:
                    raise CrossProjectError("operator draft revision belongs to another project")
                c.execute(
                    "INSERT INTO content_revisions VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        revision.project_id,
                        revision.content_id,
                        revision.revision_id,
                        revision.body,
                        revision.kind,
                        _enum(revision.status),
                        revision.source,
                        revision.source_digest,
                        revision.created_at,
                        revision.content_hash,
                    ),
                )
                self._event(revision.project_id, "content_revision.created", revision, conn=c)
            c.execute(
                "UPDATE briefs SET status='processed' WHERE project_id=? AND brief_id=? AND status='pending'",
                (brief.project_id, brief.brief_id),
            )
            if c.execute("SELECT changes()").fetchone()[0] != 1:
                raise StorageError("brief process CAS raced")
            self._event(
                brief.project_id,
                "brief.scored",
                {
                    "brief_id": brief.brief_id,
                    "verdict": score.verdict.value,
                    "reason": score.reason,
                    "arena": None if score.arena is None else score.arena.value,
                    "published": False,
                },
                conn=c,
            )

    def record_draft_verdict(self, draft: Draft, verdict: str) -> None:
        """Stamp pass|hold on a draft. Hold dismisses it from the open set; never deletes."""
        if verdict not in {"hold", "pass"}:
            raise StorageError("verdict must be pass|hold")
        with self.transaction() as c:
            self._require_project(c, draft.project_id)
            row = c.execute(
                "SELECT draft_id FROM operator_drafts WHERE project_id=? AND draft_id=?",
                (draft.project_id, draft.draft_id),
            ).fetchone()
            if row is None:
                raise StorageError(f"unknown draft: {draft.draft_id}")
            c.execute(
                "UPDATE operator_drafts SET gate_verdict=? WHERE project_id=? AND draft_id=?",
                (verdict, draft.project_id, draft.draft_id),
            )
            self._event(
                draft.project_id,
                "draft.verdict",
                {
                    "draft_id": draft.draft_id,
                    "brief_id": draft.brief_id,
                    "verdict": verdict,
                    "published": False,
                },
                conn=c,
            )

    def _brief_from_row(self, row: sqlite3.Row) -> Brief:
        arena = row["preferred_arena"]
        return Brief.create(
            project_id=row["project_id"],
            brief_id=row["brief_id"],
            facts=parse_facts_json(row["facts_json"]),
            story_kind=StoryKind(row["story_kind"]),
            claims_ship=bool(row["claims_ship"]),
            tryable=bool(row["tryable"]),
            preferred_arena=None if not arena else arena,
            source=row["source"],
            status=row["status"],
            created_at=row["created_at"],
        )

    def _require_project(self, c: sqlite3.Connection, project_id: str) -> None:
        if c.execute("SELECT 1 FROM projects WHERE project_id=?", (project_id,)).fetchone() is None:
            raise StorageError(f"unknown project: {project_id}")

    def register_artifact(self, data: bytes, *, media_type: str = "application/octet-stream", created_at: str | None = None) -> dict[str, Any]:
        """Put bytes in the immutable store and atomically register metadata."""
        meta = self.artifacts.put(data, media_type=media_type)
        with self.transaction() as c:
            c.execute("INSERT OR IGNORE INTO artifacts(digest,media_type,byte_size,uri,created_at) VALUES(?,?,?,?,COALESCE(?,datetime('now')))", (meta["digest"], meta["media_type"], meta["byte_size"], meta["uri"], created_at))
        return meta

    def append_metric(self, *, project_id: str, metric_id: str, scope_type: str, scope_id: str, metric_name: str, metric_value: float, window_start: str, window_end: str, observed_at: str, source_ref: str, platform_account_id: str | None = None, raw_payload_uri: str | None = None) -> None:
        with self.transaction() as c:
            self._require_project(c, project_id)
            c.execute("INSERT INTO metric_snapshots VALUES (?,?,?,?,?,?,?,?,?,?,?,?)", (project_id, metric_id, scope_type, scope_id, platform_account_id, metric_name, metric_value, window_start, window_end, observed_at, source_ref, raw_payload_uri))
            self._event(project_id, "metric.snapshot", {"metric_id": metric_id, "scope_id": scope_id}, conn=c)

    def append_receipt(self, *, project_id: str, receipt_id: str, status: str, payload: Mapping[str, Any], created_at: str, plan_id: str | None = None, attempt_id: str | None = None) -> None:
        with self.transaction() as c:
            self._require_project(c, project_id)
            c.execute("INSERT INTO receipts VALUES (?,?,?,?,?,?,?)", (project_id, receipt_id, plan_id, attempt_id, status, _json(payload), created_at))
            self._event(project_id, "receipt.recorded", {"receipt_id": receipt_id, "status": status}, conn=c)


# The shorter name is convenient for callers while retaining an explicit alias.
SQLiteRepository = StateRepository

__all__ = [
    "ArtifactCorruptionError",
    "ArtifactStore",
    "CrossProjectError",
    "MigrationError",
    "SQLiteRepository",
    "StateRepository",
    "StorageError",
    "UnboundSqlError",
    "reject_unbound_sql",
    "sql_has_inbound_literal",
]
