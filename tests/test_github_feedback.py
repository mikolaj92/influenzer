from __future__ import annotations

import json
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from github_feedback import collect_feedback, is_feedback_signal, is_noise_comment
from github_feedback.feedback import (
    MAX_FACT_CHARS,
    MAX_STORED_FACT_CHARS,
    WHOLE_THREAD,
    is_feedback_excerpt_url,
    whole_thread_reason,
)
from github_survey import GhCall, classify_gh_argv
from github_survey.survey import MAX_PAGES, look_argv_is_unbounded_pages, look_short_gh

from tests.gh_scripts import (
    ISSUE_COMMENT,
    ISSUE_COMMENT_BUG,
    NOW,
    PR_COMMENT,
    REPO,
    ScriptedGh,
    feedback_noise_script,
    feedback_question_script,
    gh_comment,
    repo_json,
)


def _import_lines(root: Path) -> list[str]:
    found: list[str] = []
    for path in root.rglob("*.py"):
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped.startswith(("import ", "from ")):
                found.append(stripped)
    return found


class ClassifyFeedbackArgvTests(unittest.TestCase):
    def test_comment_endpoints(self) -> None:
        self.assertEqual(
            classify_gh_argv(["api", f"repos/{REPO}/issues/comments?per_page=100"]),
            "issue_comments",
        )
        self.assertEqual(
            classify_gh_argv(["api", f"repos/{REPO}/pulls/comments?since=2026-08-06T06:00:00Z"]),
            "pull_comments",
        )


class NoiseGateTests(unittest.TestCase):
    def test_bots_and_lgtm_are_noise(self) -> None:
        self.assertTrue(
            is_noise_comment(gh_comment(html_url=ISSUE_COMMENT, body="LGTM", user_type="Bot"))
        )
        self.assertTrue(
            is_noise_comment(
                gh_comment(html_url=ISSUE_COMMENT, body="thanks!", login="bob")
            )
        )
        self.assertTrue(is_noise_comment(gh_comment(html_url=ISSUE_COMMENT, body="Looks good to me")))
        self.assertFalse(is_feedback_signal("LGTM"))
        self.assertFalse(is_feedback_signal("thanks!"))

    def test_real_question_is_signal(self) -> None:
        self.assertTrue(is_feedback_signal("How do I install this when uv is missing?"))
        self.assertTrue(is_feedback_signal("The Windows install fails with a traceback"))
        self.assertFalse(
            is_noise_comment(
                gh_comment(html_url=ISSUE_COMMENT, body="How do I install this when uv is missing?")
            )
        )


class CollectFeedbackTests(unittest.TestCase):
    def _collect(self, script: dict[str, GhCall]) -> dict:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            return collect_feedback(REPO, gh=fake, now=NOW)

    def test_bot_and_lgtm_are_silence(self) -> None:
        out = self._collect(feedback_noise_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "comment_noise")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertNotIn("project_id", out)

    def test_real_question_packs_multiple_facts(self) -> None:
        out = self._collect(feedback_question_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["source"], "github-feedback")
        self.assertEqual(out["story_kind"], "hard_issue")
        self.assertFalse(out["claims_ship"])
        self.assertFalse(out["tryable"])
        self.assertGreaterEqual(len(out["facts"]), 2)
        urls = {item["artifact_url"] for item in out["facts"]}
        self.assertIn(ISSUE_COMMENT, urls)
        self.assertIn(ISSUE_COMMENT_BUG, urls)
        self.assertIn(PR_COMMENT, urls)
        self.assertEqual(out["brief_id"], "fb-101")
        for item in out["facts"]:
            self.assertLessEqual(len(item["text"]), MAX_STORED_FACT_CHARS)
            self.assertTrue(is_feedback_excerpt_url(item["artifact_url"]))
            self.assertEqual(set(item), {"kind", "text", "artifact_url"})
        self.assertIsNone(whole_thread_reason(out))

    def test_same_issue_keeps_one_excerpt_not_the_thread(self) -> None:
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
                    gh_comment(html_url=ISSUE_COMMENT, body=long_body, comment_id=101),
                    gh_comment(
                        html_url=second,
                        body="The Windows install fails with a traceback on the same issue",
                        login="bob",
                        comment_id=199,
                        created_at="2026-08-12T12:30:00Z",
                    ),
                ]
            ),
        )
        script["pull_comments"] = GhCall(0, "[]")
        out = self._collect(script)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["facts"]), 1)
        fact = out["facts"][0]
        self.assertEqual(fact["artifact_url"], ISSUE_COMMENT)
        self.assertLessEqual(len(fact["text"]), MAX_STORED_FACT_CHARS)
        self.assertIn("...", fact["text"])
        self.assertNotIn(second, json.dumps(out))
        self.assertNotIn(long_body, json.dumps(out))
        self.assertLess(len(fact["text"]), len(long_body))
        self.assertIsNone(whole_thread_reason(out))

    def test_raw_thread_payload_is_whole_thread_not_storage(self) -> None:
        dump = {
            "status": "ok",
            "facts": [
                {
                    "kind": "issue_comment",
                    "text": "@alice: How do I install this when uv is missing?",
                    "artifact_url": ISSUE_COMMENT,
                    "body": "full comment body plus later replies",
                    "user": {"login": "alice"},
                }
            ],
            "comments": [{"body": "later reply on the same issue"}],
        }
        self.assertEqual(whole_thread_reason(dump), WHOLE_THREAD)
        self.assertGreater(MAX_FACT_CHARS, 0)

    def test_two_excerpts_from_one_issue_are_whole_thread(self) -> None:
        payload = {
            "status": "ok",
            "facts": [
                {
                    "kind": "issue_comment",
                    "text": "@alice: How do I install this when uv is missing?",
                    "artifact_url": ISSUE_COMMENT,
                },
                {
                    "kind": "issue_comment",
                    "text": "@bob: The Windows install fails with a traceback",
                    "artifact_url": ISSUE_COMMENT.replace(
                        "issuecomment-101", "issuecomment-199"
                    ),
                },
            ],
        }
        self.assertEqual(whole_thread_reason(payload), WHOLE_THREAD)

    def test_missing_gh_is_silence(self) -> None:
        out = self._collect({"repo": GhCall(127, "", "gh not found", missing=True)})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "gh_missing")

    def test_private_repo_is_silence(self) -> None:
        out = self._collect(
            {
                "repo": GhCall(0, repo_json(private=True)),
                "issue_comments": GhCall(0, "[]"),
                "pull_comments": GhCall(0, "[]"),
            }
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")

    def test_malformed_json_is_silence(self) -> None:
        out = self._collect({"repo": GhCall(0, "not-json")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_feedback")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])

    def test_decode_error_from_runner_is_silence_not_crash(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")

        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            out = collect_feedback(REPO, gh=boom, now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_feedback")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])

    def test_feedback_stops_after_max_pages(self) -> None:
        fake = ScriptedGh(feedback_question_script())
        with patch("subprocess.run", side_effect=AssertionError("feedback must not call subprocess")):
            out = collect_feedback(REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        kinds = [classify_gh_argv(list(argv)) for argv in fake.calls]
        self.assertLessEqual(kinds.count("issue_comments"), MAX_PAGES)
        self.assertLessEqual(kinds.count("pull_comments"), MAX_PAGES)
        self.assertFalse(any(look_argv_is_unbounded_pages(list(argv)) for argv in fake.calls))

    def test_whole_history_comments_are_silence_not_a_spawn(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise AssertionError("feedback must not walk every GitHub page")

        runner = look_short_gh(boom)
        paginate = runner(["api", "--paginate", f"repos/{REPO}/issues/comments"])
        huge = runner(["api", f"repos/{REPO}/issues/comments?per_page=100", "--paginate"])
        self.assertEqual(paginate.returncode, 0)
        self.assertEqual(paginate.stdout, "")
        self.assertEqual(huge.returncode, 0)
        self.assertEqual(huge.stdout, "")


class FeedbackBlockBoundaryTests(unittest.TestCase):
    def test_package_does_not_load_influenzer(self) -> None:
        root = Path(__file__).resolve().parents[1]
        blob = (root / "github_feedback" / "__init__.py").read_text(encoding="utf-8")
        self.assertIn("Does not know briefs", blob)
        self.assertIn("Does not know Heimdall", blob)
        self.assertIn("Does not know my-auth", blob)
        self.assertIn("Does not post replies", blob)
        imports = _import_lines(root / "github_feedback")
        self.assertFalse(any("influenzer" in line for line in imports))
        self.assertTrue(any("github_survey" in line for line in imports))
        survey = (root / "github_survey" / "survey.py").read_text(encoding="utf-8")
        self.assertNotIn("issues/comments", survey)
        self.assertNotIn("github_feedback", survey)
        pack = (root / "github_pack" / "pack.py").read_text(encoding="utf-8")
        self.assertNotIn("github_feedback", pack)

    def test_fala_package_lists_feedback_organs(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("github_feedback", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("github_feedback", paths)
        commands = [item["adapter"]["command"] for item in paths["github_feedback"]["effectors"]]
        self.assertEqual(
            commands,
            [
                ["python3", "-m", "github_feedback"],
                ["python3", "-m", "influenzer.hom_feedback"],
            ],
        )
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())
        self.assertIn("Does not", paths["github_feedback"]["description"])


if __name__ == "__main__":
    unittest.main()
