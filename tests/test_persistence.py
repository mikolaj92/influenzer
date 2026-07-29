import sqlite3
import tempfile
import unittest
from pathlib import Path

from influenzer.domain import AttemptStatus, ContentStatus, Project
from influenzer.domain import ContentRevision, PlatformAccount, AccountStatus
from influenzer.domain import PublishPlan, PlanStatus, PublicationAttempt
from influenzer.storage import ArtifactCorruptionError, StateRepository


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
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            with StateRepository(path) as repo:
                repo.save_project(self.project("p", "project"))
            with StateRepository(path) as repo:
                self.assertIsNotNone(repo.get_project("p"))
                self.assertEqual(repo.conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0], "1")
                self.assertEqual(len(repo.events("p")), 1)

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


if __name__ == "__main__":
    unittest.main()
