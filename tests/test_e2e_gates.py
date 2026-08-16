from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from influenzer.adapters.base import AdapterRequest
from influenzer.config import Config
from influenzer.content import create_revision, persist_revision
from influenzer.hom import Brief, Fact, Score, _gate_violation, compose_draft, score_brief
from influenzer.domain import (
    AccountStatus,
    AttemptStatus,
    ContentStatus,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    Project,
    PublishPlan,
    PlanStatus,
)
from influenzer.playbook import (
    ARENAS,
    ArenaId,
    COURT_NOT_A_LAUNCH_REASON,
    EMPTY_TAVERN_REASON,
    Verdict,
    choose_arena,
    court_reason,
    fair_loop_reason,
    has_court_insight,
    has_fair_loop,
    has_tavern_intent_split,
    has_tavern_seed,
    looks_like_court_launch,
    looks_like_fair_cta,
    looks_like_poll,
    looks_like_tavern_invite,
    tavern_reason,
    unquotable_reason,
)
from influenzer.scheduler import DueWork, tick
from influenzer.storage import StateRepository

SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"


class OrderedLiveGateTests(unittest.TestCase):
    """Fake e2e: app + builder isolation and ordered live outcomes without network."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.repo = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        self.app = Project.create(
            project_id="app-1",
            slug="my-app",
            name="My App",
            display_name="My App",
            voice="product",
            audience="customers",
            maintainer="mikolaj92",
            kind="app",
        )
        self.builder = Project.create(
            project_id="builder-1",
            slug="mikolaj",
            name="Mikolaj",
            display_name="Mikolaj",
            voice="builder",
            audience="builders",
            maintainer="mikolaj92",
            kind="builder",
        )
        self.repo.save_project(self.app)
        self.repo.save_project(self.builder)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def _seed(self, *, project_id: str, platform: str, plan_id: str, host: str | None = None):
        account = PlatformAccount(
            project_id=project_id,
            account_id=f"{platform}-{plan_id}",
            platform=platform,
            handle=f"@{project_id}",
            host=host,
            credential_ref="env:TOKEN",
            status=AccountStatus.CONNECTED,
        )
        self.repo.save_account(account)
        policy = PolicyVersion(
            project_id=project_id,
            policy_version_id=f"pol-{plan_id}",
            account_ids=(account.account_id,),
            actions=("publish",),
            content_kinds=("post",),
            max_posts_per_day=10,
            require_disclosures=False,
        ).with_hash()
        self.repo.save_policy(policy)
        grant = PolicyActivationGrant(
            project_id=project_id,
            grant_id=f"grant-{plan_id}",
            policy_version_id=policy.policy_version_id,
            policy_hash=policy.policy_hash,
            platform_account_id=account.account_id,
            actions=("publish",),
            actor="tester",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        self.repo.save_grant(grant)
        rev = create_revision(
            project_id=project_id,
            content_id=f"c-{plan_id}",
            revision_id=f"r-{plan_id}",
            body=f"{project_id} post",
            status=ContentStatus.READY,
        )
        persist_revision(self.repo, rev)
        plan = PublishPlan(
            project_id=project_id,
            plan_id=plan_id,
            content_revision_id=rev.revision_id,
            content_hash=rev.content_hash,
            platform_account_id=account.account_id,
            platform=platform,
            body=rev.body,
            status=PlanStatus.SCHEDULED,
            scheduled_at=None,
            created_at="2026-01-01T00:00:00Z",
            operation_key=f"op-{plan_id}",
        )
        self.repo.save_plan(plan)
        return DueWork(plan=plan, account=account, policy=policy, grant=grant)

    def test_app_and_builder_profiles_do_not_leak(self) -> None:
        self.assertNotEqual(self.app.brand.profile_hash, self.builder.brand.profile_hash)
        stored_app = self.repo.get_project("app-1")
        stored_builder = self.repo.get_project("builder-1")
        assert stored_app is not None and stored_builder is not None
        self.assertEqual(stored_app.kind, "app")
        self.assertEqual(stored_builder.kind, "builder")
        self.assertNotEqual(stored_app.brand.profile_hash, stored_builder.brand.profile_hash)

    def test_ordered_live_gates_with_fake_handlers(self) -> None:
        # Order: Bluesky+Mastodon -> X -> LinkedIn -> Meta (instagram/facebook_pages)
        order = [
            ("bluesky", None),
            ("mastodon", "mastodon.social"),
            ("x", None),
            ("linkedin", None),
            ("instagram", None),
            ("facebook_pages", None),
        ]
        due = []
        for idx, (platform, host) in enumerate(order):
            due.append(self._seed(project_id="app-1", platform=platform, plan_id=f"p{idx}", host=host))

        def fake(req: AdapterRequest) -> dict:
            return {
                "status": "ok",
                "ok": True,
                "mutated": True,
                "provider_id": f"{req.platform}-id",
                "provider_url": f"https://example.test/{req.platform}/{req.operation_key}",
            }

        handlers = {platform: fake for platform, _ in order}
        cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            cfg,
            due=due,
            now="2026-01-02T00:00:00Z",
            handlers=handlers,
        )
        self.assertTrue(out["mutated"])
        self.assertEqual(out["processed"], len(order))
        for idx, (platform, _) in enumerate(order):
            plan_status = self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", (f"p{idx}",)
            ).fetchone()["status"]
            self.assertEqual(plan_status, PlanStatus.SUCCEEDED.value, platform)
            attempt_status = self.repo.conn.execute(
                "SELECT status FROM publication_attempts WHERE plan_id=?", (f"p{idx}",)
            ).fetchone()["status"]
            self.assertEqual(attempt_status, AttemptStatus.SUCCEEDED.value, platform)

    def test_builder_project_can_publish_independently(self) -> None:
        due = [self._seed(project_id="builder-1", platform="bluesky", plan_id="builder-post")]

        def fake(req: AdapterRequest) -> dict:
            return {"status": "ok", "ok": True, "mutated": True, "provider_id": "b-1"}

        cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            cfg,
            due=due,
            now="2026-01-02T00:00:00Z",
            handlers={"bluesky": fake},
        )
        self.assertTrue(out["mutated"])
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT project_id FROM publication_attempts WHERE plan_id=?",
                ("builder-post",),
            ).fetchone()["project_id"],
            "builder-1",
        )

    def test_poll_quiz_or_this_or_that_is_silence_not_an_angle(self) -> None:
        polls = (
            "poll: dark mode or light",
            "this or that: CLI or TUI",
            "quiz: can you score a thin brief?",
            "ankieta o lokalnym ticku",
        )
        for idx, text in enumerate(polls):
            with self.subTest(text=text):
                self.assertTrue(looks_like_poll(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "poll",
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-poll-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "poll")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_shorts_without_loop_or_with_cta_and_loop_is_silence(self) -> None:
        missing = (
            "hook in 1-3s: brief in, draft out",
            "first 3s: picture plus voice plus text",
        )
        for idx, text in enumerate(missing):
            with self.subTest(text=text):
                self.assertFalse(has_fair_loop(text))
                self.assertEqual(fair_loop_reason(text), "fair_missing_loop")
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-noloop-{idx}",
                    facts=(
                        Fact(kind="hook", text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                )
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.SHORTS,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.SHORTS].wave,
                    canon_url=ARENAS[ArenaId.SHORTS].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.SHORTS, "\n".join((text, "hook"))),
                    (Verdict.KILL, "fair_missing_loop"),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        both = (
            "last frame into first, then subscribe",
            "rewatch the cut — link in bio",
            "ostatnia klatka w pierwszą i CTA",
        )
        for idx, text in enumerate(both):
            with self.subTest(text=text):
                self.assertTrue(has_fair_loop(text))
                self.assertTrue(looks_like_fair_cta(text))
                self.assertEqual(fair_loop_reason(text), "fair_cta_with_loop")
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-both-{idx}",
                    facts=(
                        Fact(kind="hook", text="hook in 1-3s: brief in, draft out", artifact_url=SHIP_PR),
                        Fact(text=text),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                )
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.SHORTS,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.SHORTS].wave,
                    canon_url=ARENAS[ArenaId.SHORTS].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.SHORTS, "\n".join(("hook", text))),
                    (Verdict.KILL, "fair_cta_with_loop"),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        looped = "last frame into first; rewatch is the signal"
        self.assertTrue(has_fair_loop(looped))
        self.assertFalse(looks_like_fair_cta(looped))
        self.assertIsNone(fair_loop_reason(looped))
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-loop",
            facts=(
                Fact(kind="hook", text="hook in 1-3s: brief in, draft out", artifact_url=SHIP_PR),
                Fact(text=looped),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        leaked = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.SHORTS,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.SHORTS].wave,
            canon_url=ARENAS[ArenaId.SHORTS].canon_url,
        )
        self.assertIsNone(_gate_violation(brief, ArenaId.SHORTS, "\n".join(("hook", looped))))
        draft = compose_draft(brief, leaked)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.SHORTS)
        self.assertIn("hook in 1-3s", draft.body)
        self.assertNotIn("subscribe", draft.body.lower())
        self.assertNotIn("cta", draft.body.lower())
        self.assertFalse(has_fair_loop("one loop per state.db"))
        self.assertFalse(has_fair_loop("event loop"))
        self.assertFalse(looks_like_fair_cta("follow the README to run the demo"))

    def test_court_is_not_a_launch_channel(self) -> None:
        launches = (
            "Show HN: local tick scores briefs",
            "we just shipped the operator",
            "właśnie wypuściliśmy lokalny tick",
        )
        for idx, text in enumerate(launches):
            with self.subTest(text=text):
                self.assertTrue(looks_like_court_launch(text))
                self.assertEqual(court_reason(text, claims_ship=False), COURT_NOT_A_LAUNCH_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-court-launch-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.LINKEDIN,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.LINKEDIN,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertNotEqual(score.arena, ArenaId.LINKEDIN)
                self.assertIn(score.arena, {ArenaId.HN, ArenaId.GITHUB, None})
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.LINKEDIN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.LINKEDIN].wave,
                    canon_url=ARENAS[ArenaId.LINKEDIN].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.LINKEDIN, text),
                    (Verdict.KILL, COURT_NOT_A_LAUNCH_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        dry = "Dry-run still default on every tick"
        self.assertFalse(looks_like_court_launch(dry))
        self.assertTrue(has_court_insight(dry))
        self.assertIsNone(court_reason(dry, claims_ship=False))
        self.assertEqual(court_reason(dry, claims_ship=True), COURT_NOT_A_LAUNCH_REASON)
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.LINKEDIN,
                claims_ship=False,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.LINKEDIN,
        )
        insight = Brief.create(
            project_id="app-1",
            brief_id="b-court-insight",
            facts=(
                Fact(text=dry),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.LINKEDIN,
        )
        self.assertIsNone(_gate_violation(insight, ArenaId.LINKEDIN, "\n".join((dry, "Local tick"))))
        score = score_brief(insight)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.LINKEDIN)
        draft = compose_draft(insight, score)
        assert draft is not None
        self.assertEqual(draft.costume, "court")
        self.assertFalse(draft.body.lower().startswith("show hn:"))
        self.assertNotIn("just shipped", draft.body.lower())
        empty = Brief.create(
            project_id="app-1",
            brief_id="b-court-empty",
            facts=(
                Fact(text="we just shipped the operator", artifact_url=SHIP_PR),
                Fact(text="Show HN: local tick scores briefs"),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.LINKEDIN,
        )
        score = score_brief(empty)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, COURT_NOT_A_LAUNCH_REASON)
        self.assertIsNone(compose_draft(empty, score))

    def test_empty_tavern_does_not_get_an_invite(self) -> None:
        empties = (
            "stand up a Discord",
            "public invite to the tavern",
            "help / show / contribute / lounge, no one here yet",
            "~10 builders, one channel",
        )
        for idx, text in enumerate(empties):
            with self.subTest(text=text):
                self.assertEqual(tavern_reason(text), EMPTY_TAVERN_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-empty-tavern-{idx}",
                    facts=(
                        Fact(text=text),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.DISCORD,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.DISCORD,
                        claims_ship=False,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.DISCORD,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, EMPTY_TAVERN_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.DISCORD,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.DISCORD].wave,
                    canon_url=ARENAS[ArenaId.DISCORD].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.DISCORD, text),
                    (Verdict.KILL, EMPTY_TAVERN_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        living = (
            "help / show / contribute / lounge",
            "seed about 10 builders before a public invite",
        )
        self.assertTrue(has_tavern_intent_split(living[0]))
        self.assertTrue(has_tavern_seed(living[1]))
        self.assertTrue(looks_like_tavern_invite(living[1]))
        self.assertIsNone(tavern_reason("\n".join(living)))
        self.assertFalse(has_tavern_intent_split("stand up a Discord"))
        self.assertFalse(has_tavern_seed("public invite to the tavern"))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-living-tavern",
            facts=(
                Fact(text=living[0]),
                Fact(text=living[1]),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.DISCORD,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.DISCORD, "\n".join(living)))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.DISCORD)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "tavern")
        self.assertIn("help", draft.body.lower())
        self.assertIn("lounge", draft.body.lower())
        self.assertIn("10 builders", draft.body.lower())


if __name__ == "__main__":
    unittest.main()
