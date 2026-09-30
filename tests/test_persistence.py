import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from influenzer.domain import AttemptStatus, BrandProfile, ContentStatus, Project, content_hash
from influenzer.domain import ContentRevision, PlatformAccount, AccountStatus
from influenzer.domain import PublishPlan, PlanStatus, PublicationAttempt
from influenzer.hom import Brief, Fact, Score
from influenzer.hom_draft import dress_brief
from influenzer.playbook import ARENAS, ArenaId, StoryKind, Verdict
from influenzer.storage import (
    ArtifactCorruptionError,
    MigrationError,
    StateRepository,
    StateUnusable,
    StorageError,
    UnboundSqlError,
    is_state_unusable,
    reject_unbound_sql,
    sql_has_inbound_literal,
    tick_lock_path,
    try_acquire_tick_lock,
)

# Pre-v5 brand_profiles: 9 columns, no pillars_json. ALTER TABLE ADD COLUMN
# appends pillars_json last; named INSERT must still round-trip that layout.
_PRE_V5_BRAND_PROFILES = """
CREATE TABLE brand_profiles (
    project_id TEXT PRIMARY KEY, display_name TEXT NOT NULL, voice TEXT NOT NULL,
    audience TEXT NOT NULL, maintainer TEXT NOT NULL, tone TEXT NOT NULL,
    disclosures_json TEXT NOT NULL, revision INTEGER NOT NULL,
    profile_hash TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
)
"""


def _replace_brand_profiles_with_pre_v5(conn: sqlite3.Connection) -> None:
    conn.execute("DROP TABLE brand_profiles")
    conn.executescript(_PRE_V5_BRAND_PROFILES)


class PersistenceTests(unittest.TestCase):
    def project(self, project_id: str, slug: str, kind: str = "app") -> Project:
        return Project.create(project_id=project_id, slug=slug, name=slug.title(), display_name=slug, voice="plain", audience="builders", maintainer="team", kind=kind)

    def assert_pillars_json_appended(self, repo: StateRepository) -> None:
        columns = [row[1] for row in repo.conn.execute("PRAGMA table_info(brand_profiles)")]
        self.assertIn("pillars_json", columns)
        self.assertEqual(columns[-1], "pillars_json")

    def revision(self, project_id: str) -> ContentRevision:
        return ContentRevision(project_id=project_id, content_id="content", revision_id="rev-1", body="hello", kind="post", status=ContentStatus.DRAFT, source="test", source_digest="src", created_at="2026-01-01T00:00:00Z").with_hash()

    def test_app_and_builder_profiles_are_isolated(self):
        with tempfile.TemporaryDirectory() as tmp:
            with StateRepository(Path(tmp) / "state.db") as repo:
                app = self.project("app", "app", "app")
                builder = self.project("builder", "builder", "builder")
                repo.save_project(app)
                repo.save_project(builder)
                self.assertEqual(repo.get_project("app").brand.project_id, "app")
                self.assertEqual(repo.get_project("builder").brand.project_id, "builder")
                self.assertNotEqual(repo.get_project("app").brand.display_name, repo.get_project("builder").brand.display_name)
                self.assertEqual(len(repo.events("app")), 1)
                self.assertEqual(len(repo.events("builder")), 1)

    def test_v5_migration_accepts_column_added_by_another_connection(self):
        from influenzer.migrations import SCHEMA_VERSION, migrate

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                _replace_brand_profiles_with_pre_v5(repo.conn)
                repo.conn.execute("UPDATE schema_meta SET value='4' WHERE key='schema_version'")
            other = sqlite3.connect(path, isolation_level=None)

            class InterleavedConnection(sqlite3.Connection):
                def executescript(self, sql):
                    if "ADD COLUMN pillars_json" in sql:
                        # Both connections observed v4; the competitor wins
                        # after this connection's column check, before ALTER.
                        self.competitor_version = migrate(other)
                    return super().executescript(sql)

            conn = sqlite3.connect(path, isolation_level=None, factory=InterleavedConnection)
            try:
                self.assertEqual(migrate(conn), SCHEMA_VERSION)
                self.assertEqual(conn.competitor_version, SCHEMA_VERSION)
                columns = list(conn.execute("PRAGMA table_info(brand_profiles)"))
                self.assertEqual(sum(row[1] == "pillars_json" for row in columns), 1)
                self.assertEqual(migrate(other), SCHEMA_VERSION)
            finally:
                conn.close()
                other.close()

    def test_v5_migration_rejects_invalid_column_added_by_another_connection(self):
        from influenzer.migrations import migrate

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                _replace_brand_profiles_with_pre_v5(repo.conn)
                repo.conn.execute("UPDATE schema_meta SET value='4' WHERE key='schema_version'")
            other = sqlite3.connect(path, isolation_level=None)

            class InterleavedConnection(sqlite3.Connection):
                def executescript(self, sql):
                    if "ADD COLUMN pillars_json" in sql:
                        other.execute("ALTER TABLE brand_profiles ADD COLUMN pillars_json INTEGER")
                    return super().executescript(sql)

            conn = sqlite3.connect(path, isolation_level=None, factory=InterleavedConnection)
            try:
                with self.assertRaises(MigrationError) as raised:
                    migrate(conn)
                self.assertIsInstance(raised.exception.__cause__, sqlite3.OperationalError)
                self.assertEqual(conn.execute(
                    "SELECT value FROM schema_meta WHERE key='schema_version'"
                ).fetchone()[0], "4")
            finally:
                conn.close()
                other.close()

    def test_v5_rejects_incompatible_preexisting_pillars_column(self):
        from influenzer.migrations import migrate

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                _replace_brand_profiles_with_pre_v5(repo.conn)
                repo.conn.execute("ALTER TABLE brand_profiles ADD COLUMN pillars_json TEXT")
                repo.conn.execute("UPDATE schema_meta SET value='4' WHERE key='schema_version'")
                with self.assertRaises(MigrationError):
                    migrate(repo.conn)
                self.assertEqual(repo.conn.execute(
                    "SELECT value FROM schema_meta WHERE key='schema_version'"
                ).fetchone()[0], "4")

    def test_v5_recovers_lost_pillars_from_matching_events(self):
        from dataclasses import replace

        for updated in (False, True):
            with self.subTest(updated=updated), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "state.db"
                project = self.project("legacy", "legacy")
                brand = replace(project.brand, pillars=("durable automation",)).with_hash()
                with StateRepository(path) as repo:
                    repo.save_project(replace(project, brand=brand))
                    if updated:
                        brand = replace(brand, pillars=("local-first",), revision=2).with_hash()
                        repo.save_brand_profile(brand)
                    repo.conn.execute("ALTER TABLE brand_profiles DROP COLUMN pillars_json")
                    repo.conn.execute("UPDATE schema_meta SET value='4' WHERE key='schema_version'")
                with StateRepository(path) as repo:
                    self.assertEqual(repo.get_project("legacy").brand, brand)
                with StateRepository(path) as repo:
                    self.assertEqual(repo.get_project("legacy").brand, brand)

    def test_lost_pillars_require_explicit_hash_checked_repair_without_matching_event(self):
        from dataclasses import replace

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            project = self.project("legacy", "legacy")
            brand = replace(project.brand, pillars=("durable automation",)).with_hash()
            with StateRepository(path) as repo:
                repo.save_project(replace(project, brand=brand))
                # A payload with the right pillars/hash but wrong profile fields
                # must not be trusted as recovery evidence.
                payload = json.loads(repo.events("legacy")[0]["payload_json"])
                payload["brand"]["voice"] = "different"
                repo.conn.execute("UPDATE domain_events SET payload_json=?", (json.dumps(payload),))
                repo.conn.execute("ALTER TABLE brand_profiles DROP COLUMN pillars_json")
                repo.conn.execute("UPDATE schema_meta SET value='4' WHERE key='schema_version'")
            with StateRepository(path) as repo:
                with self.assertRaisesRegex(StorageError, "repair_brand_pillars"):
                    repo.get_project("legacy")
                with self.assertRaises(StorageError):
                    repo.repair_brand_pillars("legacy", ("wrong",))
                repo.repair_brand_pillars("legacy", brand.pillars)
                self.assertEqual(repo.get_project("legacy").brand, brand)

    def test_brand_profile_pillars_round_trip_and_hash(self):
        # Exercise the four-pillar limit and Unicode without changing order.
        pillars = ("local-first", "durable state", "calm automation", "narzędzia twórców")
        project = Project.create(
            project_id="pillars",
            slug="pillars",
            name="Pillars",
            display_name="Pillars",
            voice="plain",
            audience="builders",
            maintainer="team",
            pillars=pillars,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                self.assert_pillars_json_appended(repo)
                stored = repo.get_project("pillars")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, pillars)
                self.assertEqual(stored.brand.profile_hash, project.brand.profile_hash)
                stored_json = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    ("pillars",),
                ).fetchone()[0]
                self.assertEqual(json.loads(stored_json), list(pillars))
            with StateRepository(path) as repo:
                stored = repo.get_project("pillars")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, pillars)
                self.assertEqual(stored.brand.profile_hash, project.brand.profile_hash)
                self.assertEqual(stored.brand.with_hash().profile_hash, project.brand.profile_hash)

    def test_fresh_and_migrated_pillars_columns_have_same_empty_default(self):
        from influenzer.migrations import migrate

        with tempfile.TemporaryDirectory() as tmp:
            with StateRepository(Path(tmp) / "state.db") as repo:
                def pillars_default():
                    return next(
                        row[4] for row in repo.conn.execute("PRAGMA table_info(brand_profiles)")
                        if row[1] == "pillars_json"
                    )

                fresh_default = pillars_default()
                _replace_brand_profiles_with_pre_v5(repo.conn)
                repo.conn.execute(
                    "UPDATE schema_meta SET value=? WHERE key=?", ("4", "schema_version")
                )
                migrate(repo.conn)
                self.assertEqual(pillars_default(), "'[]'")
                self.assertEqual(fresh_default, pillars_default())

    def test_v4_database_gains_brand_profile_pillars(self):
        from influenzer.migrations import SCHEMA_VERSION

        project = self.project("legacy", "legacy")
        brand = project.brand
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute(
                """
                CREATE TABLE projects (
                    project_id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    kind TEXT NOT NULL, created_at TEXT NOT NULL
                )
                """
            )
            conn.executescript(_PRE_V5_BRAND_PROFILES)
            conn.execute(
                """
                CREATE TABLE domain_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
                    event_type TEXT NOT NULL, payload_json TEXT NOT NULL, created_at TEXT NOT NULL,
                    FOREIGN KEY(project_id) REFERENCES projects(project_id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (project.project_id, project.slug, project.name, project.kind, project.created_at),
            )
            conn.execute(
                "INSERT INTO brand_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    brand.project_id,
                    brand.display_name,
                    brand.voice,
                    brand.audience,
                    brand.maintainer,
                    brand.tone,
                    json.dumps(list(brand.disclosures)),
                    brand.revision,
                    brand.profile_hash,
                ),
            )
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '4')")
            conn.commit()
            conn.close()
            with StateRepository(path) as repo:
                self.assertEqual(
                    repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
                    str(SCHEMA_VERSION),
                )
                self.assert_pillars_json_appended(repo)
                stored_json = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    ("legacy",),
                ).fetchone()[0]
                self.assertEqual(json.loads(stored_json), [])
                stored = repo.get_project("legacy")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, ())
                self.assertEqual(stored.brand.profile_hash, brand.profile_hash)
                authored = BrandProfile(
                    project_id=stored.brand.project_id,
                    display_name=stored.brand.display_name,
                    voice=stored.brand.voice,
                    audience=stored.brand.audience,
                    maintainer=stored.brand.maintainer,
                    tone=stored.brand.tone,
                    disclosures=stored.brand.disclosures,
                    pillars=("durable automation",),
                    revision=stored.brand.revision + 1,
                ).with_hash()
                repo.save_brand_profile(authored)
                reread = repo.get_project("legacy")
                assert reread is not None
                self.assertEqual(reread.brand.pillars, ("durable automation",))
                self.assertEqual(reread.brand.profile_hash, authored.profile_hash)
                stored_json = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    ("legacy",),
                ).fetchone()[0]
                self.assertEqual(json.loads(stored_json), ["durable automation"])
                # New projects must use the migrated column layout too, not
                # only the save_brand_profile update path above.
                new_project = Project.create(
                    project_id="after-migration",
                    slug="after-migration",
                    name="After migration",
                    display_name="After migration",
                    voice="plain",
                    audience="builders",
                    maintainer="team",
                    pillars=("local-first", "durable state"),
                )
                repo.save_project(new_project)
                created = repo.get_project(new_project.project_id)
                assert created is not None
                self.assertEqual(created.brand, new_project.brand)
            # Reopening v5 must not replay migration or erase authored pillars.
            with StateRepository(path) as repo:
                reopened = repo.get_project("legacy")
                assert reopened is not None
                self.assertEqual(reopened.brand, authored)
                self.assertEqual(reopened.brand.with_hash().profile_hash, authored.profile_hash)
                self.assertEqual(len(repo.events("legacy")), 1)
                created = repo.get_project(new_project.project_id)
                assert created is not None
                self.assertEqual(created.brand, new_project.brand)
                self.assertEqual(created.brand.with_hash().profile_hash, new_project.brand.profile_hash)

    def test_v0_existing_brand_profiles_gain_pillars_json(self):
        from influenzer.migrations import SCHEMA_VERSION

        project = self.project("legacy-v0", "legacy-v0")
        brand = project.brand
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute(
                """
                CREATE TABLE projects (
                    project_id TEXT PRIMARY KEY, slug TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                    kind TEXT NOT NULL, created_at TEXT NOT NULL
                )
                """
            )
            conn.executescript(_PRE_V5_BRAND_PROFILES)
            conn.execute(
                "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
                (project.project_id, project.slug, project.name, project.kind, project.created_at),
            )
            conn.execute(
                "INSERT INTO brand_profiles VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    brand.project_id,
                    brand.display_name,
                    brand.voice,
                    brand.audience,
                    brand.maintainer,
                    brand.tone,
                    json.dumps(list(brand.disclosures)),
                    brand.revision,
                    brand.profile_hash,
                ),
            )
            conn.commit()
            conn.close()
            with StateRepository(path) as repo:
                self.assertEqual(
                    repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
                    str(SCHEMA_VERSION),
                )
                self.assert_pillars_json_appended(repo)
                stored_json = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    ("legacy-v0",),
                ).fetchone()[0]
                self.assertEqual(json.loads(stored_json), [])
                stored = repo.get_project("legacy-v0")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, ())
                self.assertEqual(stored.brand.profile_hash, brand.profile_hash)
                authored = BrandProfile(
                    project_id=stored.brand.project_id,
                    display_name=stored.brand.display_name,
                    voice=stored.brand.voice,
                    audience=stored.brand.audience,
                    maintainer=stored.brand.maintainer,
                    tone=stored.brand.tone,
                    disclosures=stored.brand.disclosures,
                    pillars=("local-first",),
                    revision=stored.brand.revision + 1,
                ).with_hash()
                repo.save_brand_profile(authored)
                reread = repo.get_project("legacy-v0")
                assert reread is not None
                self.assertEqual(reread.brand.pillars, ("local-first",))
                self.assertEqual(reread.brand.profile_hash, authored.profile_hash)

    def test_save_brand_profile_persists_pillars_and_hash(self):
        project = self.project("pillars-update", "pillars-update")
        pillars = ("local-first", "durable state")
        updated = BrandProfile(
            project_id=project.project_id,
            display_name=project.brand.display_name,
            voice=project.brand.voice,
            audience=project.brand.audience,
            maintainer=project.brand.maintainer,
            tone=project.brand.tone,
            disclosures=project.brand.disclosures,
            pillars=pillars,
            revision=project.brand.revision + 1,
        ).with_hash()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.save_brand_profile(updated)
                stored = repo.get_project(project.project_id)
                assert stored is not None
                self.assertEqual(stored.brand.pillars, pillars)
                self.assertEqual(stored.brand.revision, updated.revision)
                self.assertEqual(stored.brand.profile_hash, updated.profile_hash)
                stored_json = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    (project.project_id,),
                ).fetchone()[0]
                self.assertEqual(json.loads(stored_json), list(pillars))
            with StateRepository(path) as repo:
                stored = repo.get_project(project.project_id)
                assert stored is not None
                self.assertEqual(stored.brand.pillars, pillars)
                self.assertEqual(stored.brand.profile_hash, updated.profile_hash)
                self.assertEqual(stored.brand.with_hash().profile_hash, updated.profile_hash)
                events = repo.events(project.project_id)
                self.assertEqual(len(events), 2)
                self.assertEqual(events[-1]["event_type"], "brand_profile.saved")
                payload = json.loads(events[-1]["payload_json"])
                self.assertEqual(payload["pillars"], list(stored.brand.pillars))
                self.assertEqual(payload["profile_hash"], stored.brand.profile_hash)

    def test_stale_pillars_hash_is_rejected_before_writing(self):
        from dataclasses import replace

        project = self.project("stale-pillars", "stale-pillars")
        stale = replace(project.brand, pillars=("durable automation",))
        with tempfile.TemporaryDirectory() as tmp:
            with StateRepository(Path(tmp) / "state.db") as repo:
                with self.assertRaisesRegex(StorageError, "profile_hash"):
                    repo.save_project(replace(project, brand=stale))
                self.assertIsNone(repo.get_project(project.project_id))
                self.assertEqual(repo.events(project.project_id), [])
                repo.save_project(project)
                with self.assertRaisesRegex(StorageError, "profile_hash"):
                    repo.save_brand_profile(stale)
                self.assertEqual(repo.get_project(project.project_id).brand, project.brand)
                self.assertEqual(len(repo.events(project.project_id)), 1)
                # Rehashing the same authored pillars makes the write valid.
                repo.save_brand_profile(stale.with_hash())
                self.assertEqual(repo.get_project(project.project_id).brand, stale.with_hash())

    def test_reordering_brand_pillars_persists_order_and_changes_hash(self):
        from dataclasses import replace

        project = self.project("ordered-pillars", "ordered-pillars")
        project = replace(
            project,
            brand=replace(project.brand, pillars=("local-first", "durable state")).with_hash(),
        )
        reordered = replace(project.brand, pillars=tuple(reversed(project.brand.pillars))).with_hash()
        # Same revision and same set: order alone must survive storage and hashing.
        self.assertNotEqual(reordered.profile_hash, project.brand.profile_hash)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                self.assertEqual(repo.get_project(project.project_id).brand, project.brand)
                repo.save_brand_profile(reordered)
            with StateRepository(path) as repo:
                stored = repo.get_project(project.project_id)
                self.assertIsNotNone(stored)
                self.assertEqual(stored.brand, reordered)
                self.assertEqual(stored.brand.with_hash().profile_hash, reordered.profile_hash)

    def test_clearing_brand_pillars_persists_empty_tuple_and_new_hash(self):
        from dataclasses import replace

        project = self.project("clear-pillars", "clear-pillars")
        project = replace(
            project,
            brand=replace(project.brand, pillars=("durable automation",)).with_hash(),
        )
        cleared = replace(project.brand, pillars=(), revision=2).with_hash()
        self.assertNotEqual(cleared.profile_hash, project.brand.profile_hash)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.save_brand_profile(cleared)
                raw = repo.conn.execute(
                    "SELECT pillars_json FROM brand_profiles WHERE project_id=?",
                    (project.project_id,),
                ).fetchone()[0]
                self.assertEqual(json.loads(raw), [])
            with StateRepository(path) as repo:
                stored = repo.get_project(project.project_id)
                assert stored is not None
                self.assertEqual(stored.brand, cleared)
                self.assertEqual(stored.brand.pillars, ())
                self.assertEqual(stored.brand.with_hash().profile_hash, cleared.profile_hash)

    def test_corrupt_pillars_json_is_storage_error_not_character_tuple(self):
        project = self.project("corrupt", "corrupt")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ('"durable"', "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ('{"durable":true}', "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("not-json", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("   ", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("null", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("[null]", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("[1]", "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ('[""]', "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ('["a","b","c","d","e"]', "corrupt"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")
                repo.conn.execute("ALTER TABLE brand_profiles DROP COLUMN pillars_json")
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt")

    def test_pillars_json_that_does_not_match_profile_hash_is_storage_error(self):
        project = self.project("hash-mismatch", "hash-mismatch")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ('["durable automation"]', "hash-mismatch"),
                )
                with self.assertRaises(StorageError) as mismatch:
                    repo.get_project("hash-mismatch")
                self.assertIn("profile_hash", str(mismatch.exception))
                self.assertIn("pillars", str(mismatch.exception))
                self.assertNotEqual(
                    BrandProfile(
                        project_id=project.brand.project_id,
                        display_name=project.brand.display_name,
                        voice=project.brand.voice,
                        audience=project.brand.audience,
                        maintainer=project.brand.maintainer,
                        tone=project.brand.tone,
                        disclosures=project.brand.disclosures,
                        pillars=("durable automation",),
                        revision=project.brand.revision,
                    ).with_hash().profile_hash,
                    project.brand.profile_hash,
                )

    def test_wiped_authored_pillars_json_is_storage_error_not_empty_tuple(self):
        pillars = ("durable automation",)
        project = Project.create(
            project_id="wiped-pillars",
            slug="wiped-pillars",
            name="Wiped",
            display_name="Wiped",
            voice="plain",
            audience="builders",
            maintainer="team",
            pillars=pillars,
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.conn.execute(
                    "UPDATE brand_profiles SET pillars_json=? WHERE project_id=?",
                    ("[]", "wiped-pillars"),
                )
            with StateRepository(path) as repo:
                with self.assertRaises(StorageError) as wiped:
                    repo.get_project("wiped-pillars")
                self.assertIn("profile_hash", str(wiped.exception))
                self.assertIn("pillars", str(wiped.exception))

    def test_pre_v5_hash_without_pillars_key_loads_empty_pillars(self):
        project = self.project("legacy-hash", "legacy-hash")
        legacy_hash = content_hash(
            {
                "project_id": project.brand.project_id,
                "display_name": project.brand.display_name,
                "voice": project.brand.voice,
                "audience": project.brand.audience,
                "maintainer": project.brand.maintainer,
                "tone": project.brand.tone,
                "disclosures": list(project.brand.disclosures),
                "revision": project.brand.revision,
            }
        )
        self.assertNotEqual(legacy_hash, project.brand.profile_hash)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                # Build the actual pre-v5 layout, not a v5 row with an old hash.
                repo.conn.execute("ALTER TABLE brand_profiles DROP COLUMN pillars_json")
                repo.conn.execute(
                    "UPDATE brand_profiles SET profile_hash=? WHERE project_id=?",
                    (legacy_hash, "legacy-hash"),
                )
                repo.conn.execute(
                    "UPDATE schema_meta SET value=? WHERE key=?", ("4", "schema_version")
                )
            with StateRepository(path) as repo:
                stored = repo.get_project("legacy-hash")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, ())
                self.assertEqual(stored.brand.profile_hash, legacy_hash)
                self.assert_pillars_json_appended(repo)
                from dataclasses import replace

                updated = replace(
                    stored.brand, pillars=("durable automation",), revision=2
                ).with_hash()
                repo.save_brand_profile(updated)
            with StateRepository(path) as repo:
                stored = repo.get_project("legacy-hash")
                assert stored is not None
                self.assertEqual(stored.brand, updated)
                self.assertEqual(stored.brand.with_hash().profile_hash, updated.profile_hash)

    def test_corrupt_disclosures_json_is_storage_error_not_character_tuple(self):
        project = self.project("corrupt-disclosures", "corrupt-disclosures")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
                repo.conn.execute(
                    "UPDATE brand_profiles SET disclosures_json=? WHERE project_id=?",
                    ('"durable"', "corrupt-disclosures"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt-disclosures")
                repo.conn.execute(
                    "UPDATE brand_profiles SET disclosures_json=? WHERE project_id=?",
                    ("not-json", "corrupt-disclosures"),
                )
                with self.assertRaises(StorageError):
                    repo.get_project("corrupt-disclosures")

    def test_reopened_brand_pillars_gate_linkedin_dressing(self):
        ship_pr = "https://github.com/mikolaj92/influenzer/pull/12"
        pillars = ("durable automation",)
        project = Project.create(
            project_id="app-1",
            slug="app1",
            name="App",
            display_name="Influenzer",
            voice="product",
            audience="builders",
            maintainer="team",
            pillars=pillars,
        )
        fake = Score(
            brief_id="b-pillar-restart",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.LINKEDIN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.LINKEDIN].wave,
            canon_url=ARENAS[ArenaId.LINKEDIN].canon_url,
        )
        unrelated = Brief.create(
            project_id="app-1",
            brief_id="b-pillar-restart",
            preferred_arena=ArenaId.LINKEDIN,
            claims_ship=False,
            tryable=True,
            story_kind=StoryKind.MAJOR,
            facts=(
                Fact(text="The queue got a cleaner dashboard"),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=ship_pr),
            ),
        )
        matching = Brief.create(
            project_id="app-1",
            brief_id="b-pillar-restart",
            preferred_arena=ArenaId.LINKEDIN,
            claims_ship=False,
            tryable=True,
            story_kind=StoryKind.MAJOR,
            facts=(
                Fact(text="Durable automation makes recovery explicit"),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=ship_pr),
            ),
        )
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(project)
            with StateRepository(path) as repo:
                stored = repo.get_project("app-1")
                assert stored is not None
                self.assertEqual(stored.brand.pillars, pillars)
                self.assertEqual(stored.brand.profile_hash, project.brand.profile_hash)
                self.assertIsNone(dress_brief(unrelated, fake, brand=stored.brand))
                draft = dress_brief(matching, fake, brand=stored.brand)
                self.assertIsNotNone(draft)
                assert draft is not None
                self.assertTrue(draft.body.startswith("Durable automation makes recovery explicit"))

    def test_reopen_and_migration_preserve_events(self):
        from influenzer.migrations import SCHEMA_VERSION

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(self.project("p", "project"))
            with StateRepository(path) as repo:
                self.assertIsNotNone(repo.get_project("p"))
                self.assertEqual(repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0], str(SCHEMA_VERSION))
                self.assertEqual(len(repo.events("p")), 1)

    def test_v1_database_gains_brief_tables(self):
        from influenzer.migrations import SCHEMA_VERSION, _SCHEMA

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.executescript(_SCHEMA)
            _replace_brand_profiles_with_pre_v5(conn)
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '1')")
            conn.commit()
            conn.close()
            with StateRepository(path) as repo:
                self.assertEqual(
                    repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
                    str(SCHEMA_VERSION),
                )
                repo.conn.execute("SELECT * FROM briefs")
                repo.conn.execute("SELECT * FROM operator_scores")
                repo.conn.execute("SELECT * FROM operator_drafts")
                cols = [row[1] for row in repo.conn.execute("PRAGMA table_info(operator_drafts)")]
                self.assertIn("gate_verdict", cols)
                self.assert_pillars_json_appended(repo)

    def test_v2_database_gains_gate_verdict(self):
        from influenzer.migrations import SCHEMA_VERSION, _SCHEMA, _V2_SCHEMA

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.executescript(_SCHEMA)
            conn.executescript(_V2_SCHEMA)
            _replace_brand_profiles_with_pre_v5(conn)
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '2')")
            conn.commit()
            conn.close()
            with StateRepository(path) as repo:
                self.assertEqual(
                    repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
                    str(SCHEMA_VERSION),
                )
                cols = [row[1] for row in repo.conn.execute("PRAGMA table_info(operator_drafts)")]
                self.assertIn("gate_verdict", cols)
                repo.conn.execute("SELECT * FROM hom_watch")
                self.assert_pillars_json_appended(repo)

    def test_v3_database_gains_hom_watch(self):
        from influenzer.migrations import SCHEMA_VERSION, _SCHEMA, _V2_SCHEMA, _V3_SCHEMA

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.executescript(_SCHEMA)
            conn.executescript(_V2_SCHEMA)
            conn.executescript(_V3_SCHEMA)
            _replace_brand_profiles_with_pre_v5(conn)
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '3')")
            conn.commit()
            conn.close()
            with StateRepository(path) as repo:
                self.assertEqual(
                    repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0],
                    str(SCHEMA_VERSION),
                )
                repo.conn.execute("SELECT * FROM hom_watch")
                self.assertIsNone(repo.get_hom_watch())
                self.assert_pillars_json_appended(repo)

    def test_v4_stamp_without_brand_profiles_is_migration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '4')")
            conn.commit()
            conn.close()
            with self.assertRaises(StateUnusable) as missing:
                StateRepository(path)
            self.assertIsInstance(missing.exception.__cause__, MigrationError)
            self.assertTrue(is_state_unusable(missing.exception))

    def test_v4_brand_profiles_view_is_migration_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '4')")
            conn.execute("CREATE VIEW brand_profiles AS SELECT 1 AS project_id")
            conn.commit()
            conn.close()
            with self.assertRaises(StateUnusable) as view:
                StateRepository(path)
            self.assertIsInstance(view.exception.__cause__, MigrationError)
            self.assertTrue(is_state_unusable(view.exception))

    def test_future_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '999')")
            conn.commit()
            conn.close()
            with self.assertRaises(StateUnusable) as future:
                StateRepository(path)
            self.assertIsInstance(future.exception.__cause__, MigrationError)
            self.assertTrue(is_state_unusable(future.exception))

    def test_only_one_active_attempt_per_plan(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(self.project("p", "project"))
            account = PlatformAccount("p", "acct", "x", "@x", None, "env:X_TOKEN", AccountStatus.CONNECTED)
            repo.save_account(account)
            revision = self.revision("p")
            repo.save_content_revision(revision)
            plan = PublishPlan("p", "plan", "rev-1", revision.content_hash, "acct", "x", "hello", PlanStatus.PROPOSED, None, "2026-01-01T00:00:00Z", "op-1")
            repo.save_plan(plan)
            repo.save_attempt(PublicationAttempt("p", "attempt-1", "plan", "op-1", AttemptStatus.PENDING, "2026-01-01T00:00:00Z"))
            with self.assertRaises(sqlite3.IntegrityError):
                repo.save_attempt(PublicationAttempt("p", "attempt-2", "plan", "op-1", AttemptStatus.RUNNING, "2026-01-01T00:00:01Z"))

    def test_artifact_hash_corruption_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            meta = repo.register_artifact(b"immutable", media_type="text/plain")
            artifact = Path(tmp) / "artifacts" / "sha256" / meta["digest"]
            artifact.write_bytes(b"tampered")
            with self.assertRaises(ArtifactCorruptionError):
                repo.artifacts.verify(meta["digest"])

    def test_spliced_inbound_sql_is_silence(self) -> None:
        slug = "owner/name'; DROP TABLE projects;--"
        excerpt = "How do I install this?'; DELETE FROM briefs;--"
        gh_json = '{"repo":"owner/name","facts":[{"text":"boom"}]}'
        self.assertTrue(sql_has_inbound_literal(f"SELECT * FROM hom_watch WHERE repo_slug='{slug}'"))
        self.assertTrue(sql_has_inbound_literal(f"SELECT * FROM briefs WHERE facts_json='{excerpt}'"))
        self.assertTrue(sql_has_inbound_literal(f"INSERT INTO domain_events(payload_json) VALUES ('{gh_json}')"))
        self.assertFalse(sql_has_inbound_literal("SELECT * FROM hom_watch WHERE repo_slug=?"))
        self.assertFalse(
            sql_has_inbound_literal(
                "SELECT * FROM operator_drafts WHERE coalesce(gate_verdict, '') != ?"
            )
        )
        with self.assertRaises(UnboundSqlError):
            reject_unbound_sql(f"SELECT * FROM projects WHERE slug='{slug}'")

    def test_inbound_slug_excerpt_and_gh_json_are_bound(self) -> None:
        slug = "owner/name'; DROP TABLE projects;--"
        excerpt = "How do I install this?'; DELETE FROM briefs;--"
        gh_json = '{"repo":"owner/name","body":"boom"}'
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(self.project("p", "project"))
            repo.set_hom_watch("p", slug, created_at="2026-01-01T00:00:00Z")
            repo.save_brief(
                Brief.create(
                    project_id="p",
                    brief_id="fb-bound",
                    facts=(Fact(text=excerpt, artifact_url="https://github.com/owner/name/issues/1#issuecomment-1"),),
                    story_kind=StoryKind.HARD_ISSUE,
                    source="github-feedback",
                )
            )
            repo.record_github_scan("p", slug, scanned_at="2026-01-01T00:00:00Z")
            repo.append_receipt(
                project_id="p",
                receipt_id="gh-json",
                status="scanned",
                payload={"repo": slug, "excerpt": excerpt, "raw": gh_json},
                created_at="2026-01-01T00:00:00Z",
            )
            watch = repo.get_hom_watch()
            assert watch is not None
            self.assertEqual(watch["repo"], slug)
            stored = repo.get_brief("p", "fb-bound")
            assert stored is not None
            self.assertEqual(stored.facts[0].text, excerpt)
            events = repo.events("p")
            self.assertTrue(any(row["event_type"] == "github.scanned" for row in events))
            receipt = repo.conn.execute(
                "SELECT payload_json FROM receipts WHERE receipt_id=?",
                ("gh-json",),
            ).fetchone()
            self.assertIn(slug, receipt["payload_json"])
            self.assertIn(excerpt, receipt["payload_json"])
            tables = {
                row[0]
                for row in repo.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
            }
            self.assertIn("projects", tables)
            self.assertIn("briefs", tables)
            with self.assertRaises(UnboundSqlError):
                repo.conn.execute(f"SELECT * FROM hom_watch WHERE repo_slug='{slug}'")
            with self.assertRaises(UnboundSqlError):
                repo.conn.execute(f"SELECT * FROM briefs WHERE facts_json LIKE '%{excerpt}%'")
            with self.assertRaises(UnboundSqlError):
                repo.conn.execute(f"SELECT * FROM receipts WHERE payload_json='{gh_json}'")


class TickLockTests(unittest.TestCase):
    def test_second_acquire_is_silence_until_release(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = Path(tmp) / "state.db"
            first = try_acquire_tick_lock(state)
            self.assertIsNotNone(first)
            assert first is not None
            lock = tick_lock_path(state)
            self.assertEqual(lock, (Path(tmp) / "tick.lock").resolve())
            self.assertTrue(lock.is_file())
            self.assertEqual(lock.stat().st_mode & 0o777, 0o600)
            self.assertIsNone(try_acquire_tick_lock(state))
            first.close()
            second = try_acquire_tick_lock(state)
            self.assertIsNotNone(second)
            assert second is not None
            second.close()


if __name__ == "__main__":
    unittest.main()
