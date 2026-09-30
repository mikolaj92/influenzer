"""Versioned SQLite schema for Influenzer's host-owned state database."""
from __future__ import annotations

import json
import sqlite3

from .domain import BrandProfile, DomainError

SCHEMA_VERSION = 5


class MigrationError(RuntimeError):
    """The database cannot be safely opened or migrated."""


_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('app','personal','builder')), created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS brand_profiles (
    project_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, voice TEXT NOT NULL,
    audience TEXT NOT NULL, maintainer TEXT NOT NULL, tone TEXT NOT NULL,
    disclosures_json TEXT NOT NULL, revision INTEGER NOT NULL, profile_hash TEXT NOT NULL,
    pillars_json TEXT NOT NULL DEFAULT '[]',
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS content_revisions (
    project_id TEXT NOT NULL, content_id TEXT NOT NULL, revision_id TEXT NOT NULL,
    body TEXT NOT NULL, kind TEXT NOT NULL, status TEXT NOT NULL, source TEXT NOT NULL,
    source_digest TEXT NOT NULL, created_at TEXT NOT NULL, content_hash TEXT NOT NULL,
    PRIMARY KEY(project_id, revision_id), UNIQUE(project_id, content_id, revision_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS platform_accounts (
    project_id TEXT NOT NULL, account_id TEXT NOT NULL, platform TEXT NOT NULL,
    handle TEXT NOT NULL, host TEXT, credential_ref TEXT NOT NULL, status TEXT NOT NULL,
    capabilities_json TEXT NOT NULL, PRIMARY KEY(project_id, account_id), UNIQUE(account_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS policy_versions (
    project_id TEXT NOT NULL, policy_version_id TEXT NOT NULL, account_ids_json TEXT NOT NULL,
    actions_json TEXT NOT NULL, content_kinds_json TEXT NOT NULL, max_posts_per_day INTEGER NOT NULL,
    require_disclosures INTEGER NOT NULL, policy_hash TEXT NOT NULL,
    PRIMARY KEY(project_id, policy_version_id), UNIQUE(policy_hash),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS policy_activation_grants (
    project_id TEXT NOT NULL, grant_id TEXT NOT NULL, policy_version_id TEXT NOT NULL,
    policy_hash TEXT NOT NULL, platform_account_id TEXT, actions_json TEXT NOT NULL,
    actor TEXT NOT NULL, created_at TEXT NOT NULL, expires_at TEXT, revoked_at TEXT,
    PRIMARY KEY(project_id, grant_id),
    FOREIGN KEY(project_id, policy_version_id) REFERENCES policy_versions(project_id, policy_version_id),
    FOREIGN KEY(project_id, platform_account_id) REFERENCES platform_accounts(project_id, account_id)
);
CREATE TABLE IF NOT EXISTS campaigns (
    project_id TEXT NOT NULL, campaign_id TEXT NOT NULL, kind TEXT NOT NULL CHECK (kind IN ('organic','paid')),
    name TEXT NOT NULL, status TEXT NOT NULL, budget_amount REAL, budget_currency TEXT,
    disclosures_json TEXT NOT NULL, PRIMARY KEY(project_id, campaign_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS publish_plans (
    project_id TEXT NOT NULL, plan_id TEXT NOT NULL, content_revision_id TEXT NOT NULL,
    content_hash TEXT NOT NULL, platform_account_id TEXT NOT NULL, platform TEXT NOT NULL,
    body TEXT NOT NULL, status TEXT NOT NULL, scheduled_at TEXT, created_at TEXT NOT NULL,
    operation_key TEXT NOT NULL UNIQUE, PRIMARY KEY(project_id, plan_id),
    FOREIGN KEY(project_id, content_revision_id) REFERENCES content_revisions(project_id, revision_id),
    FOREIGN KEY(project_id, platform_account_id) REFERENCES platform_accounts(project_id, account_id)
);
CREATE TABLE IF NOT EXISTS publication_attempts (
    project_id TEXT NOT NULL, attempt_id TEXT NOT NULL, plan_id TEXT NOT NULL,
    operation_key TEXT NOT NULL, status TEXT NOT NULL CHECK (status IN ('pending','running','succeeded','failed','unknown','cancelled')),
    created_at TEXT NOT NULL, provider_id TEXT, provider_url TEXT, failure_class TEXT, reason TEXT,
    PRIMARY KEY(project_id, attempt_id), UNIQUE(operation_key),
    FOREIGN KEY(project_id, plan_id) REFERENCES publish_plans(project_id, plan_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS one_active_attempt_per_plan ON publication_attempts(project_id, plan_id)
WHERE status IN ('pending','running','unknown');
CREATE TABLE IF NOT EXISTS artifacts (
    digest TEXT PRIMARY KEY, media_type TEXT NOT NULL, byte_size INTEGER NOT NULL,
    uri TEXT NOT NULL UNIQUE, created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS metric_snapshots (
    project_id TEXT NOT NULL, metric_id TEXT NOT NULL, scope_type TEXT NOT NULL, scope_id TEXT NOT NULL,
    platform_account_id TEXT, metric_name TEXT NOT NULL, metric_value REAL NOT NULL,
    window_start TEXT NOT NULL, window_end TEXT NOT NULL, observed_at TEXT NOT NULL,
    source_ref TEXT NOT NULL, raw_payload_uri TEXT, PRIMARY KEY(project_id, metric_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE,
    FOREIGN KEY(project_id, platform_account_id) REFERENCES platform_accounts(project_id, account_id)
);
CREATE TABLE IF NOT EXISTS exports (
    project_id TEXT NOT NULL, export_id TEXT NOT NULL, kind TEXT NOT NULL, content_hash TEXT NOT NULL,
    artifact_uri TEXT, created_at TEXT NOT NULL, PRIMARY KEY(project_id, export_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS receipts (
    project_id TEXT NOT NULL, receipt_id TEXT NOT NULL, plan_id TEXT, attempt_id TEXT,
    status TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, receipt_id),
    FOREIGN KEY(project_id, plan_id) REFERENCES publish_plans(project_id, plan_id),
    FOREIGN KEY(project_id, attempt_id) REFERENCES publication_attempts(project_id, attempt_id)
);
CREATE TABLE IF NOT EXISTS domain_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
    event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS domain_events_project_idx ON domain_events(project_id, event_id);
"""

_V2_SCHEMA = """
CREATE TABLE IF NOT EXISTS briefs (
    project_id TEXT NOT NULL, brief_id TEXT NOT NULL, facts_json TEXT NOT NULL,
    story_kind TEXT NOT NULL, claims_ship INTEGER NOT NULL, tryable INTEGER NOT NULL,
    preferred_arena TEXT, source TEXT NOT NULL, status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, brief_id),
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS operator_scores (
    project_id TEXT NOT NULL, brief_id TEXT NOT NULL, verdict TEXT NOT NULL,
    reason TEXT NOT NULL, arena TEXT, angle TEXT, wave_checklist_json TEXT NOT NULL,
    canon_url TEXT NOT NULL, score_hash TEXT NOT NULL, created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, brief_id),
    FOREIGN KEY(project_id, brief_id) REFERENCES briefs(project_id, brief_id)
);
CREATE TABLE IF NOT EXISTS operator_drafts (
    project_id TEXT NOT NULL, brief_id TEXT NOT NULL, draft_id TEXT NOT NULL,
    arena TEXT NOT NULL, costume TEXT NOT NULL, angle TEXT NOT NULL, body TEXT NOT NULL,
    wave_checklist_json TEXT NOT NULL, canon_url TEXT NOT NULL, content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(project_id, draft_id), UNIQUE(project_id, brief_id),
    FOREIGN KEY(project_id, brief_id) REFERENCES briefs(project_id, brief_id)
);
"""

_V3_SCHEMA = """
ALTER TABLE operator_drafts ADD COLUMN gate_verdict TEXT;
"""

_V4_SCHEMA = """
CREATE TABLE IF NOT EXISTS hom_watch (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    project_id TEXT NOT NULL,
    repo_slug TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
);
"""

_V5_SCHEMA = """
ALTER TABLE brand_profiles ADD COLUMN pillars_json TEXT NOT NULL DEFAULT '[]';
"""


def _migrate_v5(conn: sqlite3.Connection) -> None:
    """Add the profile pillars column to databases created before v5."""
    kind = conn.execute(
        "SELECT type FROM sqlite_master WHERE name = 'brand_profiles'"
    ).fetchone()
    if kind is None or kind[0] != "table":
        raise MigrationError("state database is missing brand_profiles")
    columns = {row[1] for row in conn.execute("PRAGMA table_info(brand_profiles)")}
    if "pillars_json" not in columns:
        try:
            conn.executescript(_V5_SCHEMA)
        except sqlite3.OperationalError as exc:
            # Another autocommit connection may have added the column since
            # our check. Accept only the schema this migration would create.
            pillar = next(
                (row for row in conn.execute("PRAGMA table_info(brand_profiles)")
                 if row[1] == "pillars_json"),
                None,
            )
            if pillar is None or (pillar[2].upper(), pillar[3], pillar[4]) != ("TEXT", 1, "'[]'"):
                raise MigrationError("state database cannot add brand_profiles.pillars_json") from exc
    pillar = next(
        (row for row in conn.execute("PRAGMA table_info(brand_profiles)")
         if row[1] == "pillars_json"), None,
    )
    if pillar is None or (pillar[2].upper(), pillar[3], pillar[4]) != ("TEXT", 1, "'[]'"):
        raise MigrationError("state database has incompatible brand_profiles.pillars_json")
    _recover_v5_pillars(conn)


def _recover_v5_pillars(conn: sqlite3.Connection) -> None:
    """Recover omitted pillars only from an event matching the entire profile."""
    if conn.execute("SELECT 1 FROM sqlite_master WHERE name=? AND type=?", ("domain_events", "table")).fetchone() is None:
        return
    fields = ("project_id", "display_name", "voice", "audience", "maintainer", "tone",
              "disclosures", "revision", "profile_hash")
    rows = conn.execute(
        "SELECT project_id, display_name, voice, audience, maintainer, tone, "
        "disclosures_json, revision, profile_hash FROM brand_profiles WHERE pillars_json=?",
        ("[]",),
    ).fetchall()
    for row in rows:
        stored = dict(zip(fields, row))
        try:
            stored["disclosures"] = json.loads(stored["disclosures"])
        except (TypeError, json.JSONDecodeError):
            continue
        events = conn.execute(
            "SELECT event_type, payload_json FROM domain_events WHERE project_id=? "
            "AND event_type IN (?,?) ORDER BY event_id DESC",
            (stored["project_id"], "project.created", "brand_profile.saved"),
        )
        for event_type, raw in events:
            try:
                payload = json.loads(raw)
                candidate = payload.get("brand") if event_type == "project.created" else payload
                if not isinstance(candidate, dict) or any(candidate.get(key) != value for key, value in stored.items()):
                    continue
                pillars = candidate.get("pillars")
                if not isinstance(pillars, list) or not pillars:
                    continue
                brand = BrandProfile(**{**stored, "disclosures": tuple(stored["disclosures"]),
                                        "pillars": tuple(pillars)})
                if brand.with_hash().profile_hash != stored["profile_hash"]:
                    continue
            except (AttributeError, TypeError, ValueError, DomainError):
                continue
            conn.execute(
                "UPDATE brand_profiles SET pillars_json=? WHERE project_id=? AND pillars_json=? AND profile_hash=?",
                (json.dumps(pillars, ensure_ascii=False), stored["project_id"], "[]", stored["profile_hash"]),
            )
            break


def current_version(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT value FROM schema_meta WHERE key = 'schema_version'").fetchone()
    return int(row[0]) if row else 0


def migrate(conn: sqlite3.Connection) -> int:
    conn.execute("CREATE TABLE IF NOT EXISTS schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
    version = current_version(conn)
    if version > SCHEMA_VERSION:
        raise MigrationError(f"state database schema {version} is newer than supported {SCHEMA_VERSION}")
    if version == 0:
        conn.executescript(_SCHEMA)
        conn.executescript(_V2_SCHEMA)
        conn.executescript(_V3_SCHEMA)
        conn.executescript(_V4_SCHEMA)
    elif version == 1:
        conn.executescript(_V2_SCHEMA)
        conn.executescript(_V3_SCHEMA)
        conn.executescript(_V4_SCHEMA)
    elif version == 2:
        conn.executescript(_V3_SCHEMA)
        conn.executescript(_V4_SCHEMA)
    elif version == 3:
        conn.executescript(_V4_SCHEMA)
    if version <= 4:
        _migrate_v5(conn)
        conn.execute("INSERT OR REPLACE INTO schema_meta(key, value) VALUES ('schema_version', ?)", (str(SCHEMA_VERSION),))
        conn.commit()
    return SCHEMA_VERSION


def initialize_schema(conn: sqlite3.Connection) -> int:
    return migrate(conn)
