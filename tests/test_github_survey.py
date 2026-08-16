from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from github_survey import GhCall, classify_gh_argv, run_gh, survey_public_repo
from github_survey.gh import (
    allowlisted_gh_argv,
    decode_gh_bytes,
    gh_argv,
    gh_child_env,
    isolated_gh_argv,
    isolated_gh_cwd,
    isolated_gh_env,
    loads_json,
    required_json,
)
from github_survey.survey import (
    LOOK_OVER_LIMIT,
    MAX_GH_LOOK_BYTES,
    MAX_PAGES,
    MAX_STATE_BYTES,
    look_api_only_gh,
    look_argv_is_unbounded_pages,
    look_argv_launches_project,
    look_argv_leaves_declared_repo,
    look_bytes_over_limit,
    look_declared_gh,
    look_payload_reason,
    look_short_gh,
    state_bytes_over_limit,
)

from tests.gh_scripts import NOW, REPO, b64_readme, noise_script, repo_json, ship_script, ScriptedGh


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

    def test_auth_failure_is_empty_look_not_loop_death(self) -> None:
        out = self._survey({"repo": GhCall(1, "", "gh: To get started with GitHub CLI, run: gh auth login")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)
        self.assertNotIn("brief_id", out)

    def test_rate_limit_is_empty_look_not_loop_death(self) -> None:
        out = self._survey({"repo": GhCall(1, "", "HTTP 429: API rate limit exceeded")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)

    def test_network_pad_is_empty_look_not_loop_death(self) -> None:
        out = self._survey({"repo": GhCall(1, "", "Get \"https://api.github.com/user\": dial tcp: lookup api.github.com: no such host")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)

    def test_oserror_from_runner_is_empty_look_not_crash(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise OSError("network is unreachable")

        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            out = survey_public_repo(REPO, gh=boom, now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])

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

    def test_private_repo_is_silence_even_with_a_ship_window(self) -> None:
        out = self._survey(ship_script(repo=GhCall(0, repo_json(private=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)
        self.assertNotIn("brief_id", out)

    def test_archived_repo_is_silence_even_with_a_ship_window(self) -> None:
        out = self._survey(ship_script(repo=GhCall(0, repo_json(archived=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "archived_repo")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)
        self.assertNotIn("brief_id", out)

    def test_disabled_repo_is_silence_not_a_museum_launch(self) -> None:
        out = self._survey(ship_script(repo=GhCall(0, repo_json(disabled=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "archived_repo")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)

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

    def test_oversized_readme_is_empty_look_not_a_feast(self) -> None:
        huge = "# Demo\n\n" + ("uv run influenzer-tick --once\n" * 80_000)
        self.assertTrue(look_bytes_over_limit(huge))
        out = self._survey(ship_script(readme=GhCall(0, b64_readme(huge))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertNotIn("survey", out)
        self.assertNotIn("brief_id", out)

    def test_oversized_json_from_gh_is_empty_look(self) -> None:
        pad = "x" * (MAX_GH_LOOK_BYTES + 1)
        out = self._survey({"repo": GhCall(0, json.dumps({"nameWithOwner": REPO, "pad": pad}))})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])


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

    def test_hard_byte_limit_is_a_look_not_a_feast(self) -> None:
        self.assertEqual(MAX_GH_LOOK_BYTES, 1 * 1024 * 1024)
        self.assertEqual(MAX_STATE_BYTES, 50 * 1024 * 1024)
        self.assertGreater(MAX_STATE_BYTES, MAX_GH_LOOK_BYTES)
        self.assertFalse(look_bytes_over_limit("ok"))
        self.assertTrue(look_bytes_over_limit("x" * (MAX_GH_LOOK_BYTES + 1)))
        self.assertFalse(state_bytes_over_limit("ok"))
        with patch("github_survey.survey.MAX_STATE_BYTES", 16):
            self.assertTrue(state_bytes_over_limit("x" * 64))

    def test_look_drops_oversized_stdout(self) -> None:
        def inner(_argv: object) -> GhCall:
            return GhCall(0, "x" * (MAX_GH_LOOK_BYTES + 1))

        call = look_short_gh(inner)(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        self.assertEqual(call.stderr, LOOK_OVER_LIMIT)
        self.assertEqual(look_payload_reason(call), "empty_survey")

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

    def test_allowlist_is_read_only_catalog_not_compose(self) -> None:
        self.assertTrue(allowlisted_gh_argv(["gh", "repo", "view", REPO]))
        self.assertTrue(allowlisted_gh_argv(["gh", "repo", "view", REPO, "--json", "url"]))
        self.assertTrue(
            allowlisted_gh_argv(["gh", "pr", "list", "--repo", REPO, "--state", "merged", "--limit", "20", "--json", "url"])
        )
        self.assertTrue(
            allowlisted_gh_argv(
                ["gh", "release", "list", "--repo", REPO, "--limit", "10", "--exclude-drafts", "--json", "tagName"]
            )
        )
        self.assertTrue(allowlisted_gh_argv(["gh", "api", f"repos/{REPO}/readme"]))
        self.assertTrue(allowlisted_gh_argv(["gh", "api", f"repos/{REPO}/tags?per_page=20"]))
        self.assertTrue(
            allowlisted_gh_argv(
                ["gh", "api", f"repos/{REPO}/issues/comments?per_page=100&since=2026-08-06T06:00:00Z"]
            )
        )
        self.assertTrue(allowlisted_gh_argv(["gh", "api", f"repos/{REPO}/pulls/comments?per_page=100"]))
        self.assertFalse(allowlisted_gh_argv(["repo", "view", REPO]))
        self.assertFalse(allowlisted_gh_argv(["gh", "auth", "status"]))
        self.assertFalse(allowlisted_gh_argv(["gh", "api", f"repos/{REPO}/readme", "-X", "GET"]))
        self.assertFalse(allowlisted_gh_argv(["gh", "api", f"POST:/repos/{REPO}/issues/1/comments"]))

    def test_write_argv_is_silence_not_a_comment(self) -> None:
        def fake_run(*args, **kwargs):
            raise AssertionError("gh must not spawn comment/label/close/push")

        writes = (
            ["issue", "comment", REPO, "1", "--body", "hi"],
            ["pr", "comment", "1", "--body", "hi"],
            ["api", f"repos/{REPO}/issues/1/comments", "-X", "POST", "-f", "body=hi"],
            ["api", f"repos/{REPO}/issues/comments", "-f", "body=hi"],
            ["issue", "create", "--repo", REPO, "--title", "x", "--body", "y"],
            ["pr", "create", "--repo", REPO, "--title", "x", "--body", "y"],
            ["label", "create", "ship", "--repo", REPO],
            ["issue", "close", "1", "--repo", REPO],
            ["pr", "close", "1", "--repo", REPO],
            ["pr", "merge", "1", "--repo", REPO],
            ["release", "create", "v1.0.0", "--repo", REPO],
            ["repo", "sync", REPO],
            ["auth", "login"],
            ["api", "user"],
            ["api", f"repos/{REPO}/dispatches", "-X", "POST"],
        )
        with patch("subprocess.run", side_effect=fake_run):
            for argv in writes:
                with self.subTest(argv=argv):
                    self.assertFalse(allowlisted_gh_argv(["gh", *argv]))
                    call = run_gh(argv)
                    self.assertEqual(call.returncode, 0)
                    self.assertEqual(call.stdout, "")
                    self.assertEqual(call.stderr, "")

    def test_child_env_is_allowlist_not_the_host_world(self) -> None:
        host = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/tmp/influenzer-home",
            "LANG": "C",
            "GH_TOKEN": "gh-only-token",
            "AWS_SECRET_ACCESS_KEY": "host-secret",
            "SSH_AUTH_SOCK": "/tmp/ssh-agent",
            "GITHUB_TOKEN": "github-only-token",
            "UNSAFE_PARENT": "do-not-inherit",
        }
        child = gh_child_env(host)
        self.assertEqual(child["PATH"], "/usr/bin:/bin")
        self.assertEqual(child["GH_TOKEN"], "gh-only-token")
        self.assertEqual(child["GITHUB_TOKEN"], "github-only-token")
        self.assertEqual(child["GH_PROMPT_DISABLED"], "1")
        self.assertEqual(child["GH_NO_UPDATE_NOTIFIER"], "1")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", child)
        self.assertNotIn("SSH_AUTH_SOCK", child)
        self.assertNotIn("UNSAFE_PARENT", child)
        self.assertTrue(isolated_gh_env(child))
        self.assertFalse(isolated_gh_env(host))
        self.assertFalse(isolated_gh_env(None))
        self.assertFalse(isolated_gh_env({}))
        self.assertFalse(isolated_gh_env({"AWS_SECRET_ACCESS_KEY": "host-secret"}))

        seen: list[dict[str, str]] = []

        def fake_run(*args, **kwargs):
            env = kwargs.get("env")
            self.assertIsInstance(env, dict)
            seen.append(env)
            self.assertTrue(isolated_gh_env(env))
            self.assertNotIn("AWS_SECRET_ACCESS_KEY", env)
            self.assertNotIn("SSH_AUTH_SOCK", env)
            self.assertNotIn("UNSAFE_PARENT", env)
            return subprocess.CompletedProcess(args=["gh"], returncode=0, stdout=b"{}", stderr=b"")

        with patch.dict(
            "os.environ",
            {
                "PATH": "/usr/bin:/bin",
                "AWS_SECRET_ACCESS_KEY": "host-secret",
                "SSH_AUTH_SOCK": "/tmp/ssh-agent",
                "UNSAFE_PARENT": "do-not-inherit",
            },
            clear=True,
        ), patch("subprocess.run", side_effect=fake_run):
            call = run_gh(["repo", "view", REPO])
        self.assertEqual(call.returncode, 0)
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["PATH"], "/usr/bin:/bin")
        self.assertNotIn("AWS_SECRET_ACCESS_KEY", seen[0])

    def test_env_outside_allowlist_is_silence_not_a_spawn(self) -> None:
        def fake_run(*args, **kwargs):
            raise AssertionError("gh must not spawn when env is not allowlisted")

        leak = {
            "PATH": "/usr/bin:/bin",
            "AWS_SECRET_ACCESS_KEY": "host-secret",
        }
        with patch("github_survey.gh.gh_child_env", return_value=leak), patch(
            "subprocess.run", side_effect=fake_run
        ):
            call = run_gh(["repo", "view", REPO])
        self.assertFalse(isolated_gh_env(leak))
        self.assertEqual(call.returncode, 0)
        self.assertEqual(call.stdout, "")
        self.assertEqual(call.stderr, "")


class LookPageCeilingTests(unittest.TestCase):
    def test_paginate_and_huge_limit_are_unbounded(self) -> None:
        self.assertTrue(look_argv_is_unbounded_pages(["pr", "list", "--repo", REPO, "--paginate"]))
        self.assertTrue(look_argv_is_unbounded_pages(["gh", "api", "--paginate", f"repos/{REPO}/tags"]))
        self.assertTrue(look_argv_is_unbounded_pages(["pr", "list", "--repo", REPO, "--limit", "999"]))
        self.assertTrue(look_argv_is_unbounded_pages("gh api --paginate repos/owner/name/issues"))
        self.assertFalse(look_argv_is_unbounded_pages(["pr", "list", "--repo", REPO, "--limit", "20"]))
        self.assertFalse(look_argv_is_unbounded_pages(["api", f"repos/{REPO}/tags?per_page=20"]))

    def test_look_stops_after_max_pages(self) -> None:
        seen: list[tuple[str, ...]] = []

        def inner(argv: object) -> GhCall:
            tokens = tuple(argv) if isinstance(argv, (list, tuple)) else (str(argv),)
            seen.append(tokens)
            return GhCall(0, json.dumps([{"n": len(seen)}]))

        runner = look_short_gh(inner)
        first = runner(["api", f"repos/{REPO}/tags?per_page=20"])
        second = runner(["api", f"repos/{REPO}/tags?per_page=20"])
        third = runner(["api", f"repos/{REPO}/tags?per_page=20"])
        other = runner(["api", f"repos/{REPO}/issues/comments?per_page=100"])
        self.assertEqual(MAX_PAGES, 2)
        self.assertEqual(json.loads(first.stdout), [{"n": 1}])
        self.assertEqual(json.loads(second.stdout), [{"n": 2}])
        self.assertEqual(third.stdout, "[]")
        self.assertEqual(json.loads(other.stdout), [{"n": 3}])
        self.assertEqual(len(seen), MAX_PAGES + 1)

    def test_whole_history_is_silence_not_a_spawn(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise AssertionError("look must not walk every GitHub page")

        runner = look_short_gh(boom)
        paginate = runner(["pr", "list", "--repo", REPO, "--state", "merged", "--paginate"])
        huge = runner(["pr", "list", "--repo", REPO, "--limit", "999"])
        self.assertEqual(paginate.returncode, 0)
        self.assertEqual(paginate.stdout, "")
        self.assertEqual(huge.returncode, 0)
        self.assertEqual(huge.stdout, "")

    def test_survey_does_not_eat_repo_history(self) -> None:
        fake = ScriptedGh(ship_script())
        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            out = survey_public_repo(REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        kinds = [classify_gh_argv(list(argv)) for argv in fake.calls]
        self.assertLessEqual(kinds.count("prs"), MAX_PAGES)
        self.assertLessEqual(kinds.count("releases"), MAX_PAGES)
        self.assertLessEqual(kinds.count("tags"), MAX_PAGES)
        self.assertFalse(any(look_argv_is_unbounded_pages(list(argv)) for argv in fake.calls))
        self.assertFalse(any(look_argv_leaves_declared_repo(list(argv), REPO) for argv in fake.calls))


class LookStaysOnDeclaredRepoTests(unittest.TestCase):
    def test_foreign_slug_leaves_declared_repo(self) -> None:
        self.assertTrue(look_argv_leaves_declared_repo(["repo", "view", "other/tool"], REPO))
        self.assertTrue(
            look_argv_leaves_declared_repo(
                ["pr", "list", "--repo", "other/tool", "--state", "merged"], REPO
            )
        )
        self.assertTrue(look_argv_leaves_declared_repo(["api", "repos/other/tool/readme"], REPO))
        self.assertTrue(look_argv_leaves_declared_repo("gh repo view other/tool", REPO))
        self.assertFalse(look_argv_leaves_declared_repo(["repo", "view", REPO], REPO))
        self.assertFalse(
            look_argv_leaves_declared_repo(
                ["pr", "list", "--repo", REPO, "--state", "merged"], REPO
            )
        )
        self.assertFalse(look_argv_leaves_declared_repo(["api", f"repos/{REPO}/readme"], REPO))
        self.assertFalse(
            look_argv_leaves_declared_repo(["api", f"repos/{REPO}/tags?per_page=20"], REPO)
        )

    def test_foreign_repo_link_is_silence_not_a_survey(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise AssertionError("look must not survey a foreign repo from inbound text")

        runner = look_declared_gh(REPO, boom)
        view = runner(["repo", "view", "other/tool"])
        listed = runner(["pr", "list", "--repo", "other/tool", "--state", "merged"])
        api = runner(["api", "repos/other/tool/readme"])
        self.assertEqual(view.returncode, 0)
        self.assertEqual(view.stdout, "")
        self.assertEqual(listed.returncode, 0)
        self.assertEqual(listed.stdout, "")
        self.assertEqual(api.returncode, 0)
        self.assertEqual(api.stdout, "")

    def test_inbound_foreign_link_in_issue_stays_text_not_a_survey(self) -> None:
        inbound = ship_script()
        inbound["prs"] = GhCall(
            0,
            json.dumps(
                [
                    {
                        "number": 12,
                        "title": "feat: local HoM operator scores briefs",
                        "url": "https://github.com/mikolaj92/demo/pull/12",
                        "mergedAt": "2026-08-12T12:00:00Z",
                        "body": "See also https://github.com/other/tool — not our watch.",
                    }
                ]
            ),
        )
        fake = ScriptedGh(inbound)
        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            out = survey_public_repo(REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["repo"], REPO)
        self.assertTrue(fake.calls)
        self.assertFalse(any(look_argv_leaves_declared_repo(list(argv), REPO) for argv in fake.calls))
        self.assertEqual(
            out["survey"]["prs"][0]["body"],
            "See also https://github.com/other/tool — not our watch.",
        )


class LookDoesNotLaunchProjectTests(unittest.TestCase):
    def test_install_and_run_argv_launches_project(self) -> None:
        self.assertTrue(look_argv_launches_project(["uv", "run", "influenzer-tick", "--once"]))
        self.assertTrue(look_argv_launches_project(["/usr/bin/python3", "-m", "demo"]))
        self.assertTrue(look_argv_launches_project("npm install && npm start"))
        self.assertTrue(look_argv_launches_project(["make", "dev"]))
        self.assertTrue(look_argv_launches_project(["docker", "compose", "up"]))
        self.assertTrue(look_argv_launches_project(["git", "clone", f"https://github.com/{REPO}.git"]))
        self.assertFalse(look_argv_launches_project(["repo", "view", REPO]))
        self.assertFalse(look_argv_launches_project(["api", f"repos/{REPO}/readme"]))

    def test_launch_argv_is_silence_not_a_spawn(self) -> None:
        def boom(_argv: object) -> GhCall:
            raise AssertionError("look must not run the watched project")

        runner = look_api_only_gh(boom)
        for argv in (
            ["uv", "run", "influenzer-tick", "--once"],
            ["python3", "setup.py", "install"],
            ["npm", "start"],
            ["make", "test"],
            ["docker", "compose", "up"],
            ["git", "clone", f"https://github.com/{REPO}.git"],
        ):
            with self.subTest(argv=argv):
                call = runner(argv)
                self.assertEqual(call.returncode, 0)
                self.assertEqual(call.stdout, "")
                self.assertEqual(call.stderr, "")

    def test_survey_does_not_launch_the_project(self) -> None:
        fake = ScriptedGh(ship_script())
        with patch("subprocess.run", side_effect=AssertionError("survey must not call subprocess")):
            out = survey_public_repo(REPO, gh=fake, now=NOW)
        self.assertEqual(out["status"], "ok")
        self.assertTrue(fake.calls)
        self.assertFalse(any(look_argv_launches_project(list(argv)) for argv in fake.calls))
