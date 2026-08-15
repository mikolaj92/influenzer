from __future__ import annotations

import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from influenzer.cli import main as cli_main
from influenzer.config import Config, write_config
from influenzer.hom import Brief, Fact
from influenzer.host import (
    BATTERY_LAPTOP_REASON,
    HostPower,
    HostUnsuitable,
    inspect_power,
    require_always_on_host,
)
from influenzer.storage import StateRepository
from influenzer.tick import (
    DEFAULT_INTERVAL_SECONDS,
    guarded_tick,
    loop_ticks,
    main as tick_main,
)
from influenzer.tick_all import run_tick


SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"
ALWAYS_ON = HostPower(has_battery=False, source="test")
LAPTOP = HostPower(has_battery=True, source="test")


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

    def test_guarded_interval_continues_after_tick_error(self) -> None:
        n = {"i": 0}

        def tick_once() -> dict:
            n["i"] += 1
            if n["i"] == 2:
                raise RuntimeError("transient tick fault")
            return {"status": "ok", "n": n["i"], "mutated": False, "published": False}

        stderr = io.StringIO()
        with patch("influenzer.tick.sys.stderr", stderr):
            results = loop_ticks(
                guarded_tick(tick_once, supervise=True),
                interval=1,
                max_ticks=3,
                sleep=lambda _n: None,
            )
        self.assertEqual(len(results), 3)
        self.assertEqual(results[1]["status"], "failed")
        self.assertEqual(results[1]["reason"], "transient tick fault")
        self.assertFalse(results[1]["mutated"])
        self.assertFalse(results[1]["published"])
        self.assertEqual(results[2]["n"], 3)
        self.assertIn("transient tick fault", stderr.getvalue())

    def test_guarded_once_does_not_swallow_errors(self) -> None:
        def tick_once() -> dict:
            raise RuntimeError("one-shot must fail closed")

        with self.assertRaises(RuntimeError):
            loop_ticks(
                guarded_tick(tick_once, supervise=False),
                interval=1,
                once=True,
                sleep=lambda _n: None,
            )

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
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = tick_main(
                ["--config", str(self.home / "config.json"), "--once", "--live"],
                inspect_host=lambda: LAPTOP,
            )
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "scored")
        self.assertNotIn("body", payload)
        self.assertNotIn("operator", payload)
        self.assertNotIn("Show HN:", stdout.getvalue())
        stored = self.repo.get_brief("app-1", "loop-1")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        draft = self.repo.get_operator_draft("app-1", "loop-1")
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertFalse((self.home / "runtime.db").exists())

    def test_cli_tick_loop_subcommand_once_is_dry_and_does_not_open_runtime_db(self) -> None:
        code = cli_main(
            ["--config", str(self.home / "config.json"), "tick-loop", "--once", "--live"]
        )
        self.assertEqual(code, 0)
        again = run_tick(config_path=str(self.home / "config.json"), cli_live=True)
        self.assertFalse(again["mutated"])
        self.assertFalse(again["scheduler_live_enabled"])
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
            ],
            inspect_host=lambda: ALWAYS_ON,
        )
        self.assertEqual(code, 0)
        again = run_tick(config_path=str(self.home / "config.json"), cli_live=True)
        self.assertFalse(again["mutated"])
        self.assertFalse(again["scheduler_live_enabled"])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_interval_cli_fails_closed_on_battery_laptop(self) -> None:
        stdout = io.StringIO()
        with patch("sys.stdout", stdout):
            code = tick_main(
                ["--config", str(self.home / "config.json"), "--interval", "300"],
                inspect_host=lambda: LAPTOP,
            )
        self.assertEqual(code, 2)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["status"], "failed")
        self.assertEqual(payload["reason"], BATTERY_LAPTOP_REASON)
        self.assertFalse(payload["mutated"])
        self.assertFalse(payload["published"])

    def test_repo_has_no_launchagent_and_targets_always_on_host(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(list(root.rglob("*.plist")), [])
        tick_src = (root / "influenzer" / "tick.py").read_text(encoding="utf-8")
        self.assertNotIn("launchctl", tick_src)
        self.assertNotIn("com.apple.launchd", tick_src)
        self.assertNotIn("LaunchAgents/", tick_src)
        self.assertIn("Not a laptop LaunchAgent", tick_src)
        self.assertIn("always-on host", tick_src)
        self.assertIn("Mac mini", tick_src)
        self.assertIn("--pass-if-due", tick_src)
        self.assertIn("score-only", tick_src)
        self.assertIn("cisza", tick_src)
        self.assertIn("never angle copy", tick_src)
        self.assertEqual(DEFAULT_INTERVAL_SECONDS, 300)
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        command = package["correlation_paths"][0]["effectors"][0]["adapter"]["command"]
        self.assertEqual(command, ["python3", "-m", "influenzer.tick_all"])
        self.assertNotEqual(command[-1], "influenzer.tick")
        script = root / "contrib" / "always-on-tick.sh"
        script_text = script.read_text(encoding="utf-8")
        self.assertIn("uv run influenzer-tick", script_text)
        self.assertIn("--interval", script_text)
        self.assertNotIn("launchctl", script_text)
        self.assertNotIn("LaunchAgents", script_text)
        self.assertNotIn(".plist", script_text)


class HostFitnessTests(unittest.TestCase):
    def test_linux_bat_sysfs_is_a_laptop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bat = Path(tmp) / "BAT0"
            bat.mkdir()
            power = inspect_power(platform_name="Linux", sysfs_root=Path(tmp))
        self.assertTrue(power.has_battery)
        self.assertEqual(power.source, "sysfs")

    def test_linux_without_bat_is_always_on(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "AC").mkdir()
            power = inspect_power(platform_name="Linux", sysfs_root=Path(tmp))
        self.assertFalse(power.has_battery)

    def test_darwin_internal_battery_is_a_laptop_even_on_ac(self) -> None:
        text = "Now drawing from 'AC Power'\n -InternalBattery-0 (id=1)\t100%; charged; present: true\n"
        power = inspect_power(platform_name="Darwin", pmset_text=text)
        self.assertTrue(power.has_battery)
        self.assertEqual(power.source, "pmset")

    def test_darwin_mini_has_no_internal_battery(self) -> None:
        power = inspect_power(
            platform_name="Darwin",
            pmset_text="Now drawing from 'AC Power'\n",
        )
        self.assertFalse(power.has_battery)

    def test_unknown_platform_is_allowed(self) -> None:
        power = inspect_power(platform_name="FreeBSD")
        self.assertFalse(power.has_battery)
        self.assertEqual(power.source, "unknown")

    def test_interval_requires_always_on_host(self) -> None:
        with self.assertRaises(HostUnsuitable) as ctx:
            require_always_on_host(once=False, inspect=lambda: LAPTOP)
        self.assertEqual(str(ctx.exception), BATTERY_LAPTOP_REASON)

    def test_once_is_allowed_on_a_laptop(self) -> None:
        power = require_always_on_host(once=True, inspect=lambda: LAPTOP)
        self.assertTrue(power.has_battery)


if __name__ == "__main__":
    unittest.main()
