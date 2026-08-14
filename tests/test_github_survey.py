from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_survey import GhCall, classify_gh_argv, run_gh, survey_public_repo
from github_survey.gh import (
    decode_gh_bytes,
    gh_argv,
    gh_child_env,
    isolated_gh_argv,
    isolated_gh_cwd,
    isolated_gh_env,
    loads_json,
    required_json,
)

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

    def test_run_gh_uses_empty_temp_cwd_not_home_or_checkout(self) -> None:
        seen: list[str] = []
        host = Path.cwd().resolve()
        home = Path.home().resolve()

        def fake_run(*args, **kwargs):
            cwd = Path(kwargs["cwd"]).resolve()
            seen.append(str(cwd))
            self.assertTrue(cwd.is_dir())
            self.assertEqual(list(cwd.iterdir()), [])
            self.assertNotEqual(cwd, host)
            self.assertNotEqual(cwd, home)
            self.assertTrue(isolated_gh_cwd(cwd))
            return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=b"{}", stderr=b"")

        with patch("subprocess.run", side_effect=fake_run):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "{}")
        self.assertEqual(len(seen), 1)
        self.assertFalse(Path(seen[0]).exists())

    def test_cwd_outside_empty_temp_is_silence(self) -> None:
        self.assertFalse(isolated_gh_cwd(Path.home()))
        self.assertFalse(isolated_gh_cwd(Path.cwd()))
        with tempfile.TemporaryDirectory() as tmp:
            filled = Path(tmp) / "checkout"
            filled.mkdir()
            (filled / "secret.txt").write_text("host file", encoding="utf-8")
            self.assertFalse(isolated_gh_cwd(filled))
            empty = Path(tmp) / "empty"
            empty.mkdir()
            self.assertTrue(isolated_gh_cwd(empty))
        inside_checkout = Path.cwd() / "influenzer-gh-not-isolated"
        inside_checkout.mkdir()
        try:
            self.assertFalse(isolated_gh_cwd(inside_checkout))
        finally:
            inside_checkout.rmdir()

        def fake_run(*args, **kwargs):
            raise AssertionError("gh must not spawn when cwd is not isolated")

        with patch("tempfile.mkdtemp", return_value=str(Path.home())), patch(
            "subprocess.run", side_effect=fake_run
        ):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        self.assertEqual(call.stderr, "")

    def test_gh_is_argv_list_never_a_shell_string(self) -> None:
        self.assertEqual(gh_argv(["repo", "view", REPO]), ["gh", "repo", "view", REPO])
        self.assertTrue(isolated_gh_argv(["gh", "repo", "view", REPO]))
        self.assertIsNone(gh_argv(f"gh repo view {REPO}; rm -rf /"))
        self.assertFalse(isolated_gh_argv(f"gh repo view {REPO}; rm -rf /"))
        self.assertFalse(isolated_gh_argv(["sh", "-c", f"gh repo view {REPO}"]))
        self.assertIsNone(gh_argv(None))
        seen: list[object] = []

        def fake_run(*args, **kwargs):
            cmd = args[0] if args else kwargs.get("args")
            seen.append(cmd)
            self.assertIsInstance(cmd, list)
            self.assertEqual(cmd[0], "gh")
            self.assertFalse(kwargs.get("shell", False))
            return subprocess.CompletedProcess(args=cmd, returncode=0, stdout=b"{}", stderr=b"")

        with patch("subprocess.run", side_effect=fake_run):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(seen, [["gh", "repo", "view", REPO]])

    def test_shell_string_or_bad_slug_is_silence_not_a_spawn(self) -> None:
        def fake_run(*args, **kwargs):
            raise AssertionError("gh must not spawn a shell string or a bad slug")

        with patch("subprocess.run", side_effect=fake_run):
            shell = run_gh("repo view owner/name; id")  # type: ignore[arg-type]
            bad = run_gh(["repo", "view", "owner/name; id"])
            injected = run_gh(["api", "repos/owner/name;id/readme"])
        self.assertEqual(shell.returncode, 0)
        self.assertEqual(shell.stdout, "")
        self.assertEqual(shell.stderr, "")
        self.assertEqual(bad.returncode, 0)
        self.assertEqual(bad.stdout, "")
        self.assertEqual(injected.returncode, 0)
        self.assertEqual(injected.stdout, "")

    def test_gh_child_env_is_allowlist_not_host_world(self) -> None:
        host = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/tmp/fake-home",
            "LANG": "C",
            "GH_TOKEN": "gh-ok",
            "GITHUB_TOKEN": "github-ok",
            "AWS_SECRET_ACCESS_KEY": "host-secret",
            "ANTHROPIC_API_KEY": "host-secret",
            "SSH_AUTH_SOCK": "/tmp/ssh",
            "SOCIAL_TOKEN": "do-not-inherit",
        }
        child = gh_child_env(host)
        self.assertEqual(
            child,
            {
                "PATH": "/usr/bin:/bin",
                "HOME": "/tmp/fake-home",
                "LANG": "C",
                "GH_TOKEN": "gh-ok",
                "GITHUB_TOKEN": "github-ok",
            },
        )
        self.assertTrue(isolated_gh_env(child))
        self.assertFalse(isolated_gh_env(host))
        self.assertFalse(isolated_gh_env(None))
        self.assertTrue(isolated_gh_env({}))

    def test_run_gh_passes_allowlisted_env_not_host_secrets(self) -> None:
        host = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/tmp/fake-home",
            "LANG": "C",
            "GH_TOKEN": "gh-ok",
            "AWS_SECRET_ACCESS_KEY": "host-secret",
            "ANTHROPIC_API_KEY": "host-secret",
            "SSH_AUTH_SOCK": "/tmp/ssh",
            "SOCIAL_TOKEN": "do-not-inherit",
        }
        seen: list[object] = []

        def fake_run(*args, **kwargs):
            env = kwargs.get("env")
            seen.append(env)
            self.assertIsInstance(env, dict)
            self.assertIsNot(env, os.environ)
            self.assertTrue(isolated_gh_env(env))
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertNotIn("ANTHROPIC_API_KEY", env)
            self.assertNotIn("SSH_AUTH_SOCK", env)
            self.assertNotIn("SOCIAL_TOKEN", env)
            self.assertEqual(env.get("PATH"), "/usr/bin:/bin")
            self.assertEqual(env.get("GH_TOKEN"), "gh-ok")
            return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=b"{}", stderr=b"")

        with patch.dict(os.environ, host, clear=True), patch("subprocess.run", side_effect=fake_run):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "{}")
        self.assertEqual(len(seen), 1)

    def test_env_outside_allowlist_is_silence_not_a_spawn(self) -> None:
        leak = {"PATH": "/bin", "AWS_SECRET_ACCESS_KEY": "host-secret"}
        self.assertFalse(isolated_gh_env(leak))

        def fake_run(*args, **kwargs):
            raise AssertionError("gh must not spawn when env is not isolated")

        with patch("github_survey.gh.gh_child_env", return_value=leak), patch(
            "subprocess.run", side_effect=fake_run
        ):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        self.assertEqual(call.stderr, "")
