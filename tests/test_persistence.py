import sqlite3
import tempfile
import unittest
from pathlib import Path

from influenzer.domain import AttemptStatus, ContentStatus, Project
from influenzer.domain import ContentRevision, PlatformAccount, AccountStatus
from influenzer.domain import PublishPlan, PlanStatus, PublicationAttempt
from influenzer.hom import Brief, Fact
from influenzer.playbook import StoryKind
from influenzer.storage import (
    ArtifactCorruptionError,
    StateRepository,
    UnboundSqlError,
    reject_unbound_sql,
    sql_has_inbound_literal,
)


class PersistenceTests(unittest.TestCase):
    def project(self, project_id: str, slug: str, kind: str = "app") -> Project:
        return Project.create(project_id=project_id, slug=slug, name=slug.title(), display_name=slug, voice="plain", audience="builders", maintainer="team", kind=kind)

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

    def test_v2_database_gains_gate_verdict(self):
        from influenzer.migrations import SCHEMA_VERSION, _SCHEMA, _V2_SCHEMA

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.executescript(_SCHEMA)
            conn.executescript(_V2_SCHEMA)
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

    def test_v3_database_gains_hom_watch(self):
        from influenzer.migrations import SCHEMA_VERSION, _SCHEMA, _V2_SCHEMA, _V3_SCHEMA

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.executescript(_SCHEMA)
            conn.executescript(_V2_SCHEMA)
            conn.executescript(_V3_SCHEMA)
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

    def test_future_schema_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            conn = sqlite3.connect(path)
            conn.execute("CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            conn.execute("INSERT INTO schema_meta VALUES ('schema_version', '999')")
            conn.commit()
            conn.close()
            with self.assertRaises(RuntimeError):
                StateRepository(path)

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


if __name__ == "__main__":
    unittest.main()
