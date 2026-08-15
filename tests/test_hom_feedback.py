from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from github_survey import GhCall
from github_survey.survey import look_argv_leaves_declared_repo

from influenzer.config import Config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from github_feedback.feedback import MAX_STORED_FACT_CHARS, WHOLE_THREAD
from influenzer.hom_feedback import SOURCE, admit_feedback, collect_and_admit, main as feedback_main
from influenzer.playbook import ArenaId, StoryKind
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from tests.gh_scripts import (
    ISSUE_COMMENT,
    NOW,
    REPO,
    ScriptedGh,
    SHIP_PR,
    feedback_noise_script,
    feedback_question_script,
    repo_json,
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


class HomFeedbackComposeTests(unittest.TestCase):
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

    def _run(self, script: dict, **kwargs: Any) -> dict[str, Any]:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            return collect_and_admit(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
                **kwargs,
            )

    def test_fork_look_is_silence_even_when_owner_is_ours(self) -> None:
        out = self._run(feedback_question_script(repo=GhCall(0, repo_json(fork=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "fork_not_a_site")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_noise_is_silence_and_writes_no_brief(self) -> None:
        out = self._run(feedback_noise_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "comment_noise")
        self.assertEqual(out["source"], SOURCE)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_real_question_admits_one_brief_with_multiple_facts(self) -> None:
        out = self._run(feedback_question_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["brief_id"], "fb-101")
        self.assertEqual(out["source"], SOURCE)
        self.assertEqual(out["story_kind"], StoryKind.HARD_ISSUE.value)
        self.assertFalse(out["claims_ship"])
        self.assertFalse(out["tryable"])
        self.assertTrue(out["pending"])
        self.assertFalse(out["published"])
        self.assertGreaterEqual(out["fact_count"], 2)
        stored = self.repo.get_brief("app-1", "fb-101")
        assert stored is not None
        self.assertEqual(stored.source, SOURCE)
        self.assertEqual(stored.story_kind, StoryKind.HARD_ISSUE)
        self.assertGreaterEqual(len(stored.facts), 2)
        urls = {fact.artifact_url for fact in stored.facts if fact.artifact_url}
        self.assertIn(ISSUE_COMMENT, urls)
        self.assertEqual(len(self.repo.list_pending_briefs("app-1")), 1)
        events = [row["event_type"] for row in self.repo.events("app-1")]
        self.assertIn("brief.feedback", events)
        self.assertFalse((self.home / "runtime.db").exists())

    def test_pending_brief_is_silence(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="already working a story"),),
                story_kind=StoryKind.MAJOR,
                source="cli",
            )
        )
        out = self._run(feedback_question_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_brief")
        self.assertIsNone(self.repo.get_brief("app-1", "fb-101"))

    def test_open_social_draft_is_silence(self) -> None:
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
        out = self._run(feedback_question_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "social_draft")

    def test_watch_supplies_repo_when_omitted(self) -> None:
        self.repo.set_hom_watch("app-1", REPO, created_at=NOW)
        fake = ScriptedGh(feedback_question_script())
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            out = collect_and_admit(self.repo, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["repo"], REPO)
        self.assertEqual(out["project_id"], "app-1")

    def test_live_stays_off(self) -> None:
        out = self._run(feedback_question_script())
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        loaded = json.loads((self.home / "config.json").read_text(encoding="utf-8"))
        self.assertFalse(loaded.get("scheduler", {}).get("live_enabled", False))

    def test_does_not_call_survey_ship_path(self) -> None:
        fake = ScriptedGh(feedback_question_script())
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            out = collect_and_admit(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
            )
        self.assertEqual(out["status"], "ok")
        classified = []
        from github_survey import classify_gh_argv

        for argv in fake.calls:
            classified.append(classify_gh_argv(argv))
        self.assertIn("issue_comments", classified)
        self.assertNotIn("prs", classified)
        self.assertNotIn("releases", classified)

    def test_inbound_foreign_repo_link_stays_text_not_a_survey(self) -> None:
        self.repo.set_hom_watch("app-1", REPO, created_at=NOW)
        inbound = (
            "How do I install this when uv is missing? "
            "See https://github.com/other/tool for a similar crash."
        )
        script = feedback_question_script()
        script["issue_comments"] = GhCall(
            0,
            json.dumps(
                [
                    {
                        "id": 101,
                        "html_url": ISSUE_COMMENT,
                        "body": inbound,
                        "user": {"login": "alice", "type": "User"},
                        "created_at": "2026-08-12T12:00:00Z",
                    }
                ]
            ),
        )
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            out = collect_and_admit(self.repo, project_id="app-1", repo_slug=REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["repo"], REPO)
        stored = self.repo.get_brief("app-1", out["brief_id"])
        assert stored is not None
        self.assertIn("https://github.com/other/tool", stored.facts[0].text)
        self.assertEqual(self.repo.get_hom_watch()["repo"], REPO)
        self.assertFalse(any(look_argv_leaves_declared_repo(list(argv), REPO) for argv in fake.calls))

    def test_same_issue_stores_one_excerpt_not_the_thread(self) -> None:
        second = ISSUE_COMMENT.replace("issuecomment-101", "issuecomment-199")
        long_body = (
            "How do I install this when uv is missing? "
            + ("The traceback and env dump go on. " * 40)
        )
        script = feedback_question_script()
        script["issue_comments"] = GhCall(
            0,
            json.dumps(
                [
                    {
                        "id": 101,
                        "html_url": ISSUE_COMMENT,
                        "body": long_body,
                        "user": {"login": "alice", "type": "User"},
                        "created_at": "2026-08-12T12:00:00Z",
                    },
                    {
                        "id": 199,
                        "html_url": second,
                        "body": "Does this also break when the same issue has a later reply?",
                        "user": {"login": "bob", "type": "User"},
                        "created_at": "2026-08-12T12:30:00Z",
                    },
                ]
            ),
        )
        script["pull_comments"] = GhCall(0, "[]")
        out = self._run(script)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["fact_count"], 1)
        stored = self.repo.get_brief("app-1", out["brief_id"])
        assert stored is not None
        self.assertEqual(len(stored.facts), 1)
        self.assertEqual(stored.facts[0].artifact_url, ISSUE_COMMENT)
        self.assertLessEqual(len(stored.facts[0].text), MAX_STORED_FACT_CHARS)
        self.assertNotIn(long_body, stored.facts[0].text)
        dumped = json.dumps([dict(row) for row in self.repo.events("app-1")], default=str)
        self.assertNotIn(long_body, dumped)
        self.assertNotIn(second, dumped)

    def test_whole_thread_pack_is_silence_and_writes_no_brief(self) -> None:
        packed = {
            "status": "ok",
            "ok": True,
            "repo": REPO,
            "brief_id": "fb-dump",
            "source": SOURCE,
            "story_kind": "hard_issue",
            "claims_ship": False,
            "tryable": False,
            "facts": [
                {
                    "kind": "issue_comment",
                    "text": "@alice: How do I install this when uv is missing?",
                    "artifact_url": ISSUE_COMMENT,
                },
                {
                    "kind": "issue_comment",
                    "text": "@bob: later reply on the same issue",
                    "artifact_url": ISSUE_COMMENT.replace(
                        "issuecomment-101", "issuecomment-199"
                    ),
                },
            ],
        }
        out = admit_feedback(self.repo, packed, project_id="app-1", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], WHOLE_THREAD)
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_long_excerpt_is_silence_and_writes_no_brief(self) -> None:
        packed = {
            "status": "ok",
            "ok": True,
            "repo": REPO,
            "brief_id": "fb-long",
            "source": SOURCE,
            "story_kind": "hard_issue",
            "claims_ship": False,
            "tryable": False,
            "facts": [
                {
                    "kind": "issue_comment",
                    "text": "@alice: " + ("x" * 500),
                    "artifact_url": ISSUE_COMMENT,
                }
            ],
        }
        out = admit_feedback(self.repo, packed, project_id="app-1", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], WHOLE_THREAD)
        self.assertEqual(self.repo.list_briefs("app-1"), [])


class HomFeedbackCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        from influenzer.cli import main as cli_main

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

    def test_cli_feedback_writes_one_pending_brief(self) -> None:
        from influenzer.cli import main as cli_main

        fake = ScriptedGh(feedback_question_script())
        buf = io.StringIO()
        with (
            patch("github_feedback.feedback.run_gh", fake),
            patch("subprocess.run", side_effect=AssertionError("cli feedback must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = cli_main(
                [
                    "--config",
                    str(self.config),
                    "feedback",
                    "--project-id",
                    "app-1",
                    "--repo",
                    REPO,
                    "--now",
                    NOW,
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["brief_id"], "fb-101")
        self.assertEqual(payload["source"], SOURCE)
        self.assertFalse(payload["published"])
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            stored = repo.get_brief("app-1", "fb-101")
            assert stored is not None
            self.assertEqual(len(stored.facts), 3)

    def test_organ_admits_stdin_pack_without_network(self) -> None:
        packed = {
            "status": "ok",
            "ok": True,
            "repo": REPO,
            "brief_id": "fb-101",
            "source": SOURCE,
            "story_kind": "hard_issue",
            "claims_ship": False,
            "tryable": False,
            "facts": [
                {
                    "kind": "issue_comment",
                    "text": "@alice: How do I install this when uv is missing?",
                    "artifact_url": ISSUE_COMMENT,
                },
                {
                    "kind": "issue_comment",
                    "text": "@bob: The Windows install fails with a traceback",
                    "artifact_url": "https://github.com/mikolaj92/demo/issues/8#issuecomment-102",
                },
            ],
        }
        buf = io.StringIO()
        with (
            patch("sys.stdin", io.StringIO(json.dumps(packed))),
            patch("sys.stdout", buf),
            patch("subprocess.run", side_effect=AssertionError("admit must not call subprocess")),
        ):
            code = feedback_main(
                ["--project-id", "app-1", "--config", str(self.config)]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["fact_count"], 2)
        self.assertFalse((self.home / "runtime.db").exists())


class HomFeedbackBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_feedback.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not dress", blob)
        self.assertIn("Does not score", blob)
        self.assertIn("Does not choose a social angle", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not know my-auth", blob)
        self.assertIn("Does not auto-post replies", blob)
        self.assertIn("Does not run every tick interval", blob)
        self.assertIn("Does not open runtime.db", blob)
        self.assertIn("Does not run the project", blob)
        self.assertIn("Launching on watch is silence", blob)
        self.assertIn("Tryable is a README+URL heuristic", blob)
        self.assertNotIn("pack_survey", blob)
        self.assertNotIn("survey_public_repo", blob)
        self.assertNotIn("dress_brief", blob)
        imports = _import_lines(src)
        self.assertTrue(any("github_feedback" in line for line in imports))
        self.assertFalse(any("github_pack" in line for line in imports))
        self.assertFalse(any("hom_draft" in line for line in imports))
        self.assertFalse(any("hom_pass" in line for line in imports))
        self.assertFalse(any("webbrowser" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_feedback", init)
        tick = (Path(__file__).resolve().parents[1] / "influenzer" / "tick_all.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_feedback", tick)
        self.assertNotIn("github_feedback", tick)
        survey = (Path(__file__).resolve().parents[1] / "github_survey" / "survey.py").read_text(encoding="utf-8")
        self.assertNotIn("github_feedback", survey)


if __name__ == "__main__":
    unittest.main()
