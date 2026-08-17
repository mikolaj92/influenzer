from __future__ import annotations

import io
import json
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from influenzer.brief_admit import open_story_reason
from influenzer.cli import main as cli_main
from influenzer.config import Config, write_config
from influenzer.hom import Brief, Fact, compose_draft, score_brief
from influenzer.hom_outbox import emit_angle
from influenzer.hom_verdict import apply_verdict, main as verdict_main
from influenzer.playbook import ArenaId, LIVING_STACK_REASON, StoryKind, Verdict
from influenzer.scan_due import scan_github_if_due
from influenzer.storage import StateRepository

from tests.gh_scripts import NOW, REPO, ScriptedGh, ship_script
from tests.test_hom_operator import SHIP_PR
from tests.test_hom_outbox import _project, _put_draft, _put_kill


def _import_lines(path: Path) -> list[str]:
    found: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            found.append(stripped)
    return found


class HomVerdictTests(unittest.TestCase):
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

    def test_no_draft_is_silence(self) -> None:
        with patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")):
            out = apply_verdict(self.repo, "hold")
        self.assertEqual(out["status"], "noop")
        self.assertTrue(out["ok"])
        self.assertTrue(out["empty"])
        self.assertEqual(out["reason"], "no_draft")
        self.assertIsNone(out["draft_id"])
        self.assertIsNone(out["verdict"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])

        passed = apply_verdict(self.repo, "pass")
        self.assertEqual(passed["status"], "noop")
        self.assertEqual(passed["reason"], "no_draft")
        self.assertFalse(passed["published"])

    def test_kill_is_silence(self) -> None:
        _put_kill(self.repo, brief_id="kill-1", created_at="2026-08-13T04:00:00Z")
        out = apply_verdict(self.repo, "pass", project_id="app-1")
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "no_draft")

    def test_pass_stamps_verdict_and_does_not_publish(self) -> None:
        body = f"Show HN: Local tick scores briefs\n\n{SHIP_PR}"
        draft = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="b-ship",
            created_at="2026-08-13T05:00:00Z",
            body=body,
        )
        with (
            patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("verdict must not fetch")),
        ):
            out = apply_verdict(self.repo, "pass", project_id="app-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["verdict"], "pass")
        self.assertEqual(out["draft_id"], draft.draft_id)
        self.assertEqual(out["brief_id"], "b-ship")
        self.assertEqual(out["body"], body)
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        row = self.repo.conn.execute(
            "SELECT gate_verdict FROM operator_drafts WHERE draft_id=?",
            (draft.draft_id,),
        ).fetchone()
        self.assertEqual(row["gate_verdict"], "pass")
        events = [json.loads(item["payload_json"]) | {"event_type": item["event_type"]} for item in self.repo.events("app-1")]
        verdict_events = [item for item in events if item["event_type"] == "draft.verdict"]
        self.assertEqual(len(verdict_events), 1)
        self.assertEqual(verdict_events[0]["verdict"], "pass")
        self.assertFalse(verdict_events[0]["published"])
        self.assertEqual(len(self.repo.list_operator_drafts("app-1")), 1)
        self.assertEqual(open_story_reason(self.repo, "app-1"), "social_draft")
        angle = emit_angle(self.repo, project_id="app-1")
        self.assertEqual(angle["draft_id"], draft.draft_id)
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])
        self.assertFalse((self.home / "runtime.db").exists())

        fake = ScriptedGh(ship_script())
        blocked = scan_github_if_due(
            self.repo,
            project_id="app-1",
            repo_slug=REPO,
            gh=fake,
            now=NOW,
        )
        self.assertEqual(blocked["reason"], "social_draft")
        self.assertEqual(fake.calls, [])

    def test_pass_on_github_stack_still_blocks_a_second_social_angle(self) -> None:
        draft = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="prior-github",
            created_at=NOW,
            body=f"## Quickstart\n\n{SHIP_PR}",
            arena=ArenaId.GITHUB,
        )
        with (
            patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("verdict must not fetch")),
        ):
            out = apply_verdict(self.repo, "pass", project_id="app-1")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["verdict"], "pass")
        self.assertFalse(out["published"])
        self.assertEqual(self.repo.living_stack_arena("app-1", NOW), ArenaId.GITHUB)
        self.assertEqual(open_story_reason(self.repo, "app-1", NOW), LIVING_STACK_REASON)
        fake = ScriptedGh(ship_script())
        blocked = scan_github_if_due(
            self.repo,
            project_id="app-1",
            repo_slug=REPO,
            gh=fake,
            now=NOW,
        )
        self.assertEqual(blocked["status"], "noop")
        self.assertEqual(blocked["reason"], LIVING_STACK_REASON)
        self.assertEqual(fake.calls, [])
        again = Brief.create(
            project_id="app-1",
            brief_id="second-github",
            facts=(
                Fact(text="a stranger can click and run the demo from the README", artifact_url=SHIP_PR),
                Fact(text="Dry-run still default"),
            ),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        score = score_brief(again, stack_arena=self.repo.living_stack_arena("app-1", NOW))
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, LIVING_STACK_REASON)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(again, score))
        self.assertEqual(self.repo.get_operator_draft("app-1", "prior-github").draft_id, draft.draft_id)
        self.assertIsNone(open_story_reason(self.repo, "app-1", "2026-08-19T06:00:00Z"))

    def test_hold_releases_so_scan_due_is_not_blocked(self) -> None:
        draft = _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="prior-ship",
            created_at="2026-08-13T05:00:00Z",
            body=f"Show HN: prior ship\n\n{SHIP_PR}",
        )
        self.assertEqual(open_story_reason(self.repo, "app-1"), "social_draft")
        before = list(
            self.repo.conn.execute("SELECT draft_id, body FROM operator_drafts WHERE draft_id=?", (draft.draft_id,))
        )
        self.assertEqual(len(before), 1)

        with (
            patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("verdict must not fetch")),
        ):
            out = apply_verdict(self.repo, "hold")
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["verdict"], "hold")
        self.assertEqual(out["draft_id"], draft.draft_id)
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])

        kept = self.repo.conn.execute(
            "SELECT draft_id, body, gate_verdict FROM operator_drafts WHERE draft_id=?",
            (draft.draft_id,),
        ).fetchone()
        self.assertEqual(kept["body"], before[0]["body"])
        self.assertEqual(kept["gate_verdict"], "hold")
        self.assertEqual(self.repo.list_operator_drafts("app-1"), [])
        self.assertIsNone(open_story_reason(self.repo, "app-1"))
        self.assertEqual(emit_angle(self.repo)["reason"], "no_draft")
        self.assertIsNotNone(self.repo.get_operator_draft("app-1", "prior-ship"))

        fake = ScriptedGh(ship_script())
        with patch("subprocess.run", side_effect=AssertionError("scan-due must not call subprocess")):
            due = scan_github_if_due(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
            )
        self.assertNotEqual(due.get("reason"), "social_draft")
        self.assertEqual(due["status"], "ok")
        self.assertEqual(due["brief_id"], "scan-v0-1-0")
        self.assertTrue(fake.calls)
        self.assertFalse(due["published"])
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

    def test_cli_and_module_main_are_offline_and_never_enable_live(self) -> None:
        _put_draft(
            self.repo,
            project_id="app-1",
            brief_id="b-ship",
            created_at="2026-08-13T05:00:00Z",
            body=f"Show HN: Local tick scores briefs\n\n{SHIP_PR}",
        )
        buf = io.StringIO()
        with (
            patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("verdict must not fetch")),
            redirect_stdout(buf),
        ):
            code = cli_main(["--config", str(self.home / "config.json"), "verdict", "pass"])
        self.assertEqual(code, 0)
        printed = json.loads(buf.getvalue())
        self.assertEqual(printed["verdict"], "pass")
        self.assertFalse(printed["published"])

        empty_home = self.home / "empty"
        empty_cfg = Config(home=empty_home, scheduler_live_enabled=False)
        write_config(empty_home / "config.json", empty_cfg)
        module_buf = io.StringIO()
        with (
            patch("subprocess.run", side_effect=AssertionError("verdict must not call subprocess")),
            redirect_stdout(module_buf),
        ):
            code = verdict_main(["--config", str(empty_home / "config.json"), "hold"])
        self.assertEqual(code, 0)
        silenced = json.loads(module_buf.getvalue())
        self.assertEqual(silenced["status"], "noop")
        self.assertTrue(silenced["empty"])
        self.assertEqual(silenced["reason"], "no_draft")
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse((empty_home / "runtime.db").exists())
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

    def test_fala_result_does_not_open_runtime_db(self) -> None:
        from influenzer.fala_result import write_fala_result

        fala_out = self.home / "fala-out"
        payload = apply_verdict(self.repo, "hold")
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)}, reaction_kind="hom.verdict")
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["reactions"][0]["kind"], "hom.verdict")
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse((self.home / "runtime.db").exists())


class HomVerdictBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_verdict.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not survey GitHub", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not score", blob)
        self.assertIn("Does not dress", blob)
        self.assertIn("Does not scan", blob)
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not send mail", blob)
        self.assertIn("Does not open runtime.db", blob)
        self.assertIn("Does not delete draft history", blob)
        imports = _import_lines(src)
        self.assertFalse(any("github_survey" in line or "github_pack" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("scan_due" in line or "brief_scan" in line for line in imports))
        self.assertFalse(any("scheduler" in line or "tick_all" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        self.assertTrue(any("hom_outbox" in line and "choose_draft" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_verdict", init)
        hom = (Path(__file__).resolve().parents[1] / "influenzer" / "hom.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_verdict", hom)
        outbox = (Path(__file__).resolve().parents[1] / "influenzer" / "hom_outbox.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_verdict", outbox)

    def test_fala_package_lists_verdict_organ(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("hom_verdict", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("hom_verdict", paths)
        commands = [item["adapter"]["command"] for item in paths["hom_verdict"]["effectors"]]
        self.assertEqual(commands, [["python3", "-m", "influenzer.hom_verdict"]])
        self.assertEqual(len(paths["operator_tick"]["effectors"]), 1)
        self.assertEqual(len(paths["hom_outbox"]["effectors"]), 1)
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())
        self.assertIn("Does not survey GitHub", paths["hom_verdict"]["description"])
        self.assertIn("Does not", paths["hom_verdict"]["description"])
        self.assertIn("influenzer.hom_verdict", blob)


if __name__ == "__main__":
    unittest.main()
