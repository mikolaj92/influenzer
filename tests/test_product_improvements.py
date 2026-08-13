from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from influenzer.cli import main
from influenzer.config import load_config
from influenzer.storage import StateRepository


class InfluenzerInitDemoTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "workspace"
        self.config = self.home / "config.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_creates_workspace_and_state_db(self) -> None:
        code = main(["--config", str(self.config), "init", "--home", str(self.home)])
        self.assertEqual(code, 0)
        self.assertTrue(self.config.exists())
        self.assertTrue((self.home / "state.db").exists())
        cfg = load_config(str(self.config))
        self.assertEqual(cfg.home, self.home)
        self.assertFalse(cfg.scheduler_live_enabled)

    def test_project_create_and_show_roundtrip(self) -> None:
        main(["--config", str(self.config), "init", "--home", str(self.home)])
        code = main(
            [
                "--config",
                str(self.config),
                "project",
                "create",
                "--id",
                "builder-1",
                "--slug",
                "mikolaj",
                "--name",
                "Mikolaj",
                "--display-name",
                "Mikolaj",
                "--voice",
                "builder",
                "--audience",
                "builders",
                "--maintainer",
                "mikolaj92",
                "--kind",
                "builder",
            ]
        )
        self.assertEqual(code, 0)
        code = main(["--config", str(self.config), "project", "show", "--id", "builder-1"])
        self.assertEqual(code, 0)
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            project = repo.get_project("builder-1")
            self.assertIsNotNone(project)
            assert project is not None
            self.assertEqual(project.kind, "builder")

    def test_paid_campaign_requires_budget_and_disclosure(self) -> None:
        main(["--config", str(self.config), "init", "--home", str(self.home)])
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
                "m",
            ]
        )
        bad = main(
            [
                "--config",
                str(self.config),
                "campaign",
                "create",
                "--project-id",
                "app-1",
                "--campaign-id",
                "c1",
                "--name",
                "Ads",
                "--kind",
                "paid",
            ]
        )
        self.assertEqual(bad, 1)
        good = main(
            [
                "--config",
                str(self.config),
                "campaign",
                "create",
                "--project-id",
                "app-1",
                "--campaign-id",
                "c1",
                "--name",
                "Ads",
                "--kind",
                "paid",
                "--budget-amount",
                "50",
                "--budget-currency",
                "USD",
                "--disclosure",
                "ad",
            ]
        )
        self.assertEqual(good, 0)

    def test_docs_and_ci_exist(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertTrue((root / "README.md").exists())
        self.assertTrue((root / "after-install.md").exists())
        self.assertTrue((root / "plugin.yaml").exists())
        plugin = (root / "plugin.yaml").read_text(encoding="utf-8")
        self.assertIn("name: influenzer", plugin)
        readme = (root / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("hermes plugins install", readme)
        self.assertIn("uv sync", readme)
        self.assertIn("uv run influenzer", readme)
        self.assertIn("--artifact-url https://github.com/mikolaj92/influenzer", readme)
        self.assertIn("--claim-ship", readme)
        self.assertNotIn("mikolaj92/influenzer/pull/1", readme)
        after = (root / "after-install.md").read_text(encoding="utf-8")
        self.assertIn("uv run influenzer", after)
        self.assertNotIn("python -m influenzer.cli", after)
        self.assertNotIn("mikolaj92/influenzer/pull/1", after)


if __name__ == "__main__":
    unittest.main()
