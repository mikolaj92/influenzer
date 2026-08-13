from __future__ import annotations

import base64
import io
import json
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence
from unittest.mock import patch

from influenzer.cli import main
from influenzer.config import Config, load_config, write_config
from influenzer.domain import Project
from influenzer.github_scan import (
    SOURCE,
    GhCall,
    classify_gh_argv,
    looks_like_patch_only,
    looks_like_ship_title,
    run_gh,
    scan_github,
)
from influenzer.hom import Brief, Fact
from influenzer.playbook import ArenaId, StoryKind
from influenzer.scheduler import tick
from influenzer.storage import StateRepository


NOW = "2026-08-13T06:00:00Z"
REPO = "mikolaj92/demo"
SHIP_PR = "https://github.com/mikolaj92/demo/pull/12"
SHIP_RELEASE = "https://github.com/mikolaj92/demo/releases/tag/v0.1.0"


class ScriptedGh:
    """Deterministic gh stand-in. Never talks to the network."""

    def __init__(self, script: dict[str, GhCall]):
        self.script = script
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> GhCall:
        self.calls.append(tuple(argv))
        key = classify_gh_argv(argv)
        if key not in self.script:
            raise AssertionError(f"unexpected gh argv {list(argv)!r} classified as {key!r}")
        return self.script[key]


def _b64_readme(text: str) -> str:
    return json.dumps(
        {
            "encoding": "base64",
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "html_url": f"https://github.com/{REPO}/blob/main/README.md",
        }
    )


def _repo_json(*, private: bool = False, description: str = "Local operator with a working install") -> str:
    return json.dumps(
        {
            "nameWithOwner": REPO,
            "isPrivate": private,
            "url": f"https://github.com/{REPO}",
            "description": description,
            "homepageUrl": "",
        }
    )


def _ship_script(**overrides: GhCall) -> dict[str, GhCall]:
    script = {
        "repo": GhCall(0, _repo_json()),
        "prs": GhCall(
            0,
            json.dumps(
                [
                    {
                        "number": 12,
                        "title": "feat: local HoM operator scores briefs",
                        "url": SHIP_PR,
                        "mergedAt": "2026-08-12T12:00:00Z",
                        "body": "Stranger can clone and run.",
                    }
                ]
            ),
        ),
        "releases": GhCall(
            0,
            json.dumps(
                [
                    {
                        "tagName": "v0.1.0",
                        "name": "v0.1.0",
                        "isDraft": False,
                        "isPrerelease": False,
                        "publishedAt": "2026-08-12T18:00:00Z",
                    }
                ]
            ),
        ),
        "tags": GhCall(0, json.dumps([{"name": "v0.1.0"}])),
        "readme": GhCall(0, _b64_readme("# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n")),
    }
    script.update(overrides)
    return script


def _noise_script() -> dict[str, GhCall]:
    return {
        "repo": GhCall(0, _repo_json()),
        "prs": GhCall(
            0,
            json.dumps(
                [
                    {
                        "number": 3,
                        "title": "chore: bump deps",
                        "url": "https://github.com/mikolaj92/demo/pull/3",
                        "mergedAt": "2026-08-12T12:00:00Z",
                        "body": "",
                    },
                    {
                        "number": 4,
                        "title": "typo in README",
                        "url": "https://github.com/mikolaj92/demo/pull/4",
                        "mergedAt": "2026-08-12T13:00:00Z",
                        "body": "",
                    },
                    {
                        "number": 5,
                        "title": "fix tests",
                        "url": "https://github.com/mikolaj92/demo/pull/5",
                        "mergedAt": "2026-08-12T14:00:00Z",
                        "body": "",
                    },
                ]
            ),
        ),
        "releases": GhCall(0, "[]"),
        "tags": GhCall(0, "[]"),
        "readme": GhCall(0, _b64_readme("# Demo\nWIP\n")),
    }


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


class ClassifyAndHeuristicsTests(unittest.TestCase):
    def test_argv_classes(self) -> None:
        self.assertEqual(classify_gh_argv(["repo", "view", REPO, "--json", "url"]), "repo")
        self.assertEqual(classify_gh_argv(["pr", "list", "--repo", REPO, "--state", "merged"]), "prs")
        self.assertEqual(classify_gh_argv(["release", "list", "--repo", REPO]), "releases")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/tags?per_page=20"]), "tags")
        self.assertEqual(classify_gh_argv(["api", f"repos/{REPO}/readme"]), "readme")
        self.assertEqual(classify_gh_argv(["auth", "status"]), "other")

    def test_noise_vs_ship_titles(self) -> None:
        self.assertTrue(looks_like_patch_only("chore: bump deps"))
        self.assertTrue(looks_like_patch_only("typo in README"))
        self.assertTrue(looks_like_patch_only("docs: fix badge"))
        self.assertTrue(looks_like_patch_only("fix tests"))
        self.assertFalse(looks_like_ship_title("chore: bump deps"))
        self.assertTrue(looks_like_ship_title("feat: local HoM operator scores briefs"))
        self.assertTrue(looks_like_ship_title("Shipped the operator tick"))
        self.assertFalse(looks_like_ship_title("Refactor storage helpers"))


class GitHubScanTests(unittest.TestCase):
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

    def _scan(self, script: dict[str, GhCall], **kwargs: Any) -> dict[str, Any]:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("scan must not call subprocess")):
            out = scan_github(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
                **kwargs,
            )
        return out

    def test_silence_on_commit_noise(self) -> None:
        out = self._scan(_noise_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "commit_noise")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_one_brief_on_ship_and_tryable(self) -> None:
        out = self._scan(_ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["brief_id"], "scan-v0-1-0")
        self.assertEqual(out["source"], SOURCE)
        self.assertTrue(out["claims_ship"])
        self.assertTrue(out["tryable"])
        self.assertTrue(out["pending"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertGreaterEqual(out["fact_count"], 2)
        stored = self.repo.get_brief("app-1", "scan-v0-1-0")
        assert stored is not None
        self.assertEqual(stored.status, "pending")
        self.assertEqual(stored.source, SOURCE)
        self.assertTrue(stored.claims_ship)
        self.assertTrue(stored.tryable)
        self.assertEqual(stored.story_kind, StoryKind.MAJOR)
        urls = {fact.artifact_url for fact in stored.facts if fact.artifact_url}
        self.assertIn(SHIP_PR, urls)
        self.assertIn(SHIP_RELEASE, urls)
        self.assertEqual(len(self.repo.list_pending_briefs("app-1")), 1)
        events = [row["event_type"] for row in self.repo.events("app-1")]
        self.assertIn("brief.scanned", events)

    def test_second_scan_is_silence_when_pending_exists(self) -> None:
        first = self._scan(_ship_script())
        self.assertEqual(first["status"], "ok")
        second = self._scan(_ship_script())
        self.assertEqual(second["status"], "noop")
        self.assertEqual(second["reason"], "pending_brief")
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

    def test_silence_when_unrelated_pending_brief_exists(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="already working a story"),),
                story_kind=StoryKind.MAJOR,
                source="cli",
            )
        )
        out = self._scan(_ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_brief")
        self.assertIsNone(self.repo.get_brief("app-1", "scan-v0-1-0"))

    def test_silence_when_social_draft_already_exists(self) -> None:
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
        stored = self.repo.get_brief("app-1", "prior-ship")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        self.assertIsNotNone(self.repo.get_operator_draft("app-1", "prior-ship"))
        out = self._scan(_ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "social_draft")

    def test_missing_gh_is_silence(self) -> None:
        out = self._scan({"repo": GhCall(127, "", "gh not found", missing=True)})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "gh_missing")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_auth_failure_is_silence(self) -> None:
        out = self._scan({"repo": GhCall(1, "", "gh: To get started with GitHub CLI, run: gh auth login")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "gh_auth")

    def test_empty_survey_is_silence(self) -> None:
        out = self._scan(
            {
                "repo": GhCall(0, _repo_json()),
                "prs": GhCall(0, "[]"),
                "releases": GhCall(0, "[]"),
                "tags": GhCall(0, "[]"),
                "readme": GhCall(0, "{}"),
            }
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")

    def test_private_repo_is_silence(self) -> None:
        out = self._scan(
            {
                "repo": GhCall(0, _repo_json(private=True)),
                "prs": GhCall(0, "[]"),
                "releases": GhCall(0, "[]"),
                "tags": GhCall(0, "[]"),
                "readme": GhCall(0, "{}"),
            }
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")

    def test_waitlist_release_is_silence(self) -> None:
        out = self._scan(
            _ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-wait",
                                "name": "Join the waitlist",
                                "isDraft": False,
                                "isPrerelease": False,
                                "publishedAt": "2026-08-12T18:00:00Z",
                            }
                        ]
                    ),
                )
            )
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "waitlist_not_tryable")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_malformed_json_is_silence_not_crash(self) -> None:
        out = self._scan({"repo": GhCall(0, "not-json")})
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")

    def test_already_told_artifact_is_silence_after_processing(self) -> None:
        first = self._scan(_ship_script())
        self.assertEqual(first["status"], "ok")
        tick(self.repo, self.cfg, due=(), now=NOW)
        # Drop the social draft so the open-story gate is not the reason.
        self.repo.conn.execute("DELETE FROM operator_drafts")
        self.repo.conn.execute("DELETE FROM content_revisions")
        out = self._scan(_ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "already_told")

    def test_tick_scores_scanned_brief_without_publishing(self) -> None:
        self.assertEqual(self._scan(_ship_script())["status"], "ok")
        out = tick(self.repo, self.cfg, due=(), now=NOW)
        self.assertFalse(out["mutated"])
        self.assertFalse(out["operator"]["published"])
        score = self.repo.get_operator_score("app-1", "scan-v0-1-0")
        assert score is not None
        self.assertEqual(score.verdict.value, "draft")
        cfg = load_config(str(self.home / "config.json"))
        self.assertFalse(cfg.scheduler_live_enabled)

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


class GitHubScanCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        self.assertEqual(main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)
        self.assertEqual(
            main(
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

    def test_cli_scan_writes_one_pending_brief(self) -> None:
        fake = ScriptedGh(_ship_script())
        buf = io.StringIO()
        fixed = datetime(2026, 8, 13, 6, 0, 0, tzinfo=timezone.utc)
        with (
            patch("influenzer.github_scan.run_gh", fake),
            patch("influenzer.github_scan._parse_now", return_value=fixed),
            patch("influenzer.github_scan.utc_now", return_value=NOW),
            patch("subprocess.run", side_effect=AssertionError("cli scan must not call subprocess")),
            patch("sys.stdout", buf),
        ):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
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
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            stored = repo.get_brief("app-1", "scan-v0-1-0")
            assert stored is not None
            self.assertEqual(stored.source, SOURCE)
            self.assertEqual(stored.status, "pending")

    def test_cli_invalid_repo_fails_closed_without_scan(self) -> None:
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "app-1",
                    "--repo",
                    "not a repo",
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("owner/name", buf.getvalue())

    def test_cli_missing_project_fails(self) -> None:
        buf = io.StringIO()
        with patch("sys.stderr", buf):
            code = main(
                [
                    "--config",
                    str(self.config),
                    "brief",
                    "scan",
                    "--project-id",
                    "missing",
                    "--repo",
                    REPO,
                ]
            )
        self.assertEqual(code, 1)
        self.assertIn("project not found", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
