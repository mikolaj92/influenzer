from __future__ import annotations

import io
import json
import shlex
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from influenzer.cli import main
from influenzer.config import load_config
from influenzer.storage import StateRepository
from influenzer.tick import main as tick_main
from influenzer.tick_all import main as tick_all_main

TMP_DEMO_HOME = "/tmp/influenzer"


def _readme_demo_commands(readme: str) -> list[str]:
    marker = "## 3-minute local demo"
    heading = readme.index(marker)
    fence = readme.index("```bash", heading)
    body_start = readme.index("\n", fence) + 1
    body_end = readme.index("```", body_start)
    commands: list[str] = []
    buf: list[str] = []
    for line in readme[body_start:body_end].splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        if stripped.endswith("\\"):
            buf.append(stripped[:-1].rstrip())
            continue
        buf.append(stripped)
        commands.append(" ".join(buf))
        buf = []
    if buf:
        commands.append(" ".join(buf))
    return commands


def _demo_argv(command: str, *, config: Path, home: Path) -> tuple[str, list[str]]:
    argv = [
        token.replace(TMP_DEMO_HOME, str(home))
        for token in shlex.split(command)
    ]
    if argv[:2] != ["uv", "run"]:
        raise AssertionError(f"demo command must start with uv run: {command}")
    prog = argv[2]
    rest = argv[3:]
    rewritten: list[str] = []
    skip_next = False
    for token in rest:
        if skip_next:
            skip_next = False
            continue
        if token == "--config":
            rewritten.extend(["--config", str(config)])
            skip_next = True
            continue
        rewritten.append(token)
    return prog, rewritten


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
            self.assertEqual(project.brand.maintainer, "mikolaj92")

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
                "#ad",
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
        self.assertIn('--fact "Local tick scores briefs and emits a draft"', readme)
        self.assertIn('--fact "Dry-run still default"', readme)
        self.assertNotIn("mikolaj92/influenzer/pull/1", readme)
        after = (root / "after-install.md").read_text(encoding="utf-8")
        self.assertIn("uv run influenzer", after)
        self.assertNotIn("python -m influenzer.cli", after)
        self.assertNotIn("mikolaj92/influenzer/pull/1", after)

    def test_readme_demo_commands_leave_a_wearable_hn_angle(self) -> None:
        root = Path(__file__).resolve().parents[1]
        readme = (root / "README.md").read_text(encoding="utf-8")
        commands = _readme_demo_commands(readme)
        self.assertGreaterEqual(len(commands), 8)
        blob = " ".join(commands)
        self.assertIn("brief ingest", blob)
        self.assertIn("brief show", blob)
        self.assertIn("angle", blob)
        ship = next(cmd for cmd in commands if "b-ship" in cmd and "brief ingest" in cmd)
        facts: list[str] = []
        take_fact = False
        for token in shlex.split(ship):
            if take_fact:
                facts.append(token)
                take_fact = False
                continue
            take_fact = token == "--fact"
        self.assertGreaterEqual(len(facts), 2, "HN demo needs title + first-comment backstory")
        human, backstory = facts[0], facts[1]
        show: dict[str, object] | None = None
        angle: dict[str, object] | None = None
        for command in commands:
            prog, argv = _demo_argv(command, config=self.config, home=self.home)
            buf = io.StringIO()
            with redirect_stdout(buf):
                if prog == "influenzer":
                    code = main(argv)
                elif prog == "influenzer-tick-all":
                    code = tick_all_main(argv)
                elif prog == "influenzer-tick":
                    code = tick_main(argv)
                else:
                    self.fail(f"unexpected demo program: {prog}")
            self.assertEqual(code, 0, command)
            tokens = argv[2:] if argv[:1] == ["--config"] else argv
            if tokens[:2] == ["brief", "show"]:
                show = json.loads(buf.getvalue())
            elif tokens[:1] == ["angle"]:
                angle = json.loads(buf.getvalue())
        self.assertIsNotNone(show)
        self.assertIsNotNone(angle)
        assert show is not None and angle is not None
        self.assertEqual(show["status"], "ok")
        self.assertEqual(show["brief_id"], "b-ship")
        self.assertEqual(show["verdict"], "draft")
        self.assertEqual(show["arena"], "hn")
        self.assertIn("body", show)
        self.assertTrue(str(show["body"]).startswith("Show HN:"))
        self.assertIn(human, str(show["body"]))
        self.assertIn(backstory, str(show["body"]))
        self.assertIn("https://github.com/mikolaj92/influenzer", str(show["body"]))
        self.assertNotIn("/pull/", str(show["body"]))
        self.assertEqual(angle["status"], "ok")
        self.assertFalse(angle["empty"])
        self.assertFalse(angle["published"])
        self.assertEqual(angle["body"], show["body"])
        self.assertEqual(
            angle["body"],
            f"Show HN: {human}\n\nhttps://github.com/mikolaj92/influenzer\n\n{backstory}",
        )


if __name__ == "__main__":
    unittest.main()
