from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from influenzer.cli import main
from influenzer.domain import (
    AccountStatus,
    ContentRevision,
    ContentStatus,
    PlanStatus,
    PlatformAccount,
    Project,
    PublishPlan,
    content_hash,
)
from influenzer.storage import StateRepository


class XHandoffTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        self.assertEqual(main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)
        project = Project.create(
            project_id="app-1",
            slug="app",
            name="App",
            display_name="App",
            voice="plain",
            audience="builders",
            maintainer="me",
        )
        revision = ContentRevision(
            project_id="app-1",
            content_id="content-1",
            revision_id="revision-1",
            body="Shipping today & learning in public",
            kind="post",
            status=ContentStatus.READY,
            source="manual",
            source_digest=content_hash({"source": "manual"}),
            created_at="2026-01-01T00:00:00Z",
        ).with_hash()
        account = PlatformAccount(
            project_id="app-1",
            account_id="x-1",
            platform="x",
            handle="@app",
            host=None,
            credential_ref="env:X_UNUSED_FOR_HANDOFF",
            status=AccountStatus.DISCONNECTED,
        )
        plan = PublishPlan(
            project_id="app-1",
            plan_id="plan-1",
            content_revision_id=revision.revision_id,
            content_hash=revision.content_hash,
            platform_account_id=account.account_id,
            platform="x",
            body=revision.body,
            status=PlanStatus.APPROVED,
            scheduled_at=None,
            created_at="2026-01-01T00:00:00Z",
            operation_key="op-1",
        )
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            repo.save_project(project)
            repo.save_content_revision(revision)
            repo.save_account(account)
            repo.save_plan(plan)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_cli(self, *args: str) -> tuple[int, dict[str, object]]:
        output = io.StringIO()
        errors = io.StringIO()
        with redirect_stdout(output), redirect_stderr(errors):
            code = main(["--config", str(self.config), *args])
        return code, json.loads(output.getvalue() or errors.getvalue())

    def test_handoff_opens_intent_without_claiming_publication(self) -> None:
        with patch("influenzer.cli.webbrowser.open", return_value=True) as opened:
            code, result = self.run_cli(
                "publish", "handoff", "--project-id", "app-1", "--plan-id", "plan-1"
            )
        self.assertEqual(code, 0)
        self.assertEqual(result["plan_status"], "handoff_opened")
        self.assertEqual(result["published"], False)
        intent_url = str(result["intent_url"])
        self.assertTrue(intent_url.startswith("https://twitter.com/intent/tweet?"))
        self.assertIn("Shipping+today+%26+learning+in+public", intent_url)
        opened.assert_called_once_with(intent_url, new=2)

        with StateRepository(self.home / "state.db") as repo:
            self.assertEqual(repo.get_plan("app-1", "plan-1").status, PlanStatus.HANDOFF_OPENED)
            receipts = repo.conn.execute("SELECT status FROM receipts WHERE plan_id='plan-1' ORDER BY receipt_id").fetchall()
            self.assertEqual({row["status"] for row in receipts}, {"handoff_ready", "handoff_opened"})

    def test_confirmation_requires_matching_x_status_url(self) -> None:
        with patch("influenzer.cli.webbrowser.open", return_value=True):
            self.run_cli("publish", "handoff", "--project-id", "app-1", "--plan-id", "plan-1")
        code, result = self.run_cli(
            "publish",
            "confirm",
            "--project-id",
            "app-1",
            "--plan-id",
            "plan-1",
            "--url",
            "https://x.com/app/status/123456789",
        )
        self.assertEqual(code, 0)
        self.assertEqual(result["plan_status"], "published_confirmed")
        self.assertEqual(result["provider_id"], "123456789")
        with StateRepository(self.home / "state.db") as repo:
            self.assertEqual(repo.get_plan("app-1", "plan-1").status, PlanStatus.PUBLISHED_CONFIRMED)

    def test_duplicate_receipt_rolls_back_plan_transition(self) -> None:
        with StateRepository(self.home / "state.db") as repo:
            repo.append_receipt(
                project_id="app-1",
                receipt_id="handoff-ready:plan-1",
                plan_id="plan-1",
                status="seed",
                payload={},
                created_at="2026-01-01T00:00:00Z",
            )
        with patch("influenzer.cli.webbrowser.open", return_value=True) as opened:
            code, _ = self.run_cli(
                "publish", "handoff", "--project-id", "app-1", "--plan-id", "plan-1"
            )
        opened.assert_not_called()
        self.assertEqual(code, 1)
        with StateRepository(self.home / "state.db") as repo:
            self.assertEqual(repo.get_plan("app-1", "plan-1").status, PlanStatus.APPROVED)

    def test_failed_browser_open_and_invalid_confirmation_do_not_advance(self) -> None:
        with patch("influenzer.cli.webbrowser.open", return_value=False):
            code, _ = self.run_cli(
                "publish", "handoff", "--project-id", "app-1", "--plan-id", "plan-1"
            )
        self.assertEqual(code, 1)
        with StateRepository(self.home / "state.db") as repo:
            self.assertEqual(repo.get_plan("app-1", "plan-1").status, PlanStatus.HANDOFF_READY)
            self.assertEqual(repo.conn.execute("SELECT status FROM receipts WHERE receipt_id='handoff-ready:plan-1'").fetchone()["status"], "handoff_ready")

        with patch("influenzer.cli.webbrowser.open", return_value=True):
            self.run_cli("publish", "handoff", "--project-id", "app-1", "--plan-id", "plan-1")
        code, _ = self.run_cli(
            "publish",
            "confirm",
            "--project-id",
            "app-1",
            "--plan-id",
            "plan-1",
            "--url",
            "https://example.com/app/status/123",
        )
        self.assertEqual(code, 1)
        with StateRepository(self.home / "state.db") as repo:
            self.assertEqual(repo.get_plan("app-1", "plan-1").status, PlanStatus.HANDOFF_OPENED)


if __name__ == "__main__":
    unittest.main()
