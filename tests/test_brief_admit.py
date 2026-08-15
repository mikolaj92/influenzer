from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from influenzer.brief_admit import SOURCE, admit_pack
from influenzer.brief_scan import scan_github
from influenzer.config import Config, load_config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from influenzer.playbook import ArenaId, StoryKind
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from github_survey import GhCall
from tests.gh_scripts import NOW, REPO, SHIP_PR, SHIP_RELEASE, noise_script, repo_json, ship_script, ScriptedGh


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


class AdmitAndComposeTests(unittest.TestCase):
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

    def _scan(self, script: dict, **kwargs: Any) -> dict[str, Any]:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("scan must not call subprocess")):
            return scan_github(
                self.repo,
                project_id="app-1",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
                **kwargs,
            )

    def test_silence_on_commit_noise(self) -> None:
        out = self._scan(noise_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "commit_noise")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertFalse(out["mutated"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_one_brief_on_ship_and_tryable(self) -> None:
        out = self._scan(ship_script())
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
        first = self._scan(ship_script())
        self.assertEqual(first["status"], "ok")
        second = self._scan(ship_script())
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
        out = self._scan(ship_script())
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
        out = self._scan(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "social_draft")

    def test_already_told_artifact_is_silence_after_processing(self) -> None:
        first = self._scan(ship_script())
        self.assertEqual(first["status"], "ok")
        tick(self.repo, self.cfg, due=(), now=NOW)
        self.repo.conn.execute("DELETE FROM operator_drafts")
        self.repo.conn.execute("DELETE FROM content_revisions")
        out = self._scan(ship_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "already_told")

    def test_same_repo_on_another_project_is_already_told(self) -> None:
        first = self._scan(ship_script())
        self.assertEqual(first["status"], "ok")
        _project(self.repo, "app-2")
        fake = ScriptedGh(ship_script())
        with patch("subprocess.run", side_effect=AssertionError("scan must not call subprocess")):
            out = scan_github(
                self.repo,
                project_id="app-2",
                repo_slug=REPO,
                gh=fake,
                now=NOW,
            )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "already_told")
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-1-0"))
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertEqual(self.repo.list_briefs("app-2"), [])

    def test_fork_look_is_silence_even_when_owner_is_ours(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(fork=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "fork_not_a_site")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_empty_repo_look_is_silence_even_with_a_ship_window(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(empty=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_repo_not_a_site")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_missing_readme_look_is_silence_not_readme_without_gif(self) -> None:
        out = self._scan(ship_script(readme=GhCall(0, "{}")))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_repo_not_a_site")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_empty_repo_pack_is_silence(self) -> None:
        out = admit_pack(
            self.repo,
            {
                "status": "ok",
                "repo": REPO,
                "brief_id": "scan-v0-1-0",
                "tryable": True,
                "facts": [
                    {
                        "kind": "release",
                        "text": "Released v0.1.0",
                        "artifact_url": SHIP_RELEASE,
                    },
                    {"kind": "signal", "text": "isEmpty: true"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_repo_not_a_site")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_fork_pack_is_silence(self) -> None:
        out = admit_pack(
            self.repo,
            {
                "status": "ok",
                "repo": REPO,
                "brief_id": "scan-v0-1-0",
                "tryable": True,
                "facts": [
                    {
                        "kind": "release",
                        "text": "Released v0.1.0",
                        "artifact_url": SHIP_RELEASE,
                    },
                    {"kind": "signal", "text": "isFork: true"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "fork_not_a_site")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_pack_without_tryable_flag_is_silence(self) -> None:
        out = admit_pack(
            self.repo,
            {
                "status": "ok",
                "repo": REPO,
                "brief_id": "scan-v0-1-0",
                "facts": [{"kind": "release", "text": "Released v0.1.0", "artifact_url": SHIP_RELEASE}],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not_tryable")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_tick_scores_scanned_brief_without_publishing(self) -> None:
        self.assertEqual(self._scan(ship_script())["status"], "ok")
        out = tick(self.repo, self.cfg, due=(), now=NOW)
        self.assertFalse(out["mutated"])
        self.assertFalse(out["operator"]["published"])
        score = self.repo.get_operator_score("app-1", "scan-v0-1-0")
        assert score is not None
        self.assertEqual(score.verdict.value, "draft")
        cfg = load_config(str(self.home / "config.json"))
        self.assertFalse(cfg.scheduler_live_enabled)
