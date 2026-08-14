from __future__ import annotations

import io
import json
import tomllib
import unittest
from argparse import ArgumentParser
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from github_survey import GhCall

from influenzer.brief_admit import SOURCE
from influenzer.cli import main as cli_main
from influenzer.cli import setup_parser
from influenzer.config import Config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from influenzer.hom_watch import get_watch, interval_tick, set_watch, show_watch
from influenzer.host import HostPower
from influenzer.playbook import StoryKind
from influenzer.storage import StateRepository
from influenzer.tick import guarded_tick, loop_ticks, main as tick_main
from tests.gh_scripts import NOW, REPO, SHIP_PR, ScriptedGh, ship_script

ALWAYS_ON = HostPower(has_battery=False, source="test")


def _import_lines(path: Path) -> list[str]:
    found: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            found.append(stripped)
    return found


def _project(repo: StateRepository, project_id: str = "app-1") -> None:
    repo.save_project(
        Project.create(
            project_id=project_id,
            slug=project_id.replace("-", ""),
            name="App",
            display_name="App",
            voice="product",
            audience="builders",
            maintainer="mikolaj92",
            kind="app",
        )
    )


class HomWatchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cfg = Config(home=self.home, scheduler_live_enabled=False)
        write_config(self.home / "config.json", self.cfg)
        self.repo = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        _project(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def _tick(self, script: dict | None = None, **kwargs: Any) -> tuple[dict[str, Any], ScriptedGh]:
        fake = ScriptedGh(script or ship_script())
        kwargs.setdefault("allow_hom_pass", True)
        kwargs.setdefault("now", NOW)
        with (
            patch("subprocess.run", side_effect=AssertionError("watch tick must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("watch tick must not fetch")),
        ):
            out = interval_tick(self.repo, self.cfg, gh=fake, **kwargs)
        return out, fake

    def test_no_watch_tick_scores_only_without_gh(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
                story_kind=StoryKind.MAJOR,
                claims_ship=True,
                tryable=True,
                source="cli",
            )
        )
        out, fake = self._tick()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["operator"]["processed"], 1)
        self.assertNotIn("scan", out)
        self.assertNotIn("angle", out)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))
        self.assertFalse(out.get("published", False))
        self.assertFalse(out["mutated"])
        self.assertFalse(out["operator"]["published"])
        self.assertFalse(self.cfg.scheduler_live_enabled)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_watch_not_due_scores_only_without_gh(self) -> None:
        set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        self.repo.record_github_scan("app-1", REPO, scanned_at=NOW)
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
                story_kind=StoryKind.MAJOR,
                claims_ship=True,
                tryable=True,
                source="cli",
            )
        )
        out, fake = self._tick()
        self.assertEqual(out["operator"]["processed"], 1)
        self.assertNotIn("scan", out)
        self.assertNotIn("angle", out)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))
        self.assertFalse(out.get("published", False))
        self.assertFalse(out["operator"]["published"])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_watch_due_ship_is_at_most_one_brief_then_one_angle(self) -> None:
        set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        out, fake = self._tick()
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["scan"]["status"], "admitted")
        self.assertEqual(out["scan"]["brief_id"], "scan-v0-1-0")
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        stored = self.repo.get_brief("app-1", "scan-v0-1-0")
        assert stored is not None
        self.assertEqual(stored.source, SOURCE)
        self.assertEqual(out["tick"]["scored"], 1)
        self.assertEqual(out["angle"]["status"], "ok")
        self.assertFalse(out["angle"]["empty"])
        self.assertTrue(out["angle"]["body"].startswith("Show HN:"))
        self.assertNotIn("Costume:", out["angle"]["body"])
        self.assertTrue(fake.calls)
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertFalse(self.cfg.scheduler_live_enabled)
        self.assertFalse((self.home / "runtime.db").exists())

        again, fake2 = self._tick()
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertNotIn("scan", again)
        self.assertEqual(again["operator"]["processed"], 0)
        self.assertEqual(fake2.calls, [])
        self.assertFalse(again.get("published", False))

    def test_watch_open_story_scores_only_without_gh(self) -> None:
        set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
                story_kind=StoryKind.MAJOR,
                claims_ship=True,
                tryable=True,
                source="cli",
            )
        )
        out, fake = self._tick()
        self.assertEqual(out["operator"]["processed"], 1)
        self.assertNotIn("scan", out)
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))
        self.assertFalse(out.get("published", False))
        self.assertFalse(out["operator"]["published"])

    def test_bad_gh_bytes_are_empty_look_and_loop_lives(self) -> None:
        set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        out, fake = self._tick({"repo": GhCall(0, "not-json")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertTrue(fake.calls)

        n = {"i": 0}

        def tick_once() -> dict:
            n["i"] += 1
            if n["i"] == 1:
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")
            return {"status": "ok", "n": n["i"], "mutated": False, "published": False}

        results = loop_ticks(
            guarded_tick(tick_once, supervise=True),
            interval=1,
            max_ticks=2,
            sleep=lambda _n: None,
        )
        self.assertEqual(results[0]["status"], "failed")
        self.assertFalse(results[0]["mutated"])
        self.assertEqual(results[1]["n"], 2)

    def test_once_without_flag_does_not_scan(self) -> None:
        set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        out, fake = self._tick(allow_hom_pass=False)
        self.assertNotIn("scan", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse(out.get("published", False))
        self.assertFalse((self.home / "runtime.db").exists())

    def test_set_and_show_persist_one_watch(self) -> None:
        empty = show_watch(self.repo)
        self.assertEqual(empty["status"], "noop")
        self.assertEqual(empty["reason"], "no_watch")
        out = set_watch(self.repo, project_id="app-1", repo_slug=REPO, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["project_id"], "app-1")
        self.assertEqual(out["repo"], REPO)
        self.assertFalse(out["published"])
        shown = show_watch(self.repo)
        self.assertEqual(shown["project_id"], "app-1")
        self.assertEqual(shown["repo"], REPO)
        replaced = set_watch(self.repo, project_id="app-1", repo_slug="mikolaj92/other", now=NOW)
        self.assertEqual(replaced["repo"], "mikolaj92/other")
        self.assertEqual(show_watch(self.repo)["repo"], "mikolaj92/other")
        bad = set_watch(self.repo, project_id="app-1", repo_slug="not a repo")
        self.assertEqual(bad["status"], "failed")
        missing = set_watch(self.repo, project_id="nope", repo_slug=REPO)
        self.assertEqual(missing["reason"], "project not found")
        self.assertFalse((self.home / "runtime.db").exists())

    def test_poisoned_watch_slug_is_silence_not_a_process(self) -> None:
        poison = "owner/name; rm -rf /"
        self.repo.set_hom_watch("app-1", poison, created_at=NOW)
        self.assertEqual(self.repo.get_hom_watch()["repo"], poison)
        self.assertIsNone(get_watch(self.repo))
        out, fake = self._tick()
        self.assertNotIn("scan", out)
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse(out.get("published", False))


class HomWatchCLIFAlaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        self.assertEqual(cli_main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)
        self.assertEqual(
            cli_main(
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
                    "--kind",
                    "app",
                ]
            ),
            0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cli_watch_set_and_show(self) -> None:
        parser = ArgumentParser()
        setup_parser(parser)
        parsed = parser.parse_args(["watch", "set", "--project-id", "app-1", "--repo", REPO])
        self.assertEqual(parsed.command, "watch")
        self.assertEqual(parsed.watch_command, "set")
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            code = cli_main(
                [
                    "--config",
                    str(self.config),
                    "watch",
                    "set",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["repo"], REPO)
        shown = io.StringIO()
        with patch("sys.stdout", shown):
            code = cli_main(["--config", str(self.config), "watch", "show"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(shown.getvalue())["repo"], REPO)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_cli_once_with_watch_does_not_scan(self) -> None:
        self.assertEqual(
            cli_main(
                [
                    "--config",
                    str(self.config),
                    "watch",
                    "set",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            ),
            0,
        )
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("subprocess.run", side_effect=AssertionError("once must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("once must not fetch")),
            patch("sys.stdout", buf),
        ):
            code = tick_main(
                ["--config", str(self.config), "--once"],
                inspect_host=lambda: ALWAYS_ON,
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertNotIn("scan", payload)
        self.assertEqual(fake.calls, [])
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(repo.list_briefs("app-1"), [])
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse(json.loads(self.config.read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

    def test_cli_once_pass_if_due_scans_when_watch_due(self) -> None:
        self.assertEqual(
            cli_main(
                [
                    "--config",
                    str(self.config),
                    "watch",
                    "set",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            ),
            0,
        )
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("influenzer.hom_watch.utc_now", return_value=NOW),
            patch("influenzer.hom_pass.utc_now", return_value=NOW),
            patch("influenzer.scan_due.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("once --pass-if-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("once --pass-if-due must not fetch")),
            patch("sys.stdout", buf),
        ):
            code = tick_main(
                ["--config", str(self.config), "--once", "--pass-if-due"],
                inspect_host=lambda: ALWAYS_ON,
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["scan"]["status"], "admitted")
        self.assertTrue(fake.calls)
        self.assertFalse(payload["published"])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_interval_cli_due_watch_one_angle_offline(self) -> None:
        self.assertEqual(
            cli_main(
                [
                    "--config",
                    str(self.config),
                    "watch",
                    "set",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            ),
            0,
        )
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("influenzer.hom_watch.utc_now", return_value=NOW),
            patch("influenzer.hom_pass.utc_now", return_value=NOW),
            patch("influenzer.scan_due.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("interval must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("interval must not fetch")),
            patch("sys.stdout", buf),
        ):
            code = tick_main(
                [
                    "--config",
                    str(self.config),
                    "--interval",
                    "0.01",
                    "--max-ticks",
                    "1",
                ],
                inspect_host=lambda: ALWAYS_ON,
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["scan"]["status"], "admitted")
        self.assertEqual(payload["tick"]["scored"], 1)
        self.assertNotIn("Costume:", payload["angle"]["body"])
        self.assertFalse(payload["published"])
        self.assertTrue(fake.calls)
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse(json.loads(self.config.read_text(encoding="utf-8"))["scheduler"]["live_enabled"])


class HomWatchBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_watch.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not invent a repo inventory", blob)
        self.assertIn("Does not copy scan_due or hom_pass", blob)
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not run pass every interval", blob)
        self.assertIn("Does not open runtime.db", blob)
        self.assertNotIn("run_gh", blob)
        self.assertNotIn("pack_survey", blob)
        self.assertNotIn("survey_public_repo", blob)
        self.assertNotIn("dress_brief", blob)
        self.assertNotIn("apply_verdict", blob)
        self.assertNotIn("window_elapsed", blob)
        imports = _import_lines(src)
        self.assertTrue(any("scan_due" in line and "scan_due_reason" in line for line in imports))
        self.assertTrue(any("hom_pass" in line and "run_pass" in line for line in imports))
        self.assertTrue(any("scheduler" in line and "tick" in line for line in imports))
        self.assertFalse(any("github_pack" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("hom_verdict" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_watch", init)
        tick_all = (Path(__file__).resolve().parents[1] / "influenzer" / "tick_all.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_watch", tick_all)
        self.assertNotIn("hom_pass", tick_all)
        scheduler = (Path(__file__).resolve().parents[1] / "influenzer" / "scheduler.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_watch", scheduler)
        self.assertNotIn("hom_pass", scheduler)

    def test_fala_has_no_watch_organ_interval_stays_tick(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertNotIn("hom_watch", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertNotIn("hom_watch", paths)
        self.assertEqual(
            paths["operator_tick"]["effectors"][0]["adapter"]["command"],
            ["python3", "-m", "influenzer.tick_all"],
        )
        blob = json.dumps(package)
        self.assertNotIn("influenzer.hom_watch", blob)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())


if __name__ == "__main__":
    unittest.main()
