from __future__ import annotations

import io
import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from github_survey import GhCall
from github_pack.pack import README_WITHOUT_QUICKSTART_REASON
from influenzer.brief_admit import SOURCE, open_story_reason
from influenzer.cli import main
from influenzer.config import load_config
from influenzer.hom import Brief, Fact
from influenzer.playbook import ArenaId, LIVING_STACK_REASON, SECRET_REASON, StoryKind
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from tests.gh_scripts import NOW, REPO, SHIP_PR, b64_readme, repo_json, ship_script, ScriptedGh


class GitHubScanCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        self.assertEqual(main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "project",
                    "create",
                    "--id",
                    "app-1",
                    "--slug",
                    "app",
                    "--name",
                    "App",
                    "--display-name",
                    "App",
                    "--voice",
                    "v",
                    "--audience",
                    "a",
                    "--maintainer",
                    "mikolaj92",
                    "--kind",
                    "app",
                ]
            ),
            0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cli_scan_writes_one_pending_brief(self) -> None:
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("github_survey.survey.parse_now", return_value=fixed),
            patch("influenzer.brief_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["brief_id"], "scan-v0-1-0")
        self.assertFalse(payload["published"])
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            stored = repo.get_brief("app-1", "scan-v0-1-0")
            assert stored is not None
            self.assertEqual(stored.source, SOURCE)
            self.assertEqual(stored.status, "pending")

    def test_cli_prose_install_is_silence_not_a_pending_brief(self) -> None:
        prose = (
            "# Demo\n\nInstall with pip install influenzer, then uv run the tick.\n"
            "\n![demo](docs/demo.gif)\n"
        )
        fake = ScriptedGh(ship_script(readme=GhCall(0, b64_readme(prose))))
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("github_survey.survey.parse_now", return_value=fixed),
            patch("influenzer.brief_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "noop")
        self.assertEqual(payload["reason"], README_WITHOUT_QUICKSTART_REASON)
        self.assertFalse(payload["published"])
        self.assertIsNone(payload.get("brief_id"))
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(repo.list_briefs("app-1"), [])

    def test_cli_invalid_repo_fails_closed_without_scan(self) -> None:
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    "not a repo",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("owner/name", buf.getvalue())

    def test_cli_missing_project_fails(self) -> None:
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "missing",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("project not found", buf.getvalue())

    def test_cli_secret_in_scan_is_silence_not_a_pending_brief(self) -> None:
        leak = "Bearer " + "sk" + "-" + "this-is-not-a-live-key-1"
        fake = ScriptedGh(ship_script(repo=GhCall(0, repo_json(description=f"docs mention {leak}"))))
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("github_survey.survey.parse_now", return_value=fixed),
            patch("influenzer.brief_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "noop")
        self.assertEqual(payload["reason"], SECRET_REASON)
        self.assertFalse(payload["published"])
        self.assertIsNone(payload.get("brief_id"))
        self.assertNotIn(leak, buf.getvalue())
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(repo.list_briefs("app-1"), [])

    def test_cli_scan_on_second_project_is_silence_while_first_is_pending(self) -> None:
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "project",
                    "create",
                    "--id",
                    "app-2",
                    "--slug",
                    "other",
                    "--name",
                    "Other",
                    "--display-name",
                    "Other",
                    "--voice",
                    "v",
                    "--audience",
                    "a",
                    "--maintainer",
                    "mikolaj92",
                    "--kind",
                    "app",
                ]
            ),
            0,
        )
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            repo.save_brief(
                Brief.create(
                    project_id="app-1",
                    brief_id="manual-1",
                    facts=(Fact(text="already working a story"),),
                    story_kind=StoryKind.MAJOR,
                    source="cli",
                )
            )
            self.assertEqual(open_story_reason(repo, "app-2"), "pending_brief")
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("github_survey.survey.parse_now", return_value=fixed),
            patch("influenzer.brief_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-2",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "noop")
        self.assertEqual(payload["reason"], "pending_brief")
        self.assertFalse(payload["published"])
        self.assertIsNone(payload.get("brief_id"))
        self.assertEqual(fake.calls, [])
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(repo.list_briefs("app-2"), [])
            self.assertEqual(len(repo.list_pending_briefs()), 1)

    def test_cli_scan_on_living_github_stack_is_silence(self) -> None:
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            repo.save_brief(
                Brief.create(
                    project_id="app-1",
                    brief_id="prior-github",
                    facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
                    story_kind=StoryKind.MAJOR,
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.GITHUB,
                )
            )
            cfg = load_config(self.config)
            tick(repo, cfg, due=(), now=NOW)
            self.assertEqual(repo.living_stack_arena("app-1", NOW), ArenaId.GITHUB)
            self.assertEqual(open_story_reason(repo, "app-1", NOW), LIVING_STACK_REASON)
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("influenzer.brief_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "noop")
        self.assertEqual(payload["reason"], LIVING_STACK_REASON)
        self.assertFalse(payload["published"])
        self.assertIsNone(payload.get("brief_id"))
        self.assertEqual(fake.calls, [])
