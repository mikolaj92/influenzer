from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any
from unittest.mock import patch

from influenzer.brief_admit import SOURCE, admit_pack, open_story_reason
from influenzer.brief_scan import scan_github
from influenzer.config import Config, load_config, write_config
from influenzer.domain import Project
from influenzer.hom import Brief, Fact
from github_pack.pack import README_WITHOUT_QUICKSTART_REASON
from influenzer.playbook import ArenaId, CALENDAR_FILLER_REASON, CLOUD_DRIVE_REASON, COUNTER_THANKS_REASON, DECK_REASON, EVENT_NOT_A_SHIP, FOG_REASON, FOMO_REASON, FOUNDER_JOURNAL_REASON, LEAD_MAGNET_REASON, LINKTREE_REASON, LOGO_REVEAL_NOT_A_SHIP, LIVING_STACK_REASON, MEME_REASON, SECRET_REASON, StoryKind
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from github_survey import GhCall
from github_survey.survey import MAX_GH_LOOK_BYTES
from tests.gh_scripts import NOW, REPO, SHIP_PR, SHIP_RELEASE, b64_readme, noise_script, repo_json, ship_script, ScriptedGh


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


OTHER_REPO = "mikolaj92/other"
OTHER_SHIP_PR = "https://github.com/mikolaj92/other/pull/4"
OTHER_SHIP_RELEASE = "https://github.com/mikolaj92/other/releases/tag/v0.2.0"


def _other_ship_pack() -> dict[str, Any]:
    return {
        "status": "ok",
        "repo": OTHER_REPO,
        "brief_id": "scan-v0-2-0",
        "tryable": True,
        "facts": [
            {
                "kind": "release",
                "text": "Released v0.2.0",
                "artifact_url": OTHER_SHIP_RELEASE,
            },
            {
                "kind": "pr",
                "text": "Merged a tryable ship",
                "artifact_url": OTHER_SHIP_PR,
            },
        ],
    }


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
        self.assertEqual(out["reason"], "pending_brief")
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-1-0"))
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)
        self.assertEqual(self.repo.list_briefs("app-2"), [])

    def test_other_project_pending_brief_is_machine_silence(self) -> None:
        self.repo.save_brief(
            Brief.create(
                project_id="app-1",
                brief_id="manual-1",
                facts=(Fact(text="already working a story"),),
                story_kind=StoryKind.MAJOR,
                source="cli",
            )
        )
        _project(self.repo, "app-2")
        self.assertEqual(open_story_reason(self.repo, "app-2"), "pending_brief")
        out = admit_pack(self.repo, _other_ship_pack(), project_id="app-2", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_brief")
        self.assertFalse(out["published"])
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-2-0"))
        self.assertEqual(self.repo.list_briefs("app-2"), [])

    def test_other_project_social_draft_is_machine_silence(self) -> None:
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
        _project(self.repo, "app-2")
        self.assertEqual(open_story_reason(self.repo, "app-2", NOW), "social_draft")
        out = admit_pack(self.repo, _other_ship_pack(), project_id="app-2", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "social_draft")
        self.assertFalse(out["published"])
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-2-0"))

    def test_other_project_living_stack_is_machine_silence(self) -> None:
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
        self.assertEqual(self.repo.living_stack_arena("app-1", NOW), ArenaId.GITHUB)
        self.assertEqual(self.repo.living_stack_arena("app-2", NOW), ArenaId.GITHUB)
        self.assertEqual(open_story_reason(self.repo, "app-1", NOW), LIVING_STACK_REASON)
        _project(self.repo, "app-2")
        self.assertEqual(open_story_reason(self.repo, "app-2", NOW), LIVING_STACK_REASON)
        same = admit_pack(self.repo, _other_ship_pack(), project_id="app-1", now=NOW)
        self.assertEqual(same["status"], "noop")
        self.assertEqual(same["reason"], LIVING_STACK_REASON)
        out = admit_pack(self.repo, _other_ship_pack(), project_id="app-2", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], LIVING_STACK_REASON)
        self.assertFalse(out["published"])
        self.assertIsNone(self.repo.get_brief("app-2", "scan-v0-2-0"))

        later = "2026-08-19T06:00:00Z"
        self.assertIsNone(self.repo.living_stack_arena("app-2", later))
        self.assertIsNone(open_story_reason(self.repo, "app-2", later))
        after = admit_pack(self.repo, _other_ship_pack(), project_id="app-2", now=later)
        self.assertEqual(after["status"], "ok")
        self.assertEqual(after["brief_id"], "scan-v0-2-0")
        self.assertFalse(after["published"])
        stored = self.repo.get_brief("app-2", "scan-v0-2-0")
        assert stored is not None
        self.assertEqual(stored.status, "pending")

    def test_processed_same_repo_on_another_project_is_already_told(self) -> None:
        first = self._scan(ship_script())
        self.assertEqual(first["status"], "ok")
        tick(self.repo, self.cfg, due=(), now=NOW)
        self.repo.conn.execute("DELETE FROM operator_drafts")
        self.repo.conn.execute("DELETE FROM content_revisions")
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
        self.assertEqual(self.repo.list_briefs("app-2"), [])

    def test_archived_repo_look_is_silence_even_with_a_ship_window(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(archived=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "archived_repo")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_disabled_repo_look_is_silence_not_a_museum_launch(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(disabled=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "archived_repo")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_archived_repo_pack_is_silence(self) -> None:
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
                    {"kind": "signal", "text": "isArchived: true"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "archived_repo")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_fork_look_is_silence_even_when_owner_is_ours(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(fork=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "fork_not_a_site")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_private_repo_look_is_silence_even_when_owner_is_ours(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(private=True))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")
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

    def test_prose_install_look_is_silence_not_a_social_launch(self) -> None:
        prose = (
            "# Demo\n\nInstall with pip install influenzer, then uv run the tick.\n"
            "\n![demo](docs/demo.gif)\n"
        )
        out = self._scan(ship_script(readme=GhCall(0, b64_readme(prose))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], README_WITHOUT_QUICKSTART_REASON)
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

    def test_private_repo_pack_is_silence(self) -> None:
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
                    {"kind": "signal", "text": "isPrivate: true"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "private_repo")
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

    def test_pending_ci_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "CI is pending"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_ci_unknown")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_event_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "join us Thursday for the webinar"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], EVENT_NOT_A_SHIP)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_calendar_filler_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "happy Friday from the repo"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], CALENDAR_FILLER_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_counter_thanks_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "thanks for 1000 stars"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], COUNTER_THANKS_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_fog_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "you know who still scores remotely"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], FOG_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_founder_journal_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "desk setup for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], FOUNDER_JOURNAL_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_lead_magnet_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "ebook for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], LEAD_MAGNET_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_fomo_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "only 5 spots for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], FOMO_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_meme_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "drake meme for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], MEME_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_deck_pack_is_silence_not_an_artifact(self) -> None:
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
                    {"kind": "signal", "text": "pitch deck for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], DECK_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_linktree_pack_is_silence_not_an_artifact(self) -> None:
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
                    {"kind": "signal", "text": "linktree for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], LINKTREE_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_cloud_drive_pack_is_silence_not_a_site(self) -> None:
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
                    {"kind": "signal", "text": "Google Drive folder for the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], CLOUD_DRIVE_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_logo_reveal_pack_is_silence_not_a_ship(self) -> None:
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
                    {"kind": "signal", "text": "rebrand of the local tick"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], LOGO_REVEAL_NOT_A_SHIP)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_pending_ci_look_is_silence_so_next_monday_can_look(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(description="CI is pending"))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "pending_ci_unknown")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_failed_ci_pack_is_silence_not_tryable(self) -> None:
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
                    {"kind": "signal", "text": "CI failed"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "failed_ci_not_tryable")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_failed_ci_look_is_silence_so_next_monday_can_look(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(description="CI failed"))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "failed_ci_not_tryable")
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_secret_in_fact_pack_is_kill_silence_not_almost_redacted(self) -> None:
        leak = "env:INFLUENZER_TOKEN"
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
                    {"kind": "signal", "text": f"docs mention {leak}"},
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], SECRET_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertNotIn(leak, str(out))

    def test_secret_look_is_silence_so_next_monday_can_look(self) -> None:
        leak = "keychain:service/account"
        out = self._scan(ship_script(repo=GhCall(0, repo_json(description=f"docs mention {leak}"))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], SECRET_REASON)
        self.assertTrue(out["ok"])
        self.assertFalse(out["published"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_green_ci_look_is_not_this_failed_gate(self) -> None:
        out = self._scan(ship_script(repo=GhCall(0, repo_json(description="CI passed"))))
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["brief_id"], "scan-v0-1-0")
        self.assertEqual(len(self.repo.list_briefs("app-1")), 1)

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

    def test_oversized_readme_is_empty_look_and_writes_no_brief(self) -> None:
        huge = "# Demo\n\n" + ("uv run influenzer-tick --once\n" * 80_000)
        out = self._scan(ship_script(readme=GhCall(0, b64_readme(huge))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertEqual(self.repo.list_briefs("app-1"), [])
        self.assertFalse((self.home / "runtime.db").exists())

    def test_oversized_pack_is_empty_look_not_stored(self) -> None:
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
                        "text": "Released v0.1.0 " + ("x" * (MAX_GH_LOOK_BYTES + 1)),
                        "artifact_url": SHIP_RELEASE,
                    }
                ],
            },
            project_id="app-1",
            now=NOW,
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertEqual(self.repo.list_briefs("app-1"), [])

    def test_fifty_meg_payload_is_silence_not_stored(self) -> None:
        packed = {
            "status": "ok",
            "repo": REPO,
            "brief_id": "scan-v0-1-0",
            "tryable": True,
            "facts": [
                {
                    "kind": "release",
                    "text": "Released v0.1.0",
                    "artifact_url": SHIP_RELEASE,
                }
            ],
        }
        with patch("influenzer.brief_admit.state_bytes_over_limit", return_value=True):
            out = admit_pack(self.repo, packed, project_id="app-1", now=NOW)
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "empty_survey")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
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
