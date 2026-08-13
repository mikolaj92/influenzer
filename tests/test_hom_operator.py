from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from influenzer.cli import main
from influenzer.config import Config, write_config
from influenzer.hom import (
    Brief,
    Fact,
    HomError,
    apply_brief,
    brief_from_mapping,
    compose_draft,
    is_ship_artifact,
    score_brief,
)
from influenzer.playbook import ARENAS, CANON_URL, SOCIAL_ARENAS, ArenaId, StoryKind, Verdict
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from influenzer.tick_all import main as tick_all_main


SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"
SHIP_ISSUE = "https://github.com/mikolaj92/influenzer/issues/4"
SHIP_RELEASE = "https://github.com/mikolaj92/influenzer/releases/tag/v0.1.0"


def _project(repo: StateRepository, project_id: str = "app-1") -> None:
    from influenzer.domain import Project

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


class PlaybookCopyTests(unittest.TestCase):
    def test_every_arena_has_costume_and_wave_checklist(self) -> None:
        self.assertGreaterEqual(len(ARENAS), 10)
        for arena, play in ARENAS.items():
            with self.subTest(arena=arena.value):
                self.assertTrue(play.costume)
                self.assertGreaterEqual(len(play.wave), 3)
                self.assertTrue(play.canon_url.startswith(CANON_URL))
                self.assertNotIn("champion", play.game.lower())

    def test_ship_artifact_accepts_pr_issue_release_only(self) -> None:
        self.assertTrue(is_ship_artifact(SHIP_PR))
        self.assertTrue(is_ship_artifact(SHIP_ISSUE))
        self.assertTrue(is_ship_artifact(SHIP_RELEASE))
        self.assertFalse(is_ship_artifact("https://example.com/ship"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/commit/abc"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer"))


class ScoreBriefTests(unittest.TestCase):
    def _brief(self, **overrides: object) -> Brief:
        facts = overrides.pop("facts", (Fact(text="local tick scores briefs", artifact_url=SHIP_PR),))
        kwargs = dict(
            project_id="app-1",
            brief_id="b1",
            facts=facts,
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        kwargs.update(overrides)
        return Brief.create(**kwargs)  # type: ignore[arg-type]

    def test_empty_facts_are_killed(self) -> None:
        score = score_brief(self._brief(facts=(), claims_ship=False, tryable=False))
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "empty_brief")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(self._brief(facts=()), score))

    def test_patch_stays_changelog_only(self) -> None:
        brief = self._brief(
            story_kind=StoryKind.PATCH,
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="typo in README"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "patch_changelog_only")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)

    def test_ship_without_artifact_is_killed(self) -> None:
        brief = self._brief(
            facts=(Fact(text="we shipped the operator"),),
            claims_ship=True,
            tryable=True,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "ship_claim_missing_artifact")

    def test_hype_without_tryable_demo_is_killed(self) -> None:
        brief = self._brief(tryable=False, claims_ship=True)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hype_without_demo")

    def test_hn_without_tryable_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            preferred_arena=ArenaId.HN,
            facts=(Fact(text="thinking about a launch post"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_tryable")

    def test_discord_is_not_a_launch_arena(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena="discord",
            facts=(Fact(text="stand up a Discord"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "discord_pre_pmf")

    def test_major_tryable_ship_drafts_one_hn_arena(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="Brief in, draft out on each tick", artifact_url=SHIP_PR),
                Fact(text="Dry-run still default"),
                Fact(text="Patches stay changelog-only"),
            )
        )
        decision = apply_brief(brief, now="2026-08-13T05:00:00Z")
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        self.assertEqual(decision.score.reason, "one_angle")
        self.assertIsNotNone(decision.draft)
        assert decision.draft is not None
        self.assertEqual(decision.draft.costume, "seminar")
        self.assertEqual(decision.draft.arena, ArenaId.HN)
        self.assertTrue(decision.draft.body.lstrip().startswith("Show HN:"))
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        self.assertNotIn("One angle:", decision.draft.body)
        self.assertIn(SHIP_PR, decision.draft.body)
        self.assertGreaterEqual(len(decision.draft.wave_checklist), 3)
        self.assertNotIn("linkedin", decision.draft.body.lower().split("show hn:", 1)[0])

    def test_preferred_x_uses_agora_costume_not_hn(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.X)
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.arena, ArenaId.X)
        self.assertEqual(decision.draft.costume, "agora")
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        first = decision.draft.body.splitlines()[0]
        self.assertTrue(first.strip())
        self.assertNotIn("http", first.lower())
        self.assertLess(len(decision.draft.body), 500)
        self.assertIn(SHIP_PR, decision.draft.body)

    def test_default_without_tryable_is_changelog_not_a_social_draft(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.EXPLORATION,
            facts=(Fact(text="explored adapter dry-run envelopes"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "exploration_not_a_post")
        self.assertIsNone(decision.draft)

    def test_decision_without_user_facing_change_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.DECISION,
            facts=(Fact(text="we picked SQLite over a hosted store"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "decision_not_user_facing")
        self.assertIsNone(decision.draft)

    def test_commit_noise_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.MAJOR,
            facts=(Fact(text="chore: bump deps"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "commit_noise_changelog")
        self.assertIsNone(compose_draft(brief, score))

    def test_waitlist_ship_claim_is_killed(self) -> None:
        brief = self._brief(
            facts=(Fact(text="join the waitlist, coming soon", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "waitlist_not_tryable")

    def test_press_release_tone_on_hn_is_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="we are excited to announce a game-changer", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "press_release_tone")
        self.assertIsNone(compose_draft(brief, score))

    def test_youtube_without_package_is_killed(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.YOUTUBE)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "cinema_missing_package")

    def test_shorts_without_hook_is_killed(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.SHORTS)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "fair_missing_hook")

    def test_reddit_without_named_room_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            preferred_arena=ArenaId.REDDIT,
            facts=(Fact(text="I struggled with subprocess timeouts looking like success"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "reddit_no_room")

    def test_x_without_tryable_is_killed_not_an_empty_feed_original(self) -> None:
        brief = self._brief(
            tryable=False,
            claims_ship=False,
            preferred_arena=ArenaId.X,
            facts=(Fact(text="thinking about posting a launch thread"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "x_empty_feed")

    def test_bluesky_without_artifact_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            preferred_arena=ArenaId.BLUESKY,
            facts=(Fact(text="vibe posting about the operator"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "bluesky_vibe_without_artifact")

    def test_mastodon_ship_claim_is_killed_as_pr_tone(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.MASTODON)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "mastodon_pr_tone")

    def test_linkedin_one_fact_is_killed_as_court_not_ready(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.LINKEDIN,
            facts=(Fact(text="shipped"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "court_not_ready")

    def test_hn_without_clickable_url_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.HN,
            facts=(Fact(text="a working demo exists on my laptop"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_tryable")

    def test_hard_issue_defaults_to_github_workshop_not_social(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.HARD_ISSUE,
            facts=(
                Fact(text="I struggled with timeouts looking like success"),
                Fact(text="unknown plus reconcile is the rule now"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.draft.arena, ArenaId.GITHUB)
        self.assertEqual(decision.draft.costume, "workshop")
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        self.assertIn("I struggled with timeouts looking like success", decision.draft.body)

    def test_youtube_with_package_drafts_cinema_only(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.YOUTUBE,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(kind="package", text="title plus thumb in 0.5s: one-angle operator tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.arena, ArenaId.YOUTUBE)
        self.assertEqual(decision.draft.costume, "cinema")

    def test_thin_x_brief_without_artifact_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.X,
            facts=(Fact(text="shipped it"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "thin_brief")
        self.assertIsNone(compose_draft(brief, score))

    def test_every_arena_has_a_fail_closed_gate(self) -> None:
        from influenzer.playbook import ARENA_GATES

        self.assertEqual(set(ARENA_GATES), set(ARENAS))
        self.assertTrue(ARENA_GATES[ArenaId.DISCORD].always_kill)
        self.assertNotIn(ArenaId.GITHUB, SOCIAL_ARENAS)

    def test_scoring_is_deterministic(self) -> None:
        brief = self._brief()
        one = score_brief(brief)
        two = score_brief(brief)
        self.assertEqual(one.score_hash, two.score_hash)
        self.assertEqual(one.verdict, two.verdict)
        self.assertEqual(one.arena, two.arena)

    def test_unknown_arena_is_rejected_at_ingest(self) -> None:
        with self.assertRaises(HomError):
            Brief.create(
                project_id="app-1",
                brief_id="b-bad",
                facts=(Fact(text="x"),),
                story_kind=StoryKind.MAJOR,
                preferred_arena="tiktok",
            )

    def test_json_rejects_secret_fields(self) -> None:
        with self.assertRaises(HomError):
            brief_from_mapping(
                {
                    "project_id": "app-1",
                    "brief_id": "b-secret",
                    "story_kind": "major",
                    "facts": [{"text": "nope"}],
                    "token": "should-not-be-here",
                }
            )


class TickBriefPathTests(unittest.TestCase):
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

    def test_tick_scores_pending_brief_and_second_tick_is_noop_for_it(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="ship-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["mutated"])
        self.assertFalse(out["operator"]["published"])
        self.assertEqual(out["operator"]["processed"], 1)
        outcome = out["operator"]["outcomes"][0]
        self.assertEqual(outcome["verdict"], "draft")
        self.assertEqual(outcome["arena"], "hn")
        self.assertFalse(outcome["published"])
        self.assertTrue(str(outcome.get("body") or "").startswith("Show HN:"))
        self.assertNotIn("Costume:", str(outcome.get("body") or ""))
        stored = self.repo.get_brief("app-1", "ship-1")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        draft = self.repo.get_operator_draft("app-1", "ship-1")
        assert draft is not None
        self.assertEqual(draft.costume, "seminar")
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)
        revision = self.repo.conn.execute(
            "SELECT status, source, kind FROM content_revisions WHERE revision_id=?",
            (draft.draft_id,),
        ).fetchone()
        self.assertEqual(revision["status"], "draft")
        self.assertEqual(revision["source"], "operator")
        self.assertEqual(revision["kind"], "post")

        again = tick(self.repo, self.cfg, due=(), now="2026-08-13T06:00:00Z")
        self.assertEqual(again["status"], "noop")
        self.assertEqual(again["operator"]["processed"], 0)
        drafts = list(self.repo.conn.execute("SELECT draft_id FROM operator_drafts"))
        self.assertEqual(len(drafts), 1)

    def test_tick_kill_persists_score_without_draft_or_publish(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="kill-1",
            facts=(Fact(text="we shipped it"),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        self.assertEqual(out["operator"]["outcomes"][0]["verdict"], "kill")
        self.assertEqual(out["operator"]["outcomes"][0]["reason"], "ship_claim_missing_artifact")
        self.assertIsNone(self.repo.get_operator_draft("app-1", "kill-1"))
        self.assertIsNone(
            self.repo.conn.execute("SELECT 1 FROM content_revisions").fetchone()
        )
        self.assertFalse(out["mutated"])

    def test_cli_ingest_and_tick_all_patch_is_changelog_only(self) -> None:
        code = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "ingest",
                "--project-id",
                "app-1",
                "--brief-id",
                "patch-1",
                "--story-kind",
                "patch",
                "--fact",
                "fix README typo",
            ]
        )
        self.assertEqual(code, 0)
        code = tick_all_main(["--config", str(self.home / "config.json")])
        self.assertEqual(code, 0)
        score = self.repo.get_operator_score("app-1", "patch-1")
        assert score is not None
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertIsNone(self.repo.get_operator_draft("app-1", "patch-1"))

    def test_cli_json_ingest_roundtrip_show(self) -> None:
        path = self.home / "brief.json"
        path.write_text(
            json.dumps(
                {
                    "brief_id": "json-1",
                    "story_kind": "hard_issue",
                    "claims_ship": False,
                    "tryable": True,
                    "preferred_arena": "reddit",
                    "facts": [
                        {"kind": "pain", "text": "subprocess timeouts looked like success in r/SideProject"},
                        {"kind": "fix", "text": "unknown plus reconcile, no blind retry"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        code = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "ingest",
                "--project-id",
                "app-1",
                "--from-json",
                str(path),
            ]
        )
        self.assertEqual(code, 0)
        tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        show = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "show",
                "--project-id",
                "app-1",
                "--brief-id",
                "json-1",
            ]
        )
        self.assertEqual(show, 0)
        draft = self.repo.get_operator_draft("app-1", "json-1")
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.REDDIT)
        self.assertEqual(draft.costume, "village")

    def test_config_still_has_no_secret_fields(self) -> None:
        raw = json.loads((self.home / "config.json").read_text(encoding="utf-8"))
        blob = json.dumps(raw)
        for needle in ("token", "password", "secret", "api_key"):
            self.assertNotIn(needle, blob)

    def test_tick_all_writes_fala_subprocess_result_without_opening_runtime_db(self) -> None:
        from influenzer.tick_all import write_fala_result

        fala_out = self.home / "fala-out"
        payload = {"status": "ok", "mutated": False, "operator": {"published": False, "processed": 1}}
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)})
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse(data["metadata"]["mutated"])
        self.assertEqual(data["reactions"][0]["kind"], "hom.decision")
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertIsNone(write_fala_result(payload, env={}))


class FalaPackageAndCatalogTests(unittest.TestCase):
    def test_fala_package_declares_operator_tick_on_sqlite_journal(self) -> None:
        import tomllib

        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        self.assertEqual(package["id"], "influenzer")
        self.assertEqual(package["runtime"]["backend"]["kind"], "sqlite")
        self.assertEqual(package["runtime"]["backend"]["path"], "runtime.db")
        self.assertNotEqual(package["runtime"]["backend"]["path"], "state.db")
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("operator_tick", paths)
        effectors = paths["operator_tick"]["effectors"]
        self.assertEqual(len(effectors), 1)
        self.assertEqual(effectors[0]["adapter"]["kind"], "subprocess")
        self.assertEqual(effectors[0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])
        blob = json.dumps(package)
        self.assertNotIn("ads", blob.lower())
        self.assertNotIn("native_function", blob)

    def test_catalog_score_brief_is_dry_and_never_publishes(self) -> None:
        from influenzer.catalog import list_effectors
        from influenzer.effector import run

        names = [entry["name"] for entry in list_effectors()]
        self.assertIn("score_brief", names)
        result = run(
            {
                "handler": "score_brief",
                "input": {
                    "project_id": "app-1",
                    "brief_id": "b-ship",
                    "story_kind": "major",
                    "claims_ship": True,
                    "tryable": True,
                    "facts": [
                        {
                            "text": "operator tick scores briefs",
                            "artifact_url": SHIP_PR,
                        }
                    ],
                },
            }
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["mutated"])
        self.assertFalse(result["published"])
        self.assertEqual(result["verdict"], "draft")
        self.assertEqual(result["arena"], "hn")

        killed = run(
            {
                "handler": "score_brief",
                "input": {
                    "project_id": "app-1",
                    "brief_id": "b-kill",
                    "story_kind": "major",
                    "claims_ship": True,
                    "tryable": True,
                    "facts": [{"text": "shipped with no proof"}],
                },
            }
        )
        self.assertEqual(killed["verdict"], "kill")
        self.assertFalse(killed["mutated"])
        self.assertFalse(killed["published"])


if __name__ == "__main__":
    unittest.main()
