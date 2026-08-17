from __future__ import annotations

import io
import json
import tomllib
import unittest
from argparse import ArgumentParser
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from unittest.mock import patch

from github_survey import classify_gh_argv

from influenzer.brief_admit import SOURCE
from influenzer.cli import main as cli_main
from influenzer.cli import setup_parser
from influenzer.config import Config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from influenzer.hom_feedback import SOURCE as FEEDBACK_SOURCE
from influenzer.hom_pass import main as pass_main
from influenzer.hom_pass import run_pass
from influenzer.playbook import HN_CAMP_REASON, StoryKind
from influenzer.storage import StateRepository, try_acquire_tick_lock
from tests.gh_scripts import (
    NOW,
    REPO,
    SHIP_PR,
    ScriptedGh,
    feedback_noise_script,
    feedback_question_script,
    merge_log_script,
    noise_script,
    ship_script,
)


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


class HomPassTests(unittest.TestCase):
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

    def _pass(self, script: dict, **kwargs: Any) -> tuple[dict[str, Any], ScriptedGh]:
        fake = ScriptedGh(script)
        with (
            patch("subprocess.run", side_effect=AssertionError("hom-pass must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("hom-pass must not fetch")),
            patch(
                "influenzer.hom_verdict.apply_verdict",
                side_effect=AssertionError("hom-pass must not invoke verdict"),
            ),
        ):
            out = run_pass(
                self.repo,
                self.cfg,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
                **kwargs,
            )
        return out, fake

    def test_not_due_and_no_briefs_is_silence_angle(self) -> None:
        self.repo.record_github_scan("app-1", REPO, scanned_at=NOW)
        out, fake = self._pass(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "not due")
        self.assertNotIn("brief_id", out["feedback"])
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "not due")
        self.assertNotIn("brief_id", out["scan"])
        self.assertEqual(out["tick"]["scored"], 0)
        self.assertNotIn("outcomes", out["tick"])
        self.assertNotIn("operator", out)
        self.assertEqual(out["angle"]["status"], "noop")
        self.assertTrue(out["angle"]["empty"])
        self.assertEqual(out["angle"]["reason"], "no_draft")
        self.assertIsNone(out["angle"]["body"])
        self.assertEqual(fake.calls, [])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertFalse(self.cfg.scheduler_live_enabled)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_due_ship_admits_one_brief_scores_and_one_angle_body(self) -> None:
        out, fake = self._pass(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "comment_noise")
        self.assertNotIn("brief_id", out["feedback"])
        self.assertEqual(out["scan"]["status"], "admitted")
        self.assertEqual(out["scan"]["brief_id"], "scan-v0-1-0")
        self.assertNotIn("reason", out["scan"])
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        stored = self.repo.get_brief("app-1", "scan-v0-1-0")
        assert stored is not None
        self.assertEqual(stored.source, SOURCE)
        self.assertEqual(out["tick"]["scored"], 1)
        self.assertEqual(list(out["tick"].keys()), ["scored"])
        self.assertNotIn("outcomes", out)
        self.assertNotIn("body", out["tick"])
        self.assertEqual(out["angle"]["status"], "ok")
        self.assertFalse(out["angle"]["empty"])
        self.assertTrue(out["angle"]["body"].startswith("Show HN:"))
        self.assertFalse(out["angle"]["body"].startswith("Costume:"))
        self.assertNotIn("Costume:", out["angle"]["body"])
        self.assertNotIn("One arena:", out["angle"]["body"])
        self.assertIn("github.com/mikolaj92/demo", out["angle"]["body"])
        self.assertEqual(out["angle"]["brief_id"], "scan-v0-1-0")
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertTrue(fake.calls)
        self.assertFalse(json.loads((self.home / "config.json").read_text(encoding="utf-8"))["scheduler"]["live_enabled"])
        self.assertFalse((self.home / "runtime.db").exists())

        again, fake2 = self._pass(ship_script())
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertEqual(again["feedback"]["status"], "silence")
        self.assertIn(again["feedback"]["reason"], {HN_CAMP_REASON, "pending_brief", "social_draft"})
        self.assertEqual(again["scan"]["status"], "silence")
        self.assertIn(again["scan"]["reason"], {"pending_brief", "social_draft"})
        kinds = [classify_gh_argv(list(argv)) for argv in fake2.calls]
        self.assertNotIn("prs", kinds)
        self.assertNotIn("releases", kinds)
        self.assertEqual(again["tick"]["scored"], 0)
        self.assertEqual(again["angle"]["status"], "ok")
        self.assertNotIn("Costume:", again["angle"]["body"])

    def test_other_project_same_repo_is_one_look(self) -> None:
        first, fake1 = self._pass(ship_script())
        self.assertEqual(first["scan"]["status"], "admitted")
        self.assertTrue(fake1.calls)
        _project(self.repo, "app-2")
        fake2 = ScriptedGh(ship_script())
        with (
            patch("subprocess.run", side_effect=AssertionError("hom-pass must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("hom-pass must not fetch")),
        ):
            out = run_pass(
                self.repo,
                self.cfg,
                project_id="app-2",
                repo_slug=REPO,
                gh=fake2,
                now=NOW,
            )
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "not due")
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "not due")
        self.assertEqual(fake2.calls, [])
        self.assertEqual(out["tick"]["scored"], 0)
        self.assertTrue(out["angle"].get("empty") or out["angle"]["status"] == "noop")
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-1-0"))
        self.assertEqual(self.repo.list_briefs("app-2"), [])
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertFalse(out["published"])

    def test_open_story_skips_scan_and_still_ticks_and_angles(self) -> None:
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
        out, fake = self._pass(ship_script())
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "pending_brief")
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "pending_brief")
        self.assertEqual(fake.calls, [])
        self.assertEqual(out["tick"]["scored"], 1)
        self.assertEqual(out["angle"]["status"], "ok")
        self.assertEqual(out["angle"]["brief_id"], "manual-1")
        self.assertNotIn("Costume:", out["angle"]["body"])
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertFalse(out["published"])

    def test_merge_log_look_is_not_show_hn(self) -> None:
        out, fake = self._pass(merge_log_script())
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        blob = json.dumps(out)
        self.assertNotIn("Show HN: Merged PR", blob)
        self.assertNotIn("Show HN: Merged PR #190", blob)
        angle = out["angle"]
        body = angle.get("body")
        if body:
            self.assertFalse(str(body).startswith("Show HN: Merged PR"))
            self.assertNotIn("Merged PR #190", str(body).split("\n", 1)[0])
        else:
            self.assertTrue(angle.get("empty") or angle.get("status") == "noop")
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "comment_noise")
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "not_tryable")
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertTrue(fake.calls)

    def test_noise_look_is_due_silence_then_not_due_without_gh(self) -> None:
        first, fake1 = self._pass(noise_script())
        self.assertEqual(first["feedback"]["status"], "silence")
        self.assertEqual(first["feedback"]["reason"], "comment_noise")
        self.assertEqual(first["scan"]["status"], "silence")
        self.assertEqual(first["scan"]["reason"], "commit_noise")
        self.assertTrue(fake1.calls)
        self.assertEqual(first["tick"]["scored"], 0)
        self.assertTrue(first["angle"]["empty"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

        second, fake2 = self._pass(ship_script())
        self.assertEqual(second["feedback"]["reason"], "not due")
        self.assertEqual(second["scan"]["reason"], "not due")
        self.assertEqual(fake2.calls, [])
        self.assertEqual(second["tick"]["scored"], 0)
        self.assertTrue(second["angle"]["empty"])
        self.assertFalse(second["published"])

    def test_due_question_admits_feedback_and_scan_stays_silent(self) -> None:
        out, fake = self._pass(feedback_question_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["feedback"]["status"], "admitted")
        self.assertEqual(out["feedback"]["brief_id"], "fb-101")
        self.assertNotIn("reason", out["feedback"])
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "pending_brief")
        kinds = [classify_gh_argv(list(argv)) for argv in fake.calls]
        self.assertIn("issue_comments", kinds)
        self.assertNotIn("prs", kinds)
        self.assertNotIn("releases", kinds)
        stored = self.repo.get_brief("app-1", "fb-101")
        assert stored is not None
        self.assertEqual(stored.source, FEEDBACK_SOURCE)
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))
        self.assertEqual(out["tick"]["scored"], 1)
        self.assertEqual(out["angle"]["status"], "ok")
        self.assertEqual(out["angle"]["brief_id"], "fb-101")
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertFalse(self.cfg.scheduler_live_enabled)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_question_plus_open_story_is_no_second_brief(self) -> None:
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
        out, fake = self._pass(feedback_question_script())
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "pending_brief")
        self.assertEqual(out["scan"]["status"], "silence")
        self.assertEqual(out["scan"]["reason"], "pending_brief")
        self.assertEqual(fake.calls, [])
        self.assertIsNone(self.repo.get_brief("app-1", "fb-101"))
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertEqual(out["tick"]["scored"], 1)
        self.assertEqual(out["angle"]["brief_id"], "manual-1")
        self.assertFalse(out["published"])

    def test_bot_only_is_feedback_silence_then_scan_may_admit(self) -> None:
        script = ship_script()
        script.update(feedback_noise_script())
        out, fake = self._pass(script)
        self.assertEqual(out["feedback"]["status"], "silence")
        self.assertEqual(out["feedback"]["reason"], "comment_noise")
        self.assertNotIn("brief_id", out["feedback"])
        self.assertEqual(out["scan"]["status"], "admitted")
        self.assertEqual(out["scan"]["brief_id"], "scan-v0-1-0")
        kinds = [classify_gh_argv(list(argv)) for argv in fake.calls]
        self.assertIn("issue_comments", kinds)
        self.assertIn("prs", kinds)
        self.assertIsNone(self.repo.get_brief("app-1", "fb-101"))
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertEqual(self.repo.get_brief("app-1", "scan-v0-1-0").source, SOURCE)
        self.assertFalse(out["published"])
        self.assertFalse(self.cfg.scheduler_live_enabled)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_live_enabled_does_not_put_adapters_on_look(self) -> None:
        from influenzer.content import create_revision, persist_revision
        from influenzer.domain import (
            AccountStatus,
            ContentStatus,
            PlatformAccount,
            PolicyActivationGrant,
            PolicyVersion,
            PublishPlan,
            PlanStatus,
        )

        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        account = PlatformAccount(
            project_id="app-1",
            account_id="x-look",
            platform="x",
            handle="@app",
            host=None,
            credential_ref="env:X_TOKEN",
            status=AccountStatus.CONNECTED,
        )
        self.repo.save_account(account)
        policy = PolicyVersion(
            project_id="app-1",
            policy_version_id="pol-look",
            account_ids=(account.account_id,),
            actions=("publish",),
            content_kinds=("post",),
            max_posts_per_day=5,
            require_disclosures=False,
        ).with_hash()
        self.repo.save_policy(policy)
        self.repo.save_grant(
            PolicyActivationGrant(
                project_id="app-1",
                grant_id="grant-look",
                policy_version_id=policy.policy_version_id,
                policy_hash=policy.policy_hash,
                platform_account_id=account.account_id,
                actions=("publish",),
                actor="tester",
                created_at="2026-01-01T00:00:00Z",
                expires_at=None,
            )
        )
        rev = create_revision(
            project_id="app-1",
            content_id="c-look",
            revision_id="r-look",
            body="hello live",
            status=ContentStatus.READY,
        )
        persist_revision(self.repo, rev)
        self.repo.save_plan(
            PublishPlan(
                project_id="app-1",
                plan_id="plan-look",
                content_revision_id=rev.revision_id,
                content_hash=rev.content_hash,
                platform_account_id=account.account_id,
                platform="x",
                body="hello live",
                status=PlanStatus.SCHEDULED,
                scheduled_at=None,
                created_at="2026-01-01T00:00:00Z",
                operation_key="op-look",
            )
        )

        with (
            patch(
                "influenzer.scheduler.get_adapter",
                side_effect=AssertionError("look/pass must not resolve adapters"),
            ),
            patch(
                "influenzer.scheduler.run_adapter",
                side_effect=AssertionError("look/pass must not call adapters"),
            ),
        ):
            out, _fake = self._pass(ship_script())
            live_out = run_pass(
                self.repo,
                live_cfg,
                project_id="app-1",
                repo_slug=REPO,
                gh=ScriptedGh(ship_script()),
                now=NOW,
            )
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertFalse(live_out["published"])
        self.assertFalse(live_out["mutated"])
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-look",)
            ).fetchone()["status"],
            PlanStatus.SCHEDULED.value,
        )
        self.assertIsNone(
            self.repo.conn.execute(
                "SELECT 1 FROM publication_attempts WHERE plan_id=?", ("plan-look",)
            ).fetchone()
        )


class HomPassCLIFAlaTests(unittest.TestCase):
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
                    "mikolaj92",
                    "--kind",
                    "app",
                ]
            ),
            0,
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_cli_pass_requires_project_and_repo(self) -> None:
        parser = ArgumentParser()
        setup_parser(parser)
        parsed = parser.parse_args(["pass", "--project-id", "app-1", "--repo", REPO])
        self.assertEqual(parsed.command, "pass")
        self.assertEqual(parsed.project_id, "app-1")
        self.assertEqual(parsed.repo, REPO)
        err = io.StringIO()
        with patch("sys.stderr", err):
            with self.assertRaises(SystemExit):
                parser.parse_args(["pass", "--project-id", "app-1"])
            with self.assertRaises(SystemExit):
                parser.parse_args(["pass", "--repo", REPO])
            with self.assertRaises(SystemExit):
                parser.parse_args(["pass"])
        verdict = parser.parse_args(["verdict", "pass", "--project-id", "app-1"])
        self.assertEqual(verdict.command, "verdict")
        self.assertEqual(verdict.verdict, "pass")

    def test_cli_and_module_main_due_ship_one_angle_offline(self) -> None:
        fake = ScriptedGh(ship_script())
        buf = io.StringIO()
        with (
            patch("github_survey.survey.run_gh", fake),
            patch("influenzer.hom_pass.utc_now", return_value=NOW),
            patch("influenzer.scan_due.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli pass must not call subprocess")),
            patch("urllib.request.urlopen", side_effect=AssertionError("cli pass must not fetch")),
            patch(
                "influenzer.hom_verdict.apply_verdict",
                side_effect=AssertionError("cli pass must not invoke verdict"),
            ),
            patch("sys.stdout", buf),
        ):
            code = cli_main(
                [
                    "--config",
                    str(self.config),
                    "pass",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["feedback"]["status"], "silence")
        self.assertEqual(payload["scan"]["status"], "admitted")
        self.assertEqual(payload["tick"]["scored"], 1)
        self.assertNotIn("Costume:", payload["angle"]["body"])
        self.assertFalse(payload["published"])
        self.assertFalse(payload["mutated"])
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertFalse(json.loads(self.config.read_text(encoding="utf-8"))["scheduler"]["live_enabled"])

        module_buf = io.StringIO()
        fake2 = ScriptedGh(ship_script())
        with (
            patch("github_survey.survey.run_gh", fake2),
            patch("subprocess.run", side_effect=AssertionError("pass module must not call subprocess")),
            redirect_stdout(module_buf),
        ):
            code = pass_main(
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
        again = json.loads(module_buf.getvalue())
        self.assertEqual(again["feedback"]["status"], "silence")
        self.assertIn(again["feedback"]["reason"], {HN_CAMP_REASON, "pending_brief", "social_draft"})
        self.assertEqual(again["scan"]["status"], "silence")
        self.assertIn(again["scan"]["reason"], {"pending_brief", "social_draft"})
        kinds = [classify_gh_argv(list(argv)) for argv in fake2.calls]
        self.assertNotIn("prs", kinds)
        self.assertNotIn("releases", kinds)
        self.assertEqual(again["tick"]["scored"], 0)
        self.assertEqual(again["angle"]["status"], "ok")
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            self.assertEqual(len(repo.list_briefs("app-1")), 1)

    def test_second_pass_instance_is_cisza_without_look(self) -> None:
        fake = ScriptedGh(ship_script())
        held = try_acquire_tick_lock(self.home / "state.db")
        self.assertIsNotNone(held)
        assert held is not None
        try:
            buf = io.StringIO()
            with (
                patch("github_survey.survey.run_gh", fake),
                patch("subprocess.run", side_effect=AssertionError("locked pass must not call subprocess")),
                patch("sys.stdout", buf),
            ):
                code = cli_main(
                    [
                        "--config",
                        str(self.config),
                        "pass",
                        "--project-id",
                        "app-1",
                        "--repo",
                        REPO,
                    ]
                )
            self.assertEqual(code, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload, {"status": "cisza", "mutated": False, "published": False})
            self.assertEqual(fake.calls, [])
            with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
                self.assertEqual(repo.list_briefs("app-1"), [])
        finally:
            held.close()

    def test_fala_result_does_not_open_runtime_db(self) -> None:
        from influenzer.fala_result import write_fala_result

        fake = ScriptedGh(noise_script())
        with (
            patch("subprocess.run", side_effect=AssertionError("hom-pass must not call subprocess")),
            StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo,
        ):
            payload = run_pass(
                repo,
                Config(home=self.home, scheduler_live_enabled=False),
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
            )
        fala_out = self.home / "fala-out"
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)}, reaction_kind="hom.pass")
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["reactions"][0]["kind"], "hom.pass")
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse(data["metadata"]["mutated"])
        self.assertNotIn("outcomes", data["values"].get("tick", {}))
        self.assertFalse((self.home / "runtime.db").exists())


class HomPassBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_pass.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not invoke hold or pass", blob)
        self.assertIn("Does not run every tick interval", blob)
        self.assertIn("Does not merge scan_due, tick, and outbox into one file", blob)
        self.assertIn("Does not grow github_feedback into a bag", blob)
        self.assertIn("Does not run feedback on score-only ticks", blob)
        self.assertIn("Does not open runtime.db", blob)
        self.assertIn("Does not run the project", blob)
        self.assertIn("Launching on watch is silence", blob)
        self.assertIn("Tryable is a README+URL heuristic", blob)
        self.assertNotIn("run_gh", blob)
        self.assertNotIn("pack_survey", blob)
        self.assertNotIn("survey_public_repo", blob)
        self.assertNotIn("dress_brief", blob)
        self.assertNotIn("apply_verdict", blob)
        self.assertNotIn("apply_brief", blob)
        imports = _import_lines(src)
        self.assertTrue(any("scan_due" in line and "scan_github_if_due" in line for line in imports))
        self.assertTrue(any("hom_feedback" in line and "collect_and_admit" in line for line in imports))
        self.assertTrue(any("scheduler" in line and "tick" in line for line in imports))
        self.assertTrue(any("hom_outbox" in line and "emit_angle" in line for line in imports))
        self.assertFalse(any("github_feedback" in line for line in imports))
        self.assertFalse(any("github_pack" in line for line in imports))
        self.assertFalse(any("github_survey" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("hom_verdict" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_pass", init)
        for name in ("scan_due.py", "tick_all.py", "hom_outbox.py", "hom_verdict.py", "hom_draft.py"):
            other = (Path(__file__).resolve().parents[1] / "influenzer" / name).read_text(encoding="utf-8")
            self.assertNotIn("hom_pass", other)
        self.assertFalse((Path(__file__).resolve().parents[1] / "influenzer" / "github_scan.py").exists())

    def test_fala_package_lists_hom_pass_compose(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("hom_pass", caps)
        self.assertIn("scan_due", caps)
        self.assertIn("tick_all", caps)
        self.assertIn("hom_outbox", caps)
        self.assertIn("hom_verdict", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("hom_pass", paths)
        commands = [item["adapter"]["command"] for item in paths["hom_pass"]["effectors"]]
        self.assertEqual(commands, [["python3", "-m", "influenzer.hom_pass"]])
        self.assertEqual(len(paths["hom_pass"]["effectors"]), 1)
        self.assertEqual(len(paths["operator_tick"]["effectors"]), 1)
        self.assertEqual(len(paths["github_scan_due"]["effectors"]), 1)
        self.assertEqual(len(paths["hom_outbox"]["effectors"]), 1)
        self.assertEqual(len(paths["hom_verdict"]["effectors"]), 1)
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())
        self.assertIn("Does not", paths["hom_pass"]["description"])
        self.assertIn("verdict", paths["hom_pass"]["description"].lower())
        self.assertIn("influenzer.hom_pass", blob)
        self.assertEqual(paths["operator_tick"]["effectors"][0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])
        self.assertEqual(package["correlation_paths"][0]["effectors"][0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])


if __name__ == "__main__":
    unittest.main()
