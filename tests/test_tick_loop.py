from __future__ import annotations

import tempfile
import tomllib
import unittest
from pathlib import Path

from influenzer.config import Config, write_config
from influenzer.hom import Brief, Fact
from influenzer.storage import StateRepository
from influenzer.tick import DEFAULT_INTERVAL_SECONDS, loop_ticks, main as tick_main
from influenzer.tick_all import run_tick


SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"


def _project(repo: StateRepository, project_id: str = "app-1") -> None:
    from influenzer.domain import Project

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


class TickLoopTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cfg = Config(home=self.home, scheduler_live_enabled=False)
        write_config(self.home / "config.json", self.cfg)
        self.repo = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        _project(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def test_loop_ticks_runs_without_launchagent_and_honors_max_ticks(self) -> None:
        slept: list[float] = []
        n = {"i": 0}

        def tick_once() -> dict:
            n["i"] += 1
            return {"status": "ok", "mutated": False, "n": n["i"], "published": False}

        results = loop_ticks(
            tick_once,
            interval=15,
            max_ticks=3,
            sleep=slept.append,
        )
        self.assertEqual([item["n"] for item in results], [1, 2, 3])
        self.assertEqual(slept, [15, 15])
        self.assertFalse(any(item["mutated"] or item["published"] for item in results))

    def test_once_does_not_sleep(self) -> None:
        slept: list[float] = []
        results = loop_ticks(
            lambda: {"status": "ok", "mutated": False},
            interval=99,
            once=True,
            sleep=slept.append,
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(slept, [])

    def test_interval_zero_without_once_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            loop_ticks(lambda: {}, interval=0, sleep=lambda _n: None)

    def test_cli_once_scores_pending_brief_like_tick_all(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="loop-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        code = tick_main(["--config", str(self.home / "config.json"), "--once", "--live"])
        self.assertEqual(code, 0)
        stored = self.repo.get_brief("app-1", "loop-1")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        self.assertIsNotNone(self.repo.get_operator_draft("app-1", "loop-1"))
        self.assertFalse((self.home / "runtime.db").exists())

    def test_cli_max_ticks_loop_does_not_enable_live_or_open_runtime_db(self) -> None:
        code = tick_main(
            [
                "--config",
                str(self.home / "config.json"),
                "--interval",
                "0.01",
                "--max-ticks",
                "2",
                "--live",
            ]
        )
        self.assertEqual(code, 0)
        again = run_tick(config_path=str(self.home / "config.json"), cli_live=True)
        self.assertFalse(again["mutated"])
        self.assertFalse(again["scheduler_live_enabled"])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_repo_has_no_launchagent_plist_or_mac_mini_target(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list(root.rglob("*.plist")), [])
        tick_src = (root / "influenzer" / "tick.py").read_text(encoding="utf-8")
        self.assertNotIn("launchctl", tick_src)
        self.assertNotIn("com.apple.launchd", tick_src)
        self.assertNotIn("LaunchAgents/", tick_src)
        self.assertIn("Not a LaunchAgent", tick_src)
        self.assertIn("Not a Mac mini", tick_src)
        self.assertEqual(DEFAULT_INTERVAL_SECONDS, 300)
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        command = package["correlation_paths"][0]["effectors"][0]["adapter"]["command"]
        self.assertEqual(command, ["python3", "-m", "influenzer.tick_all"])
        self.assertNotEqual(command[-1], "influenzer.tick")


if __name__ == "__main__":
    unittest.main()
