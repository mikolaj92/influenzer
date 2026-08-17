from __future__ import annotations

import io
import json
import tempfile
import tomllib
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch

from github_survey import GhCall

from influenzer.brief_admit import SOURCE, open_story_reason
from influenzer.cli import main as cli_main
from influenzer.config import Config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from influenzer.playbook import ArenaId, LIVING_STACK_REASON, StoryKind
from influenzer.scan_due import (
    DEFAULT_WINDOW_DAYS,
    last_scan_at,
    main as scan_due_main,
    scan_github_if_due,
    window_elapsed,
)
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from tests.gh_scripts import NOW, REPO, SHIP_PR, noise_script, ship_script, ScriptedGh


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


class ScanDueTests(unittest.TestCase):
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

    def _due(self, script: dict, **kwargs: Any) -> tuple[dict[str, Any], ScriptedGh]:
        fake = ScriptedGh(script)
        with (
            patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("scan-due must not fetch")),
        ):
            out = scan_github_if_due(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
                **kwargs,
            )
        return out, fake

    def test_due_ship_admits_at_most_one_brief(self) -> None:
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["brief_id"], "scan-v0-1-0")
        self.assertEqual(out["source"], SOURCE)
        self.assertTrue(out["pending"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertTrue(fake.calls)
        stored = self.repo.get_brief("app-1", "scan-v0-1-0")
        assert stored is not None
        self.assertEqual(stored.source, SOURCE)
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

        again, fake2 = self._due(ship_script())
        self.assertEqual(again["status"], "noop")
        self.assertEqual(again["reason"], "pending_brief")
        self.assertEqual(fake2.calls, [])
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse(self.cfg.scheduler_live_enabled)

    def test_not_due_after_look_is_silence_without_gh(self) -> None:
        first, fake1 = self._due(noise_script())
        self.assertEqual(first["status"], "noop")
        self.assertEqual(first["reason"], "commit_noise")
        self.assertTrue(fake1.calls)
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertIsNotNone(last_scan_at(self.repo, "app-1", REPO))

        second, fake2 = self._due(ship_script())
        self.assertEqual(second["status"], "noop")
        self.assertEqual(second["reason"], "not due")
        self.assertEqual(fake2.calls, [])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse(second["published"])

    def test_rate_limit_from_gh_is_empty_look_not_exception(self) -> None:
        out, fake = self._due({"repo": GhCall(1, "", "HTTP 429: API rate limit exceeded")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertTrue(fake.calls)
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertIsNotNone(last_scan_at(self.repo, "app-1", REPO))

    def test_bad_json_from_gh_is_empty_look_not_exception(self) -> None:
        out, fake = self._due({"repo": GhCall(0, "not-json")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertTrue(fake.calls)
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertIsNotNone(last_scan_at(self.repo, "app-1", REPO))

    def test_non_utf8_from_gh_is_empty_look_not_exception(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")

        with (
            patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("scan-due must not fetch")),
        ):
            out = scan_github_if_due(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=boom,
                now=NOW,
            )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertIsNotNone(last_scan_at(self.repo, "app-1", REPO))

    def test_github_scan_brief_fallback_is_not_due_without_gh(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="scan-v0-1-0",
                facts=(Fact(text="already told", artifact_url=SHIP_PR),),
                story_kind=StoryKind.MAJOR,
                claims_ship=True,
                tryable=True,
                source=SOURCE,
                status="processed",
                created_at="2026-08-17T05:00:00Z",
            )
        )
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not due")
        self.assertEqual(fake.calls, [])
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

    def test_pending_story_is_silence_without_gh(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="already working a story"),),
                story_kind=StoryKind.MAJOR,
                source="cli",
            )
        )
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_brief")
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))

    def test_social_draft_is_silence_without_gh(self) -> None:
        pending = Brief.create(
            project_id="app-1",
            brief_id="prior-ship",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        self.repo.save_brief(pending)
        tick(self.repo, self.cfg, due=(), now=NOW)
        self.assertIsNotNone(self.repo.get_operator_draft("app-1", "prior-ship"))
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "social_draft")
        self.assertEqual(fake.calls, [])

    def test_living_github_stack_is_silence_without_gh(self) -> None:
        pending = Brief.create(
            project_id="app-1",
            brief_id="prior-github",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        self.repo.save_brief(pending)
        tick(self.repo, self.cfg, due=(), now=NOW)
        self.assertIsNotNone(self.repo.get_operator_draft("app-1", "prior-github"))
        self.assertEqual(self.repo.living_stack_arena("app-1", NOW), ArenaId.GITHUB)
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], LIVING_STACK_REASON)
        self.assertEqual(fake.calls, [])
        self.assertFalse(out["published"])
        self.assertEqual(open_story_reason(self.repo, "app-1", NOW), LIVING_STACK_REASON)
        self.assertIsNone(open_story_reason(self.repo, "app-1", "2026-08-19T06:00:00Z"))

    def test_stale_watermark_is_due_again(self) -> None:
        self.repo.record_github_scan("app-1", REPO, scanned_at="2026-08-01T06:00:00Z")
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertTrue(fake.calls)
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

    def test_window_days_does_not_open_a_wednesday(self) -> None:
        self.repo.record_github_scan("app-1", REPO, scanned_at="2026-08-05T06:00:00Z")
        fake = ScriptedGh(ship_script())
        with (
            patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("scan-due must not fetch")),
        ):
            wed = scan_github_if_due(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now="2026-08-12T06:00:00Z",
                window_days=1,
            )
        self.assertEqual(wed["status"], "noop")
        self.assertEqual(wed["reason"], "not due")
        self.assertEqual(fake.calls, [])

    def test_other_repo_watermark_does_not_block(self) -> None:
        self.repo.record_github_scan("app-1", "other/repo", scanned_at=NOW)
        out, fake = self._due(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertTrue(fake.calls)

    def test_other_project_same_repo_watermark_is_one_look(self) -> None:
        _project(self.repo, "app-2")
        self.repo.record_github_scan("app-1", REPO, scanned_at=NOW)
        self.assertIsNotNone(last_scan_at(self.repo, "app-2", REPO))
        fake = ScriptedGh(ship_script())
        with (
            patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("scan-due must not fetch")),
        ):
            out = scan_github_if_due(
                self.repo,
                project_id="app-2",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
            )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not due")
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.repo.list_briefs("app-2"), [])

    def test_always_run_scan_ignores_the_window(self) -> None:
        from influenzer.brief_scan import scan_github

        first, _fake = self._due(noise_script())
        self.assertEqual(first["reason"], "commit_noise")
        fake = ScriptedGh(ship_script())
        with patch("subprocess.run", side_effect=AssertionError("scan must not call subprocess")):
            out = scan_github(self.repo, project_id="app-1", repo_slug=REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertTrue(fake.calls)
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

    def test_default_window_flag_still_exists(self) -> None:
        self.assertEqual(DEFAULT_WINDOW_DAYS, 7)

    def test_monday_calendar_not_rolling_168h(self) -> None:
        self.assertFalse(window_elapsed(None, "2026-08-12T06:00:00Z"))
        self.assertFalse(window_elapsed("2026-08-05T06:00:00Z", "2026-08-12T06:00:00Z"))
        self.assertTrue(window_elapsed(None, NOW))
        self.assertTrue(window_elapsed("2026-08-10T06:00:00Z", NOW))
        self.assertFalse(window_elapsed(NOW, NOW))
        self.assertFalse(window_elapsed(NOW, "2026-08-17T18:00:00Z"))
        self.assertFalse(window_elapsed(None, "2026-08-16T21:30:00Z"))
        self.assertTrue(window_elapsed(None, "2026-08-16T22:00:00Z"))

    def test_not_monday_first_look_is_silence_without_gh(self) -> None:
        fake = ScriptedGh(ship_script())
        with (
            patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("scan-due must not fetch")),
        ):
            out = scan_github_if_due(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now="2026-08-12T06:00:00Z",
            )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not due")
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.repo.list_briefs("app-1"), [])


class ScanDueCLIFAlaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
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
                    "mikolaj92",
                    "--kind",
                    "app",
                ]
            ),
            0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cli_scan_due_and_if_due_write_one_brief(self) -> None:
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("github_survey.survey.parse_now", return_value=fixed),
            patch("influenzer.scan_due.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan-due must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = cli_main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan-due",
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

        again = io.StringIO()
        fake2 = ScriptedGh(ship_script())
        with (
            patch("github_survey.survey.run_gh", fake2),
            patch("influenzer.scan_due.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli --if-due must not call subprocess")),
            patch("sys.stdout", again),
        ):
            code = cli_main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--if-due",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        silenced = json.loads(again.getvalue())
        self.assertEqual(silenced["status"], "noop")
        self.assertEqual(silenced["reason"], "pending_brief")
        self.assertEqual(fake2.calls, [])
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(len(repo.list_briefs("app-1")), 1)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_module_main_not_due_is_silence(self) -> None:
        fake = ScriptedGh(noise_script())
        first = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("subprocess.run", side_effect=AssertionError("scan-due module must not call subprocess")),
            redirect_stdout(first),
        ):
            code = scan_due_main(
                [
                    "--config",
                    str(self.config),
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                    "--now",
                    NOW,
                ]
            )
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(first.getvalue())["status"], "noop")
        self.assertEqual(json.loads(first.getvalue())["reason"], "commit_noise")

        second = io.StringIO()
        fake2 = ScriptedGh(ship_script())
        with (
            patch("github_survey.survey.run_gh", fake2),
            patch("subprocess.run", side_effect=AssertionError("scan-due module must not call subprocess")),
            redirect_stdout(second),
        ):
            code = scan_due_main(
                [
                    "--config",
                    str(self.config),
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                    "--now",
                    NOW,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(second.getvalue())
        self.assertEqual(payload["status"], "noop")
        self.assertEqual(payload["reason"], "not due")
        self.assertEqual(fake2.calls, [])
        self.assertFalse((self.home / "runtime.db").exists())
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(repo.list_briefs("app-1"), [])

    def test_fala_result_does_not_open_runtime_db(self) -> None:
        from influenzer.fala_result import write_fala_result

        fake = ScriptedGh(noise_script())
        with patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")):
            with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
                payload = scan_github_if_due(
                    repo,
                    project_id="app-1",
                    repo_slug=REPO,
                    gh=fake,
                    now=NOW,
                )
        fala_out = self.home / "fala-out"
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)}, reaction_kind="hom.brief")
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["reactions"][0]["kind"], "hom.brief")
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse((self.home / "runtime.db").exists())


class ScanDueBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "scan_due.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not score", blob)
        self.assertIn("Does not dress", blob)
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not know my-auth", blob)
        self.assertIn("Does not implement github_pack", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not run every tick interval", blob)
        self.assertIn("Does not open runtime.db", blob)
        self.assertIn("Does not run the project", blob)
        self.assertIn("Launching on watch is silence", blob)
        self.assertIn("Tryable is a README+URL heuristic", blob)
        self.assertNotIn("run_gh", blob)
        self.assertNotIn("pack_survey", blob)
        self.assertNotIn("survey_public_repo", blob)
        imports = _import_lines(src)
        self.assertFalse(any("github_pack" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("hom_outbox" in line for line in imports))
        self.assertFalse(any("scheduler" in line or "tick_all" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("scan_due", init)
        tick = (Path(__file__).resolve().parents[1] / "influenzer" / "tick_all.py").read_text(encoding="utf-8")
        self.assertNotIn("scan_due", tick)
        self.assertNotIn("github_survey", tick)
        survey = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (Path(__file__).resolve().parents[1] / "github_survey").rglob("*.py")
        )
        self.assertNotIn("scan_due", survey)
        pack = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (Path(__file__).resolve().parents[1] / "github_pack").rglob("*.py")
        )
        self.assertNotIn("scan_due", pack)

    def test_fala_package_lists_scan_due_organ_separate_from_tick(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("scan_due", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("github_scan_due", paths)
        commands = [item["adapter"]["command"] for item in paths["github_scan_due"]["effectors"]]
        self.assertEqual(commands, [["python3", "-m", "influenzer.scan_due"]])
        self.assertEqual(
            [item["adapter"]["command"] for item in paths["github_scan"]["effectors"]],
            [
                ["python3", "-m", "github_survey"],
                ["python3", "-m", "github_pack"],
                ["python3", "-m", "influenzer.brief_admit"],
            ],
        )
        self.assertEqual(paths["operator_tick"]["effectors"][0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])
        self.assertEqual(len(paths["operator_tick"]["effectors"]), 1)
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())
        self.assertIn("Does not score", paths["github_scan_due"]["description"])
        self.assertIn("Tick still does not survey GitHub", paths["github_scan_due"]["description"])


if __name__ == "__main__":
    unittest.main()
