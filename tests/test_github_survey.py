from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from github_survey import GhCall, classify_gh_argv, run_gh, survey_public_repo
from github_survey.gh import decode_gh_bytes, loads_json, required_json

from tests.gh_scripts import NOW, REPO, noise_script, repo_json, ship_script, ScriptedGh


class ClassifyArgvTests(unittest.TestCase):
    def test_argv_classes(self) -> None:
        self.assertEqual(classify_gh_argv(["repo", "view", REPO, "--json", "url"]), "repo")
        self.assertEqual(classify_gh_argv(["pr", "list", "--repo", REPO, "--state", "merged"]), "prs")
        self.assertEqual(classify_gh_argv(["release", "list", "--repo", REPO]), "releases")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/tags?per_page=20"]), "tags")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/readme"]), "readme")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/issues/comments"]), "issue_comments")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/pulls/comments"]), "pull_comments")
        self.assertEqual(classify_gh_argv(["auth", "status"]), "other")


class SurveySilenceTests(unittest.TestCase):
    def _survey(self, script: dict[str, GhCall]) -> dict:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            return survey_public_repo(REPO, gh=fake, now=NOW)

    def test_missing_gh_is_silence(self) -> None:
        out = self._survey({"repo": GhCall(127, "", "gh not found", missing=True)})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "gh_missing")
        self.assertNotIn("brief_id", out)
        self.assertNotIn("project_id", out)

    def test_auth_failure_is_silence(self) -> None:
        out = self._survey({"repo": GhCall(1, "", "gh: To get started with GitHub CLI, run: gh auth login")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "gh_auth")

    def test_empty_survey_is_silence(self) -> None:
        out = self._survey(
            {
                "repo": GhCall(0, repo_json()),
                "prs": GhCall(0, "[]"),
                "releases": GhCall(0, "[]"),
                "tags": GhCall(0, "[]"),
                "readme": GhCall(0, "{}"),
            }
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")

    def test_private_repo_is_silence(self) -> None:
        out = self._survey(
            {
                "repo": GhCall(0, repo_json(private=True)),
                "prs": GhCall(0, "[]"),
                "releases": GhCall(0, "[]"),
                "tags": GhCall(0, "[]"),
                "readme": GhCall(0, "{}"),
            }
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")

    def test_malformed_json_is_silence_not_crash(self) -> None:
        out = self._survey({"repo": GhCall(0, "not-json")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertNotIn("brief_id", out)

    def test_decode_error_from_runner_is_silence_not_crash(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad")

        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            out = survey_public_repo(REPO, gh=boom, now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])

    def test_ship_survey_is_ok_json(self) -> None:
        out = self._survey(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertIn("survey", out)
        self.assertEqual(out["repo"], REPO)

    def test_noise_prs_are_still_a_survey(self) -> None:
        out = self._survey(noise_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(len(out["survey"]["prs"]), 3)
        self.assertEqual(out["survey"]["releases"], [])


class RunGhTests(unittest.TestCase):
    def test_run_gh_missing_binary_is_not_a_crash(self) -> None:
        with patch("subprocess.run", side_effect=FileNotFoundError("gh")):
            call = run_gh(["repo", "view", REPO])
        self.assertTrue(call.missing)
        self.assertEqual(call.returncode, 127)

    def test_run_gh_timeout_is_not_a_crash(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="gh", timeout=1)):
            call = run_gh(["repo", "view", REPO])
        self.assertFalse(call.missing)
        self.assertEqual(call.returncode, 124)

    def test_run_gh_decode_error_is_empty_not_a_crash(self) -> None:
        with patch(
            "subprocess.run",
            side_effect=UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"),
        ):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        data, reason = required_json(call)
        self.assertIsNone(data)
        self.assertEqual(reason, "empty_survey")

    def test_run_gh_non_utf8_stdout_is_empty_not_a_crash(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout=b"\xff\xfe not utf8", stderr=b""
        )
        with patch("subprocess.run", return_value=completed):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        data, reason = required_json(call)
        self.assertIsNone(data)
        self.assertEqual(reason, "empty_survey")

    def test_run_gh_bad_json_bytes_are_empty_not_a_crash(self) -> None:
        completed = subprocess.CompletedProcess(
            args=["gh"], returncode=0, stdout=b"not-json", stderr=b""
        )
        with patch("subprocess.run", return_value=completed):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.stdout, "not-json")
        data, reason = required_json(call)
        self.assertIsNone(data)
        self.assertEqual(reason, "empty_survey")

    def test_loads_json_rejects_bad_bytes_without_raising(self) -> None:
        self.assertEqual(decode_gh_bytes(b"\xff"), "")
        self.assertIsNone(loads_json(b"\xff"))
        self.assertIsNone(loads_json("not-json"))
        self.assertEqual(loads_json(b'{"ok": true}'), {"ok": True})
