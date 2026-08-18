from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from github_pack.pack import (
    README_WITHOUT_DEMO_REASON,
    README_WITHOUT_QUICKSTART_REASON,
    REVERTED_NOT_A_SHIP_REASON,
    SOLICIT_GESTURE_REASON,
    looks_like_solicit_gesture,
    pack_survey,
    readme_has_copyable_start,
    readme_has_visible_demo,
)
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
from github_feedback.feedback import collect_feedback, whole_thread_reason
from influenzer.brief_admit import open_story_reason
from influenzer.hom_feedback import SOURCE as FEEDBACK_SOURCE, admit_feedback
from influenzer.playbook import (
    ARENAS,
    ArenaId,
    AGORA_NO_NEW_THOUGHT_REASON,
    BLUESKY_PACK_WITHOUT_FEED_REASON,
    BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON,
    CINEMA_ANNOUNCES_END_REASON,
    CINEMA_MISSING_PACKAGE_REASON,
    COURT_NOT_A_LAUNCH_REASON,
    DEAD_STAR_COUNT_REASON,
    EMPTY_TAVERN_REASON,
    FAIR_MISSING_HOOK_REASON,
    LETTER_ASK_WITHOUT_GIFT_REASON,
    HN_CAMP_REASON,
    LETTER_WITHOUT_SURNAME_REASON,
    LIVING_STACK_REASON,
    REDDIT_NO_DISCLOSURE_REASON,
    REDDIT_NO_ROOM_REASON,
    PRESS_RELEASE_REASON,
    SECRET_REASON,
    SEMINAR_BRAND_VOICE_REASON,
    WORSE_CLONE_REASON,
    Verdict,
    agora_reason,
    cafe_artifact_reason,
    cafe_reason,
    choose_arena,
    has_parent_post,
    cinema_end_reason,
    cinema_package_reason,
    court_reason,
    fair_hook_reason,
    fair_loop_reason,
    has_agora_thought,
    has_cafe_feed,
    has_cafe_pack,
    has_cinema_package,
    has_court_insight,
    has_fair_hook,
    has_fair_loop,
    has_letter_gift,
    has_letter_surname,
    has_named_subreddit,
    has_reddit_repo,
    has_tavern_intent_split,
    has_tavern_seed,
    has_workshop_life,
    letter_reason,
    looks_like_agora_echo,
    looks_like_brand_voice,
    looks_like_cinema_end,
    looks_like_court_launch,
    looks_like_dead_star_count,
    looks_like_dead_star_story,
    looks_like_fair_cta,
    looks_like_letter_ask,
    looks_like_letter_crush,
    looks_like_letter_team_voice,
    looks_like_poll,
    looks_like_model_in_frame,
    looks_like_reddit_disclose,
    looks_like_secret,
    looks_like_seminar_first_person,
    looks_like_tavern_invite,
    looks_like_press_release,
    looks_like_event,
    looks_like_calendar_filler,
    looks_like_counter_thanks,
    looks_like_fog,
    looks_like_founder_journal,
    looks_like_lead_magnet,
    looks_like_fomo,
    looks_like_meme,
    looks_like_deck,
    looks_like_logo_reveal,
    looks_like_waitlist,
    looks_like_worse_clone,
    EVENT_NOT_A_SHIP,
    CALENDAR_FILLER_REASON,
    COUNTER_THANKS_REASON,
    FOG_REASON,
    FOUNDER_JOURNAL_REASON,
    LEAD_MAGNET_REASON,
    FOMO_REASON,
    MEME_REASON,
    DECK_REASON,
    LOGO_REVEAL_NOT_A_SHIP,
    reddit_reason,
    seminar_reason,
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

    def test_secret_token_or_key_is_silence_not_an_angle(self) -> None:
        auth = "Authorization" + ": " + "Bearer" + " " + "sk" + "-" + "this-is-not-a-live-key-1"
        leaks = (
            "docs mention env:INFLUENZER_TOKEN",
            auth,
            "paste " + "sk" + "-" + "this-is-not-a-live-key-1 into the demo",
            "ghp_" + "exampletokenvalue1",
            "docs mention keychain:service/account",
        )
        for idx, text in enumerate(leaks):
            with self.subTest(text=text):
                self.assertTrue(looks_like_secret(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    SECRET_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-secret-{idx}",
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
                self.assertEqual(score.reason, SECRET_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_waitlist_is_not_a_ship_on_hn_x_or_shorts(self) -> None:
        vapor = (
            "Coming soon",
            "join the list",
            "sign up to get access",
            "join the waitlist",
            "get early access",
            "request access",
        )
        self.assertFalse(looks_like_waitlist(""))
        self.assertFalse(looks_like_waitlist("   "))
        self.assertFalse(looks_like_waitlist("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_waitlist("as soon as you install, the local tick scores"))
        arenas = (ArenaId.HN, ArenaId.X, ArenaId.SHORTS)
        for text in vapor:
            with self.subTest(text=text):
                self.assertTrue(looks_like_waitlist(text))
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = Brief.create(
                        project_id="app-1",
                        brief_id=f"b-waitlist-{arena.value}-{text.split()[0].lower()}",
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                        story_kind="major",
                        claims_ship=True,
                        tryable=True,
                        preferred_arena=arena,
                    )
                    score = score_brief(brief)
                    self.assertEqual(score.verdict, Verdict.KILL)
                    self.assertEqual(score.reason, "waitlist_not_tryable")
                    self.assertIsNone(score.arena)
                    self.assertIsNone(compose_draft(brief, score))
                    leaked = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(compose_draft(brief, leaked))

        quiet = Brief.create(
            project_id="app-1",
            brief_id="b-waitlist-changelog",
            facts=(Fact(text="join the list", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "waitlist_not_tryable")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-waitlist-alive",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))

    def test_event_is_not_a_ship_on_hn_x_or_shorts(self) -> None:
        vapor = (
            "webinar Thursday",
            "join us Thursday",
            "meetup next week",
            "add it to the calendar",
            "wydarzenie w czwartek",
            "dołącz w czwartek",
        )
        self.assertFalse(looks_like_event(""))
        self.assertFalse(looks_like_event("   "))
        self.assertFalse(looks_like_event("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_event("as soon as you install, the local tick scores"))
        self.assertFalse(looks_like_event("calendar year 2026 on the README"))
        arenas = (ArenaId.HN, ArenaId.X, ArenaId.SHORTS)
        for idx, text in enumerate(vapor):
            with self.subTest(text=text):
                self.assertTrue(looks_like_event(text))
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = Brief.create(
                        project_id="app-1",
                        brief_id=f"b-event-{arena.value}-{idx}",
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                        story_kind="major",
                        claims_ship=True,
                        tryable=True,
                        preferred_arena=arena,
                    )
                    score = score_brief(brief)
                    self.assertEqual(score.verdict, Verdict.KILL)
                    self.assertEqual(score.reason, EVENT_NOT_A_SHIP)
                    self.assertIsNone(score.arena)
                    self.assertIsNone(compose_draft(brief, score))
                    leaked = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(compose_draft(brief, leaked))

        quiet = Brief.create(
            project_id="app-1",
            brief_id="b-event-changelog",
            facts=(Fact(text="join us Thursday", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, EVENT_NOT_A_SHIP)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-event-alive",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))

    def test_calendar_filler_is_silence_not_an_angle(self) -> None:
        greetings = (
            "happy Friday",
            "repo birthday",
            "urodziny repo",
            "wesołych świąt",
        )
        self.assertFalse(looks_like_calendar_filler(""))
        self.assertFalse(looks_like_calendar_filler("   "))
        self.assertFalse(looks_like_calendar_filler("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_calendar_filler("shipped Friday after the timeout fix"))
        self.assertFalse(looks_like_calendar_filler("calendar year 2026 on the README"))
        for idx, text in enumerate(greetings):
            with self.subTest(text=text):
                self.assertTrue(looks_like_calendar_filler(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    CALENDAR_FILLER_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-calendar-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, CALENDAR_FILLER_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_counter_thanks_is_silence_not_an_angle(self) -> None:
        greetings = (
            "thanks for 1000 stars",
            "milestone follow",
            "dziękujemy za gwiazdki",
            "podziękowanie za licznik",
        )
        self.assertFalse(looks_like_counter_thanks(""))
        self.assertFalse(looks_like_counter_thanks("   "))
        self.assertFalse(looks_like_counter_thanks("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_counter_thanks("thanks for the issue"))
        self.assertFalse(looks_like_counter_thanks("thanks for watching"))
        self.assertFalse(looks_like_counter_thanks("follow the README to run the demo"))
        for idx, text in enumerate(greetings):
            with self.subTest(text=text):
                self.assertTrue(looks_like_counter_thanks(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    COUNTER_THANKS_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-counter-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, COUNTER_THANKS_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_fog_is_silence_not_an_angle(self) -> None:
        hints = (
            "subtweet about the local tick",
            "you know who still scores remotely",
            "aluzja bez artefaktu",
            "mgła",
        )
        self.assertFalse(looks_like_fog(""))
        self.assertFalse(looks_like_fog("   "))
        self.assertFalse(looks_like_fog("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_fog("Unlike Loki, this scores briefs locally"))
        self.assertFalse(looks_like_fog("you know the timeout bug"))
        self.assertFalse(looks_like_fog("we name the difference"))
        for idx, text in enumerate(hints):
            with self.subTest(text=text):
                self.assertTrue(looks_like_fog(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    FOG_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-fog-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, FOG_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_founder_journal_is_silence_not_an_angle(self) -> None:
        lifestyle = (
            "desk setup for the local tick",
            "tools I use to score briefs",
            "day in the life of a local tick",
            "morning routine before the demo",
            "dziennik założyciela",
        )
        self.assertFalse(looks_like_founder_journal(""))
        self.assertFalse(looks_like_founder_journal("   "))
        self.assertFalse(looks_like_founder_journal("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_founder_journal("this morning we shipped the local tick"))
        self.assertFalse(looks_like_founder_journal("setup.py installs the CLI"))
        self.assertFalse(looks_like_founder_journal("we use the local tick to score briefs"))
        for idx, text in enumerate(lifestyle):
            with self.subTest(text=text):
                self.assertTrue(looks_like_founder_journal(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    FOUNDER_JOURNAL_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-journal-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, FOUNDER_JOURNAL_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_lead_magnet_is_silence_not_an_angle(self) -> None:
        magnets = (
            "ebook for the local tick",
            "free guide to scoring briefs",
            "typeform for an email",
            "download the free pdf",
            "ebook za maila",
        )
        self.assertFalse(looks_like_lead_magnet(""))
        self.assertFalse(looks_like_lead_magnet("   "))
        self.assertFalse(looks_like_lead_magnet("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_lead_magnet("user guide for the local tick"))
        self.assertFalse(looks_like_lead_magnet("email notifications stay local"))
        self.assertFalse(looks_like_lead_magnet("join the waitlist"))
        for idx, text in enumerate(magnets):
            with self.subTest(text=text):
                self.assertTrue(looks_like_lead_magnet(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    LEAD_MAGNET_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-magnet-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, LEAD_MAGNET_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_fomo_is_silence_not_an_angle(self) -> None:
        pressure = (
            "only 5 spots for the local tick",
            "countdown to the launch",
            "last chance to try the local tick",
            "tylko 3 miejsca",
            "ostatnia szansa",
        )
        self.assertFalse(looks_like_fomo(""))
        self.assertFalse(looks_like_fomo("   "))
        self.assertFalse(looks_like_fomo("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_fomo("join the waitlist"))
        self.assertFalse(looks_like_fomo("like if this local tick helped"))
        self.assertFalse(looks_like_fomo("parking spots near the office"))
        for idx, text in enumerate(pressure):
            with self.subTest(text=text):
                self.assertTrue(looks_like_fomo(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    FOMO_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-fomo-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, FOMO_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_meme_is_silence_not_an_angle(self) -> None:
        pictures = (
            "drake meme for the local tick",
            "wojak of the local tick",
            "reaction image without a demo",
            "tablica z memami",
            "ściana memów",
        )
        self.assertFalse(looks_like_meme(""))
        self.assertFalse(looks_like_meme("   "))
        self.assertFalse(looks_like_meme("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_meme("remember the timeout fix"))
        self.assertFalse(looks_like_meme("screenshot of the local tick demo"))
        self.assertFalse(looks_like_meme("join the waitlist"))
        for idx, text in enumerate(pictures):
            with self.subTest(text=text):
                self.assertTrue(looks_like_meme(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    MEME_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-meme-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, MEME_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_deck_is_silence_not_an_artifact(self) -> None:
        decks = (
            "pitch deck for the local tick",
            "PDF of the slides",
            "Notion one-pager",
            "slajdy bez produktu",
            "our pitch for investors",
        )
        self.assertFalse(looks_like_deck(""))
        self.assertFalse(looks_like_deck("   "))
        self.assertFalse(looks_like_deck("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_deck("on deck for the next ship"))
        self.assertFalse(looks_like_deck("screenshot of the local tick demo"))
        self.assertFalse(looks_like_deck("join the waitlist"))
        for idx, text in enumerate(decks):
            with self.subTest(text=text):
                self.assertTrue(looks_like_deck(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    DECK_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-deck-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, DECK_REASON)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

    def test_logo_reveal_is_silence_not_a_ship(self) -> None:
        looks = (
            "rebrand of the local tick",
            "new palette for the local tick",
            "moodboard for the launch",
            "logo reveal this week",
            "odsłona logo",
        )
        self.assertFalse(looks_like_logo_reveal(""))
        self.assertFalse(looks_like_logo_reveal("   "))
        self.assertFalse(looks_like_logo_reveal("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_logo_reveal("logo intro then the demo"))
        self.assertFalse(looks_like_logo_reveal("outro-logo"))
        self.assertFalse(looks_like_logo_reveal("![logo](docs/logo.png)"))
        arenas = (ArenaId.HN, ArenaId.X, ArenaId.SHORTS)
        for idx, text in enumerate(looks):
            with self.subTest(text=text):
                self.assertTrue(looks_like_logo_reveal(text))
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = Brief.create(
                        project_id="app-1",
                        brief_id=f"b-logo-{arena.value}-{idx}",
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                        story_kind="major",
                        claims_ship=True,
                        tryable=True,
                        preferred_arena=arena,
                    )
                    score = score_brief(brief)
                    self.assertEqual(score.verdict, Verdict.KILL)
                    self.assertEqual(score.reason, LOGO_REVEAL_NOT_A_SHIP)
                    self.assertIsNone(score.arena)
                    self.assertIsNone(compose_draft(brief, score))
                    leaked = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(compose_draft(brief, leaked))

        quiet = Brief.create(
            project_id="app-1",
            brief_id="b-logo-changelog",
            facts=(Fact(text="rebrand of the local tick", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, LOGO_REVEAL_NOT_A_SHIP)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-logo-alive",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))

    def test_press_release_tone_is_changelog_or_silence_not_an_angle(self) -> None:
        phrases = (
            "we're excited",
            "we are excited",
            "product announcement",
            "unveiling our new tool",
            "delighted to share",
            "we are delighted to share",
            "proud to announce",
            "pleased to announce",
        )
        self.assertFalse(looks_like_press_release(""))
        self.assertFalse(looks_like_press_release("   "))
        self.assertFalse(looks_like_press_release("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_press_release("I built a local tick and struggled with the score"))
        arenas = (ArenaId.HN, ArenaId.GITHUB, ArenaId.X)
        for idx, text in enumerate(phrases):
            with self.subTest(text=text):
                self.assertTrue(looks_like_press_release(text))
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = Brief.create(
                        project_id="app-1",
                        brief_id=f"b-pr-{arena.value}-{idx}",
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                        story_kind="major",
                        claims_ship=True,
                        tryable=True,
                        preferred_arena=arena,
                    )
                    score = score_brief(brief)
                    self.assertEqual(score.verdict, Verdict.KILL)
                    self.assertEqual(score.reason, PRESS_RELEASE_REASON)
                    self.assertIsNone(score.arena)
                    self.assertIsNone(compose_draft(brief, score))
                    leaked = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(compose_draft(brief, leaked))

        quiet = Brief.create(
            project_id="app-1",
            brief_id="b-pr-changelog",
            facts=(Fact(text="delighted to share", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, PRESS_RELEASE_REASON)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-pr-alive",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertNotIn("delighted to share", draft.body.lower())
        self.assertNotIn("we're excited", draft.body.lower())

    def test_worse_clone_is_changelog_or_silence_not_an_angle(self) -> None:
        clones = (
            "someone already did this better",
            "we reinvented X",
            "znowu wymyśliliśmy X",
            "gorszy klon Loki",
            "just another clone of Loki",
        )
        self.assertFalse(looks_like_worse_clone(""))
        self.assertFalse(looks_like_worse_clone("   "))
        self.assertFalse(looks_like_worse_clone("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_worse_clone("Loki is the predecessor; the difference is a local tick"))
        self.assertFalse(looks_like_worse_clone("Loki is worth helping with a local tick"))
        arenas = (ArenaId.HN, ArenaId.X, ArenaId.SHORTS)
        for text in clones:
            with self.subTest(text=text):
                self.assertTrue(looks_like_worse_clone(text))
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = Brief.create(
                        project_id="app-1",
                        brief_id=f"b-clone-{arena.value}-{text.split()[0].lower()}",
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                        story_kind="major",
                        claims_ship=True,
                        tryable=True,
                        preferred_arena=arena,
                    )
                    score = score_brief(brief)
                    self.assertEqual(score.verdict, Verdict.KILL)
                    self.assertEqual(score.reason, WORSE_CLONE_REASON)
                    self.assertIsNone(score.arena)
                    self.assertIsNone(compose_draft(brief, score))
                    leaked = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(compose_draft(brief, leaked))

        quiet = Brief.create(
            project_id="app-1",
            brief_id="b-clone-changelog",
            facts=(Fact(text="someone already did this better", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, WORSE_CLONE_REASON)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

        better = Brief.create(
            project_id="app-1",
            brief_id="b-clone-better",
            facts=(
                Fact(text="Loki is the predecessor; the difference is a local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(better)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(better, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertIn("Loki", draft.body)

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

    def test_prompt_dump_or_i_asked_chatgpt_is_silence_not_an_angle(self) -> None:
        dumps = (
            "I asked ChatGPT how to score a brief",
            "as an AI I would ship the local tick",
            "here's the prompt I used for the launch",
            "zrzut rozmowy z modelem",
        )
        for idx, text in enumerate(dumps):
            with self.subTest(text=text):
                self.assertTrue(looks_like_model_in_frame(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "model_in_frame",
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-model-{idx}",
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
                self.assertEqual(score.reason, "model_in_frame")
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
            "last frame into first, thanks for watching",
            "rewatch the cut — outro-logo",
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
                    _gate_violation(
                        brief,
                        ArenaId.SHORTS,
                        "\n".join(("hook in 1-3s: brief in, draft out", text)),
                    ),
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
        self.assertIsNone(
            _gate_violation(
                brief,
                ArenaId.SHORTS,
                "\n".join(("hook in 1-3s: brief in, draft out", looped)),
            )
        )
        draft = compose_draft(brief, leaked)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.SHORTS)
        self.assertIn("hook in 1-3s", draft.body)
        self.assertNotIn("subscribe", draft.body.lower())
        self.assertNotIn("cta", draft.body.lower())
        self.assertFalse(has_fair_loop("one loop per state.db"))
        self.assertFalse(has_fair_loop("event loop"))
        self.assertFalse(looks_like_fair_cta("follow the README to run the demo"))

    def test_shorts_without_hook_or_youtube_cut_is_silence(self) -> None:
        looped = "last frame into first; rewatch is the signal"
        missing = (
            "hook",
            "logo intro then the demo",
            "hey, watch this local tick",
            "title plus thumb in 0.5s: one-angle operator tick",
        )
        for idx, text in enumerate(missing):
            with self.subTest(text=text):
                self.assertFalse(has_fair_hook(text))
                self.assertEqual(fair_hook_reason(text), FAIR_MISSING_HOOK_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-nohook-{idx}",
                    facts=(
                        Fact(kind="hook", text=text, artifact_url=SHIP_PR),
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
                self.assertEqual(
                    _gate_violation(brief, ArenaId.SHORTS, "\n".join((text, looped))),
                    (Verdict.KILL, FAIR_MISSING_HOOK_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))
                cinema = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.YOUTUBE,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
                    canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
                )
                if has_cinema_package(text):
                    self.assertIsNone(
                        _gate_violation(brief, ArenaId.YOUTUBE, "\n".join((text, looped)))
                    )
                    cinema_draft = compose_draft(brief, cinema)
                    assert cinema_draft is not None
                    self.assertEqual(cinema_draft.arena, ArenaId.YOUTUBE)
                    self.assertNotEqual(cinema_draft.costume, "fair")

        hooked = "hook in 1-3s: picture plus voice plus text"
        self.assertTrue(has_fair_hook(hooked))
        self.assertTrue(has_fair_hook("first 3s: obraz+g\u0142os+tekst"))
        self.assertFalse(has_fair_hook("event loop"))
        self.assertFalse(has_fair_hook("first frame into last"))
        self.assertIsNone(fair_hook_reason(hooked))
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-hook",
            facts=(
                Fact(kind="hook", text=hooked, artifact_url=SHIP_PR),
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
        self.assertIsNone(_gate_violation(brief, ArenaId.SHORTS, "\n".join((hooked, looped))))
        draft = compose_draft(brief, leaked)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.SHORTS)
        self.assertIn("1-3s", draft.body)
        self.assertNotIn("0.5s", draft.body)
        self.assertIsNone(compose_draft(brief, Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.YOUTUBE,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
            canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
        )))

    def test_youtube_without_title_promise_pair_is_silence(self) -> None:
        missing = (
            "package",
            "title",
            "hey guys watch this local tick",
            "poster of the operator tick",
            "hook in 1-3s: picture plus voice plus text",
        )
        demo = "strangers can click and run the demo today"
        for idx, text in enumerate(missing):
            with self.subTest(text=text):
                self.assertFalse(has_cinema_package(text))
                self.assertEqual(cinema_package_reason(text), CINEMA_MISSING_PACKAGE_REASON)
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.YOUTUBE,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.YOUTUBE,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-cinema-nopair-{idx}",
                    facts=(
                        Fact(kind="package", text=text, artifact_url=SHIP_PR),
                        Fact(text=demo),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.YOUTUBE,
                )
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.YOUTUBE,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
                    canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, CINEMA_MISSING_PACKAGE_REASON)
                self.assertIsNone(score.arena)
                self.assertEqual(
                    _gate_violation(brief, ArenaId.YOUTUBE, "\n".join((text, demo))),
                    (Verdict.KILL, CINEMA_MISSING_PACKAGE_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        packaged = "title plus thumb in 0.5s: one-angle operator tick"
        self.assertTrue(has_cinema_package(packaged))
        self.assertTrue(has_cinema_package("tytu\u0142+obietnica w 0.5s"))
        self.assertTrue(has_cinema_package("one message in 0.5s"))
        self.assertFalse(has_cinema_package("event loop"))
        self.assertFalse(has_cinema_package("first 3s: obraz+g\u0142os+tekst"))
        self.assertIsNone(cinema_package_reason(packaged))
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-cinema-pair",
            facts=(
                Fact(kind="package", text=packaged, artifact_url=SHIP_PR),
                Fact(text=demo),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.YOUTUBE,
        )
        self.assertIsNone(_gate_violation(brief, ArenaId.YOUTUBE, "\n".join((packaged, demo))))
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.YOUTUBE)
        draft = compose_draft(brief, score)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.YOUTUBE)
        self.assertEqual(draft.costume, "cinema")
        self.assertIn("0.5s", draft.body)
        self.assertNotIn("hey guys", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

        self.assertEqual(
            choose_arena(
                claims_ship=True,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.HN,
        )
        no_pref = Brief.create(
            project_id="app-1",
            brief_id="b-cinema-falls-to-hn",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text=demo),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        no_pref_score = score_brief(no_pref)
        self.assertEqual(no_pref_score.verdict, Verdict.DRAFT)
        self.assertEqual(no_pref_score.arena, ArenaId.HN)
        self.assertNotEqual(no_pref_score.arena, ArenaId.YOUTUBE)
        no_pref_draft = compose_draft(no_pref, no_pref_score)
        assert no_pref_draft is not None
        self.assertEqual(no_pref_draft.costume, "seminar")
        self.assertNotEqual(no_pref_draft.costume, "cinema")

    def test_cinema_end_does_not_announce_the_end(self) -> None:
        package = "title plus thumb in 0.5s: one-angle operator tick"
        endings = (
            "thanks for watching",
            "like and subscribe",
            "outro-logo",
            "dzi\u0119kuj\u0119 za ogl\u0105danie",
        )
        for idx, text in enumerate(endings):
            with self.subTest(text=text):
                self.assertTrue(looks_like_cinema_end(text))
                self.assertEqual(cinema_end_reason(text), CINEMA_ANNOUNCES_END_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-cinema-end-{idx}",
                    facts=(
                        Fact(kind="package", text=package, artifact_url=SHIP_PR),
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
                    arena=ArenaId.YOUTUBE,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
                    canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.YOUTUBE, "\n".join((package, text))),
                    (Verdict.KILL, CINEMA_ANNOUNCES_END_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        one_cta = "open the working demo after the cut"
        self.assertFalse(looks_like_cinema_end(one_cta))
        self.assertFalse(looks_like_cinema_end(package))
        self.assertIsNone(cinema_end_reason("\n".join((package, one_cta))))
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-cinema-one-cta",
            facts=(
                Fact(kind="package", text=package, artifact_url=SHIP_PR),
                Fact(text=one_cta),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        leaked = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.YOUTUBE,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
            canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
        )
        self.assertIsNone(_gate_violation(brief, ArenaId.YOUTUBE, "\n".join((package, one_cta))))
        draft = compose_draft(brief, leaked)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.YOUTUBE)
        self.assertEqual(draft.costume, "cinema")
        self.assertIn("0.5s", draft.body)
        self.assertNotIn("thanks for watching", draft.body.lower())
        self.assertNotIn("subscribe", draft.body.lower())
        self.assertNotIn("outro", draft.body.lower())
        self.assertFalse(looks_like_cinema_end("follow the README to run the demo"))
        self.assertFalse(looks_like_fair_cta(one_cta))

        both = "last frame into first, then subscribe"
        self.assertTrue(has_fair_loop(both))
        self.assertTrue(looks_like_fair_cta(both))
        self.assertEqual(fair_loop_reason(both), "fair_cta_with_loop")
        looped_ask = Brief.create(
            project_id="app-1",
            brief_id="b-cinema-loop-cta",
            facts=(
                Fact(kind="package", text=package, artifact_url=SHIP_PR),
                Fact(text=both),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        leaked_both = Score(
            brief_id=looped_ask.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.YOUTUBE,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.YOUTUBE].wave,
            canon_url=ARENAS[ArenaId.YOUTUBE].canon_url,
        )
        self.assertEqual(
            _gate_violation(looped_ask, ArenaId.YOUTUBE, "\n".join((package, both))),
            (Verdict.KILL, "fair_cta_with_loop"),
        )
        self.assertIsNone(compose_draft(looped_ask, leaked_both))

    def test_x_reply_without_a_new_thought_is_silence(self) -> None:
        parent = "https://x.com/mikolaj92/status/123456789"
        parent_text = "Show HN about mikolaj92/influenzer"
        empties = (
            (
                Fact(kind="parent", text=parent_text, artifact_url=parent),
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
            ),
            (
                Fact(kind="parent", text=parent_text, artifact_url=parent),
                Fact(text=parent_text, artifact_url=SHIP_PR),
            ),
            (
                Fact(kind="parent", text=parent_text, artifact_url=parent),
                Fact(text=parent, artifact_url=SHIP_PR),
            ),
        )
        self.assertFalse(has_agora_thought(""))
        self.assertFalse(has_agora_thought(parent))
        self.assertTrue(has_agora_thought(parent_text))
        self.assertTrue(looks_like_agora_echo(parent_text, parent_text))
        self.assertTrue(looks_like_agora_echo("mikolaj92/influenzer", parent_text))
        self.assertFalse(
            looks_like_agora_echo(
                "Local tick scores briefs and emits a draft", parent_text
            )
        )
        for idx, extra in enumerate(empties):
            with self.subTest(idx=idx):
                triples = tuple(
                    (fact.kind, fact.text, fact.artifact_url) for fact in extra
                )
                self.assertEqual(agora_reason(triples), AGORA_NO_NEW_THOUGHT_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-agora-echo-{idx}",
                    facts=extra,
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.X,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.X,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                        parent_post=True,
                    ),
                    ArenaId.X,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, AGORA_NO_NEW_THOUGHT_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.X,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.X].wave,
                    canon_url=ARENAS[ArenaId.X].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.X, "\n".join(fact.text for fact in brief.facts)),
                    (Verdict.KILL, AGORA_NO_NEW_THOUGHT_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        thought = "Local tick scores briefs and emits a draft"
        living = (
            Fact(kind="parent", text=parent_text, artifact_url=parent),
            Fact(text=thought, artifact_url=SHIP_PR),
            Fact(text="strangers can click and run the demo today"),
        )
        self.assertIsNone(
            agora_reason(tuple((fact.kind, fact.text, fact.artifact_url) for fact in living))
        )
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-agora-thought",
            facts=living,
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.X,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.X, "\n".join(fact.text for fact in living)))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.X)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "agora")
        self.assertIn(thought, draft.body)
        self.assertNotIn(parent_text, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_x_without_a_parent_url_is_not_an_empty_feed_original(self) -> None:
        self.assertFalse(has_parent_post((("signal", "local tick scores briefs", SHIP_PR),)))
        self.assertTrue(
            has_parent_post(
                (("parent", "Show HN about mikolaj92/influenzer", "https://x.com/m/status/1"),)
            )
        )
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.X,
                claims_ship=True,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.HN,
        )
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-x-empty-feed",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.X,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertNotEqual(score.arena, ArenaId.X)
        leaked = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.X,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.X].wave,
            canon_url=ARENAS[ArenaId.X].canon_url,
        )
        self.assertEqual(
            _gate_violation(brief, ArenaId.X, "\n".join(fact.text for fact in brief.facts)),
            (Verdict.KILL, "x_empty_feed"),
        )
        self.assertIsNone(compose_draft(brief, leaked))

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

    def test_linkedin_fold_is_insight_not_pitch_cta_or_url(self) -> None:
        stalls = (
            "we're launching the operator today",
            "we’re launching the operator today",
            "Learn more in the comments",
            "https://example.com/launch",
        )
        leaked = Score(
            brief_id="b-court-fold-stall",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.LINKEDIN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.LINKEDIN].wave,
            canon_url=ARENAS[ArenaId.LINKEDIN].canon_url,
        )
        for idx, text in enumerate(stalls):
            with self.subTest(text=text):
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-court-fold-stall-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text=text),
                    ),
                    story_kind="major",
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.LINKEDIN,
                )
                self.assertIsNone(compose_draft(brief, leaked))

        insight = "Dry-run still default on every tick"
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-court-fold-insight",
            facts=(
                Fact(text="we're launching the operator today"),
                Fact(text=insight, artifact_url=SHIP_PR),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.LINKEDIN,
        )
        draft = compose_draft(alive, leaked)
        assert draft is not None
        self.assertEqual(draft.costume, "court")
        fold = draft.body.split("\n\n", 1)[0]
        self.assertEqual(fold, insight)
        self.assertLessEqual(len(fold), 210)
        self.assertNotIn("http", fold.lower())
        self.assertNotIn("launching", fold.lower())
        self.assertNotIn("learn more", fold.lower())
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_parish_does_not_get_the_x_punchline(self) -> None:
        punchline = "Local tick scores briefs and emits a draft"
        clips = (
            (punchline,),
            (punchline, "Local tick scores briefs"),
            (punchline, punchline),
        )
        leaked = Score(
            brief_id="b-parish-punchline",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.MASTODON,
            angle="I struggled with X",
            wave_checklist=ARENAS[ArenaId.MASTODON].wave,
            canon_url=ARENAS[ArenaId.MASTODON].canon_url,
        )
        for idx, texts in enumerate(clips):
            with self.subTest(texts=texts):
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-parish-punchline-{idx}",
                    facts=tuple(
                        Fact(text=text, artifact_url=SHIP_PR if pos == 0 else None)
                        for pos, text in enumerate(texts)
                    ),
                    story_kind="hard_issue",
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.MASTODON,
                )
                self.assertIsNone(compose_draft(brief, leaked))

        talk = "The dry-run still sat with us on every tick"
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-parish-talk",
            facts=(
                Fact(text=punchline, artifact_url=SHIP_PR),
                Fact(text=talk),
            ),
            story_kind="hard_issue",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.MASTODON,
        )
        draft = compose_draft(alive, leaked)
        assert draft is not None
        self.assertEqual(draft.costume, "parish")
        self.assertEqual(draft.body, talk)
        self.assertNotEqual(draft.body, punchline)
        self.assertNotIn(punchline, draft.body)
        self.assertNotIn("Costume:", draft.body)

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

    def test_durable_qa_does_not_go_to_discord_search(self) -> None:
        # #52: how-to / bug / decision lives on GitHub (issue/Discussions).
        # Score does not pick Discord for hard_issue. Tavern is merge/celebration.
        living = (
            "help / show / contribute / lounge",
            "seed about 10 builders before a public invite",
        )
        questions = (
            "How do I install this when uv is missing?",
            "how-to: wire the operator tick",
            "bug: timeouts look like success",
            "decyzja: durable Q&A stays on GitHub Discussions",
        )
        for idx, text in enumerate(questions):
            with self.subTest(text=text):
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-durable-qa-{idx}",
                    facts=(
                        Fact(text=text),
                        Fact(text=living[0]),
                        Fact(text=living[1]),
                    ),
                    story_kind="hard_issue",
                    claims_ship=False,
                    tryable=False,
                    preferred_arena=ArenaId.DISCORD,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.DISCORD,
                        claims_ship=False,
                        tryable=False,
                        story_kind="hard_issue",
                        clickable=False,
                    ),
                    ArenaId.DISCORD,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, EMPTY_TAVERN_REASON)
                self.assertNotEqual(score.arena, ArenaId.DISCORD)
                self.assertIn(score.arena, {ArenaId.GITHUB, None})
                self.assertIsNone(compose_draft(brief, score))
                self.assertEqual(
                    _gate_violation(brief, ArenaId.DISCORD, "\n".join((text, *living))),
                    (Verdict.KILL, EMPTY_TAVERN_REASON),
                )

        decision = Brief.create(
            project_id="app-1",
            brief_id="b-durable-qa-decision",
            facts=(
                Fact(text="decyzja: durable Q&A stays on GitHub Discussions"),
                Fact(text=living[0]),
                Fact(text=living[1]),
            ),
            story_kind="decision",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.DISCORD,
        )
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.DISCORD,
                claims_ship=False,
                tryable=True,
                story_kind="decision",
                clickable=True,
            ),
            ArenaId.GITHUB,
        )
        decision_score = score_brief(decision)
        self.assertEqual(decision_score.verdict, Verdict.DRAFT)
        self.assertEqual(decision_score.arena, ArenaId.GITHUB)
        self.assertNotEqual(decision_score.arena, ArenaId.DISCORD)
        decision_draft = compose_draft(decision, decision_score)
        assert decision_draft is not None
        self.assertEqual(decision_draft.costume, "workshop")
        self.assertNotEqual(decision_draft.costume, "tavern")
        self.assertIn("Discussions", decision_draft.body)
        self.assertNotIn("Costume:", decision_draft.body)
        self.assertEqual(
            _gate_violation(decision, ArenaId.DISCORD, "\n".join(("decyzja", *living))),
            (Verdict.KILL, EMPTY_TAVERN_REASON),
        )

        workshop = Brief.create(
            project_id="app-1",
            brief_id="b-durable-qa-github",
            facts=(
                Fact(text="I struggled with timeouts looking like success"),
                Fact(text="unknown plus reconcile is the rule now"),
            ),
            story_kind="hard_issue",
            claims_ship=False,
            tryable=False,
        )
        score = score_brief(workshop)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.GITHUB)
        draft = compose_draft(workshop, score)
        assert draft is not None
        self.assertEqual(draft.costume, "workshop")
        self.assertIn("I struggled with timeouts", draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_launch_window_issue_is_one_feedback_fact_not_a_second_bag(self) -> None:
        from github_survey import GhCall
        from tests.gh_scripts import ISSUE, NOW, REPO, ScriptedGh, feedback_noise_script, gh_issue

        script = feedback_noise_script()
        script["issues"] = GhCall(
            0,
            json.dumps(
                [
                    gh_issue(
                        html_url=ISSUE,
                        title="How do I install this when uv is missing?",
                        body="The Windows install fails with a traceback",
                    )
                ]
            ),
        )
        packed = collect_feedback(REPO, gh=ScriptedGh(script), now=NOW)
        self.assertEqual(packed["status"], "ok")
        self.assertEqual(packed["source"], FEEDBACK_SOURCE)
        self.assertEqual(packed["story_kind"], "hard_issue")
        self.assertFalse(packed["claims_ship"])
        self.assertFalse(packed["tryable"])
        self.assertIsNone(whole_thread_reason(packed))
        self.assertTrue(
            any(item["kind"] == "excerpt" and item["artifact_url"] == ISSUE for item in packed["facts"])
        )
        admitted = admit_feedback(self.repo, packed, project_id="app-1", now=NOW)
        self.assertEqual(admitted["status"], "ok")
        self.assertEqual(admitted["source"], FEEDBACK_SOURCE)
        self.assertFalse(admitted["published"])
        stored = self.repo.get_brief("app-1", admitted["brief_id"])
        assert stored is not None
        self.assertEqual(stored.source, FEEDBACK_SOURCE)
        self.assertTrue(any(fact.kind == "excerpt" and fact.artifact_url == ISSUE for fact in stored.facts))
        self.assertEqual(len(self.repo.list_pending_briefs("app-1")), 1)

    def test_decision_does_not_sit_on_discord(self) -> None:
        # #38: story_kind=decision → warsztat (GitHub), nigdy tawerna.
        # Discord celebruje merge, nie uchwałę. Not live. One story.
        living = (
            "help / show / contribute / lounge",
            "seed about 10 builders before a public invite",
        )
        uchwala = "we chose SQLite over a hosted store so the operator stays local"
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.DISCORD,
                claims_ship=False,
                tryable=True,
                story_kind="decision",
                clickable=True,
            ),
            ArenaId.GITHUB,
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
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-decision-not-tavern",
            facts=(
                Fact(text=uchwala, artifact_url=SHIP_PR),
                Fact(text=living[0]),
                Fact(text=living[1]),
            ),
            story_kind="decision",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.DISCORD,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.GITHUB)
        self.assertNotEqual(score.arena, ArenaId.DISCORD)
        self.assertEqual(
            _gate_violation(brief, ArenaId.DISCORD, "\n".join((uchwala, *living))),
            (Verdict.KILL, EMPTY_TAVERN_REASON),
        )
        draft = compose_draft(brief, score)
        assert draft is not None
        self.assertEqual(draft.costume, "workshop")
        self.assertNotEqual(draft.costume, "tavern")
        self.assertIn("SQLite", draft.body)
        self.assertNotIn("Costume:", draft.body)

        no_pref = Brief.create(
            project_id="app-1",
            brief_id="b-decision-falls-to-github",
            facts=(
                Fact(text=uchwala, artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="decision",
            claims_ship=False,
            tryable=True,
        )
        no_pref_score = score_brief(no_pref)
        self.assertEqual(no_pref_score.verdict, Verdict.DRAFT)
        self.assertEqual(no_pref_score.arena, ArenaId.GITHUB)
        self.assertNotEqual(no_pref_score.arena, ArenaId.DISCORD)
        no_pref_draft = compose_draft(no_pref, no_pref_score)
        assert no_pref_draft is not None
        self.assertEqual(no_pref_draft.costume, "workshop")
        self.assertNotEqual(no_pref_draft.costume, "tavern")
        self.assertNotIn("Costume:", no_pref_draft.body)

    def test_bluesky_without_artifact_url_is_silence(self) -> None:
        living = (
            "starter pack of 30 active accounts in the local-first niche",
            "two custom feeds retain the same people",
        )
        almost = (
            None,
            "https://example.com/demo",
            "https://bsky.app/profile/did:plc:demo/post/1",
            "https://github.com/mikolaj92/influenzer/commit/abc",
        )
        for idx, url in enumerate(almost):
            with self.subTest(url=url):
                self.assertEqual(
                    cafe_artifact_reason((url,) if url else ()),
                    BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-empty-cafe-artifact-{idx}",
                    facts=(
                        Fact(text="vibe posting about the operator", artifact_url=url),
                        Fact(text=living[0]),
                        Fact(text=living[1]),
                    ),
                    story_kind="major",
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.BLUESKY,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.BLUESKY,
                        claims_ship=False,
                        tryable=True,
                        story_kind="major",
                        clickable=bool(url),
                    ),
                    ArenaId.BLUESKY,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.BLUESKY,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.BLUESKY].wave,
                    canon_url=ARENAS[ArenaId.BLUESKY].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.BLUESKY, "\n".join((url or "", *living))),
                    (Verdict.KILL, BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        self.assertIsNone(cafe_artifact_reason((SHIP_PR,)))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-living-cafe-artifact",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text=living[0]),
                Fact(text=living[1]),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.BLUESKY,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.BLUESKY, "\n".join((SHIP_PR, *living))))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.BLUESKY)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "newer cafe")
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_bluesky_without_pack_and_feed_is_silence(self) -> None:
        empties = (
            "vibe posting about the operator",
            "Released v1.2 with a tryable demo",
            "starter pack of 30 active accounts, no feed yet",
            "custom feed for local-first tools, no pack",
            "GitHub pack lists are the map",
            "do not flood originals into an empty feed",
        )
        for idx, text in enumerate(empties):
            with self.subTest(text=text):
                self.assertEqual(cafe_reason(text), BLUESKY_PACK_WITHOUT_FEED_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-empty-cafe-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.BLUESKY,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.BLUESKY,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.BLUESKY,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, BLUESKY_PACK_WITHOUT_FEED_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.BLUESKY,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.BLUESKY].wave,
                    canon_url=ARENAS[ArenaId.BLUESKY].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.BLUESKY, f"{text}\n{SHIP_PR}"),
                    (Verdict.KILL, BLUESKY_PACK_WITHOUT_FEED_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        living = (
            "starter pack of 30 active accounts in the local-first niche",
            "two custom feeds retain the same people",
        )
        self.assertTrue(has_cafe_pack(living[0]))
        self.assertTrue(has_cafe_feed(living[1]))
        self.assertIsNone(cafe_reason("\n".join(living)))
        self.assertFalse(has_cafe_pack("GitHub pack lists are the map"))
        self.assertFalse(has_cafe_feed("do not flood originals into an empty feed"))
        self.assertFalse(has_cafe_pack("title plus thumb in 0.5s: one-angle operator tick"))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-living-cafe",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text=living[0]),
                Fact(text=living[1]),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.BLUESKY,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.BLUESKY, "\n".join((SHIP_PR, *living))))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.BLUESKY)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "newer cafe")
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_dead_star_count_is_changelog_not_a_launch(self) -> None:
        corpses = (
            "N stars",
            "5k\u2605",
            "we hit 1200 stars",
            "star ranking without installs",
            "martwe gwiazdki",
        )
        for idx, text in enumerate(corpses):
            with self.subTest(text=text):
                self.assertTrue(looks_like_dead_star_count(text))
                self.assertTrue(looks_like_dead_star_story((text,)))
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-dead-stars-{idx}",
                    facts=(
                        Fact(text=text),
                        Fact(text="README has an install/quickstart a stranger can run"),
                    ),
                    story_kind="major",
                    claims_ship=False,
                    tryable=False,
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
                self.assertEqual(score.reason, DEAD_STAR_COUNT_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))
                self.assertIsNone(compose_draft(brief, score))

        living = (
            "pip install influenzer",
            "strangers opened issue #4 after the spike",
        )
        self.assertTrue(has_workshop_life(living[0]))
        self.assertTrue(has_workshop_life(living[1]))
        self.assertFalse(looks_like_dead_star_story(("N stars", living[0])))
        self.assertFalse(looks_like_dead_star_count("star the repo after you try it"))
        self.assertTrue(looks_like_solicit_gesture("star the repo after you try it"))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-living-stars",
            facts=(
                Fact(text="we hit 1200 stars this week"),
                Fact(text=living[0]),
                Fact(text=living[1], artifact_url=SHIP_PR),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.GITHUB)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "workshop")
        self.assertIn("pip install", draft.body.lower())
        self.assertIn("issue #4", draft.body.lower())

    def test_star_upvote_follow_or_rt_ask_is_silence_not_an_angle(self) -> None:
        asks = (
            "star the repo after you try it",
            "please star us",
            "give us a star",
            "please upvote this",
            "follow us",
            "RT this",
            "daj nam gwiazdkę",
        )
        self.assertFalse(looks_like_solicit_gesture(""))
        self.assertFalse(looks_like_solicit_gesture("follow the README to run the demo"))
        self.assertFalse(looks_like_solicit_gesture("Local tick scores briefs and emits a draft"))
        for idx, text in enumerate(asks):
            with self.subTest(text=text):
                self.assertTrue(looks_like_solicit_gesture(text))
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-solicit-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))
                survey = {
                    "meta": {"description": text, "homepageUrl": ""},
                    "prs": [
                        {
                            "number": 12,
                            "title": "feat: local HoM operator scores briefs",
                            "url": "https://github.com/mikolaj92/demo/pull/12",
                        }
                    ],
                    "releases": [{"tagName": "v0.1.0", "name": "v0.1.0"}],
                    "tags": [{"name": "v0.1.0"}],
                    "readme_text": "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n\n![demo](docs/demo.gif)\n",
                    "readme_url": "https://github.com/mikolaj92/demo/blob/main/README.md",
                }
                packed = pack_survey(
                    {
                        "status": "ok",
                        "ok": True,
                        "repo": "mikolaj92/demo",
                        "now": "2026-08-17T06:00:00Z",
                        "survey": survey,
                    }
                )
                self.assertEqual(packed["status"], "noop")
                self.assertEqual(packed["reason"], SOLICIT_GESTURE_REASON)
                self.assertIsNone(packed["brief_id"])
                self.assertNotIn("facts", packed)

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-solicit-alive",
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="follow the README to run the demo"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertIn("follow the README", draft.body)

    def test_letter_without_a_gift_is_silence(self) -> None:
        empties = (
            "subscribe to our list",
            "our launch is next week",
            "join the newsletter",
            "zapisz się na listę",
            "crush the competitor",
            "subscribe, then strangers can click and run the demo today",
        )
        for idx, text in enumerate(empties):
            with self.subTest(text=text):
                self.assertEqual(letter_reason(text), LETTER_ASK_WITHOUT_GIFT_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-empty-letter-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.NEWSLETTER,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.NEWSLETTER,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.NEWSLETTER,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, LETTER_ASK_WITHOUT_GIFT_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.NEWSLETTER,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.NEWSLETTER].wave,
                    canon_url=ARENAS[ArenaId.NEWSLETTER].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.NEWSLETTER, f"{text}\n{SHIP_PR}"),
                    (Verdict.KILL, LETTER_ASK_WITHOUT_GIFT_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        gift = "Local tick scores briefs and emits a draft"
        ask = "subscribe if you want the next cut"
        rec = "adjacent tool in the same niche, not a crush"
        byline = "Mikolaj Nowak"
        living = (gift, rec, ask, byline)
        self.assertTrue(has_letter_gift(gift))
        self.assertTrue(looks_like_letter_ask(ask))
        self.assertFalse(looks_like_letter_crush(rec))
        self.assertTrue(has_letter_surname(byline))
        self.assertIsNone(letter_reason("\n".join(living)))
        self.assertFalse(has_letter_gift("subscribe to our list"))
        self.assertFalse(looks_like_letter_ask("follow the README to run the demo"))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-living-letter",
            facts=(
                Fact(text=gift, artifact_url=SHIP_PR),
                Fact(text=rec),
                Fact(text=ask),
                Fact(text=byline),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.NEWSLETTER,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.NEWSLETTER, "\n".join((gift, rec, ask, byline, SHIP_PR))))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.NEWSLETTER)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "letter")
        self.assertIn("local tick", draft.body.lower())
        self.assertIn("adjacent", draft.body.lower())
        self.assertIn("mikolaj nowak", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

    def test_letter_without_a_surname_is_silence(self) -> None:
        nameless = (
            "we shipped a gift for the list",
            "the team wrote this week's letter",
            "From Mikolaj",
            "signed Mikolaj",
            "My App weekly letter",
        )
        gift = "Local tick scores briefs and emits a draft"
        rec = "adjacent tool in the same niche, not a crush"
        for idx, text in enumerate(nameless):
            with self.subTest(text=text):
                blob = "\n".join((gift, rec, text))
                self.assertTrue(has_letter_gift(blob))
                if text.startswith(("we ", "the team")):
                    self.assertTrue(looks_like_letter_team_voice(text))
                self.assertFalse(has_letter_surname(text))
                self.assertEqual(letter_reason(blob), LETTER_WITHOUT_SURNAME_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-nameless-letter-{idx}",
                    facts=(
                        Fact(text=gift, artifact_url=SHIP_PR),
                        Fact(text=rec),
                        Fact(text=text),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.NEWSLETTER,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, LETTER_WITHOUT_SURNAME_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.NEWSLETTER,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.NEWSLETTER].wave,
                    canon_url=ARENAS[ArenaId.NEWSLETTER].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.NEWSLETTER, f"{blob}\n{SHIP_PR}"),
                    (Verdict.KILL, LETTER_WITHOUT_SURNAME_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        self.assertEqual(self.app.brand.display_name, "My App")
        self.assertEqual(self.builder.brand.display_name, "Mikolaj")
        self.assertFalse(has_letter_surname(self.app.brand.display_name))
        self.assertFalse(has_letter_surname(self.builder.brand.display_name))
        self.assertFalse(has_letter_surname(self.app.brand.maintainer))
        named = "Mikolaj Nowak"
        self.assertTrue(has_letter_surname(named))
        self.assertFalse(looks_like_letter_team_voice(named))
        signed = Brief.create(
            project_id=self.builder.project_id,
            brief_id="b-named-letter",
            facts=(
                Fact(text=gift, artifact_url=SHIP_PR),
                Fact(text=rec),
                Fact(text=named),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.NEWSLETTER,
        )
        self.assertIsNone(_gate_violation(signed, ArenaId.NEWSLETTER, "\n".join((gift, rec, named, SHIP_PR))))
        score = score_brief(signed)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.NEWSLETTER)
        draft = compose_draft(signed, score)
        assert draft is not None
        self.assertEqual(draft.costume, "letter")
        self.assertIn("mikolaj nowak", draft.body.lower())
        self.assertNotIn("we ", draft.body.lower())
        self.assertNotIn("the team", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

    def test_letter_only_when_a_stranger_can_try_it(self) -> None:
        gift = "Local tick scores briefs and emits a draft"
        rec = "adjacent tool in the same niche, not a crush"
        named = "Mikolaj Nowak"
        feedback = "https://github.com/mikolaj92/influenzer/issues/4#issuecomment-101"
        silent = (
            (
                "tryable-no-ship",
                False,
                True,
                (
                    Fact(text=gift, artifact_url=SHIP_PR),
                    Fact(text=rec),
                    Fact(text=named),
                ),
            ),
            (
                "artifact-no-tryable",
                False,
                False,
                (
                    Fact(text=gift, artifact_url=SHIP_PR),
                    Fact(text=rec),
                    Fact(text=named),
                ),
            ),
            (
                "feedback-only",
                False,
                False,
                (
                    Fact(
                        kind="issue_comment",
                        text="@bob: How do I install this when uv is missing?",
                        artifact_url=feedback,
                    ),
                    Fact(text=gift),
                    Fact(text=named),
                ),
            ),
        )
        for label, claims_ship, tryable, facts in silent:
            with self.subTest(label=label):
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-letter-not-tryable-{label}",
                    facts=facts,
                    story_kind="major",
                    claims_ship=claims_ship,
                    tryable=tryable,
                    preferred_arena=ArenaId.NEWSLETTER,
                )
                blob = "\n".join(
                    part for part in (*(fact.text for fact in facts), SHIP_PR) if part
                )
                self.assertIsNone(_gate_violation(brief, ArenaId.NEWSLETTER, blob))
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
                self.assertEqual(score.reason, "newsletter_no_user_facing_change")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.NEWSLETTER,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.NEWSLETTER].wave,
                    canon_url=ARENAS[ArenaId.NEWSLETTER].canon_url,
                )
                self.assertIsNone(compose_draft(brief, leaked))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-letter-ship-tryable",
            facts=(
                Fact(text=gift, artifact_url=SHIP_PR),
                Fact(text=rec),
                Fact(text=named),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.NEWSLETTER,
        )
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.NEWSLETTER)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "letter")
        self.assertIn("local tick", draft.body.lower())
        self.assertIn("mikolaj nowak", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

    def test_show_hn_brand_voice_is_silence(self) -> None:
        brands = (
            "We at Product announced a local tick",
            "we announced the operator",
            "our team announced the demo",
            "the company announced a working demo",
            "ogłaszamy lokalny tick",
        )
        for idx, text in enumerate(brands):
            with self.subTest(text=text):
                self.assertTrue(looks_like_brand_voice(text))
                self.assertEqual(seminar_reason(text), SEMINAR_BRAND_VOICE_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-brand-hn-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, SEMINAR_BRAND_VOICE_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.HN, f"{text}\n{SHIP_PR}"),
                    (Verdict.KILL, SEMINAR_BRAND_VOICE_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        human = "I built a local tick that scores briefs"
        self.assertTrue(looks_like_seminar_first_person(human))
        self.assertFalse(looks_like_brand_voice(human))
        self.assertIsNone(seminar_reason(human))
        self.assertEqual(self.app.brand.maintainer, "mikolaj92")
        self.assertEqual(self.builder.brand.maintainer, "mikolaj92")
        alive = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-human-hn",
            facts=(
                Fact(text=human, artifact_url=SHIP_PR),
                Fact(text="I struggled with a queue that never scored a brief"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.HN, "\n".join((human, SHIP_PR))))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "seminar")
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertIn("I built", draft.body)
        self.assertIn(SHIP_PR, draft.body)
        self.assertIn("I struggled", draft.body)
        self.assertEqual(len(draft.body.split("\n\n")), 3)
        self.assertNotIn("We at Product", draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_show_hn_is_title_url_and_backstory_or_silence(self) -> None:
        human = "I built a local tick that scores briefs"
        backstory = "I struggled with a queue that never scored a brief"
        extra = "Patches stay changelog-only"
        title_only = Brief.create(
            project_id="app-1",
            brief_id="b-hn-title-only",
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(text=human),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(title_only)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNone(compose_draft(title_only, score))
        leaked = Score(
            brief_id=title_only.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(compose_draft(title_only, leaked))

        alive = Brief.create(
            project_id="app-1",
            brief_id="b-hn-three-fields",
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(text=human),
                Fact(text=backstory),
                Fact(text=extra),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        draft = compose_draft(alive, score_brief(alive))
        assert draft is not None
        self.assertEqual(draft.costume, "seminar")
        self.assertEqual(
            draft.body,
            f"Show HN: {human}\n\n{SHIP_PR}\n\n{backstory}",
        )
        self.assertNotIn(extra, draft.body)
        self.assertNotIn("please upvote", draft.body.lower())
        self.assertNotIn("waitlist", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

    def test_show_hn_without_tryable_ship_does_not_sit(self) -> None:
        # #40: exploration / decision / failure without tryable → HN forbidden.
        # Workshop or silence. Seminar only when a stranger can click and run.
        # Composes onto #32 (three fields). Not live. One story.
        lab = (
            ("exploration", "we tried a dry-run envelope and learned the adapter stays quiet"),
            ("decision", "we chose SQLite over a hosted store so the operator stays local"),
            ("failure", "the queue never scored a brief and we learned to fail closed"),
        )
        demo = "strangers can click and run the demo today"
        for kind, text in lab:
            with self.subTest(kind=kind):
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.HN,
                        claims_ship=False,
                        tryable=False,
                        story_kind=kind,
                        clickable=True,
                    ),
                    ArenaId.GITHUB,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.HN,
                        claims_ship=True,
                        tryable=True,
                        story_kind=kind,
                        clickable=True,
                    ),
                    ArenaId.GITHUB,
                )
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-hn-lab-{kind}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text=demo),
                    ),
                    story_kind=kind,
                    claims_ship=False,
                    tryable=False,
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertNotEqual(score.arena, ArenaId.HN)
                self.assertIn(score.arena, {ArenaId.GITHUB, None})
                draft = compose_draft(brief, score)
                if draft is not None:
                    self.assertEqual(draft.costume, "workshop")
                    self.assertNotEqual(draft.costume, "seminar")
                    self.assertNotIn("Show HN:", draft.body)
                    self.assertNotIn("Costume:", draft.body)
                self.assertEqual(
                    _gate_violation(brief, ArenaId.HN, "\n".join((text, demo))),
                    (Verdict.KILL, "hn_not_tryable"),
                )

        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.HN,
                claims_ship=True,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.HN,
        )
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.HN,
                claims_ship=False,
                tryable=False,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.HN,
        )
        seminar = Brief.create(
            project_id="app-1",
            brief_id="b-hn-tryable-sits",
            facts=(
                Fact(text="I built a local tick that scores briefs", artifact_url=SHIP_PR),
                Fact(text="I struggled with a queue that never scored a brief"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        seminar_score = score_brief(seminar)
        self.assertEqual(seminar_score.verdict, Verdict.DRAFT)
        self.assertEqual(seminar_score.arena, ArenaId.HN)
        seminar_draft = compose_draft(seminar, seminar_score)
        assert seminar_draft is not None
        self.assertEqual(seminar_draft.costume, "seminar")
        self.assertTrue(seminar_draft.body.startswith("Show HN:"))
        self.assertNotIn("Costume:", seminar_draft.body)

        decision = Brief.create(
            project_id="app-1",
            brief_id="b-hn-decision-workshop",
            facts=(
                Fact(text="we chose SQLite over a hosted store so the operator stays local", artifact_url=SHIP_PR),
                Fact(text=demo),
            ),
            story_kind="decision",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        decision_score = score_brief(decision)
        self.assertEqual(decision_score.verdict, Verdict.DRAFT)
        self.assertEqual(decision_score.arena, ArenaId.GITHUB)
        self.assertNotEqual(decision_score.arena, ArenaId.HN)
        decision_draft = compose_draft(decision, decision_score)
        assert decision_draft is not None
        self.assertEqual(decision_draft.costume, "workshop")
        self.assertNotEqual(decision_draft.costume, "seminar")
        self.assertNotIn("Show HN:", decision_draft.body)
        self.assertNotIn("Costume:", decision_draft.body)

    def test_reddit_without_named_sub_is_not_village(self) -> None:
        empties = (
            "I built a local tick that scores briefs",
            "post this on reddit",
            "village self-post in programming subs",
            "blast the programming cousins",
            "r/",
        )
        for text in empties:
            with self.subTest(text=text):
                self.assertFalse(has_named_subreddit(text))
                self.assertEqual(reddit_reason(f"{text}\n{SHIP_PR}"), REDDIT_NO_ROOM_REASON)

        unnamed = "I built a local tick that scores briefs"
        demo = "strangers can click and run the demo today"
        self.assertFalse(has_named_subreddit(unnamed))
        self.assertFalse(has_named_subreddit(demo))
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.REDDIT,
                claims_ship=True,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.REDDIT,
        )
        brief = Brief.create(
            project_id="app-1",
            brief_id="b-village-no-room",
            facts=(
                Fact(text=unnamed, artifact_url=SHIP_PR),
                Fact(text=demo),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.REDDIT,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, REDDIT_NO_ROOM_REASON)
        self.assertIsNone(score.arena)
        self.assertNotEqual(score.arena, ArenaId.REDDIT)
        leaked = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.REDDIT,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.REDDIT].wave,
            canon_url=ARENAS[ArenaId.REDDIT].canon_url,
        )
        self.assertEqual(
            _gate_violation(brief, ArenaId.REDDIT, f"{unnamed}\n{SHIP_PR}\n{demo}"),
            (Verdict.KILL, REDDIT_NO_ROOM_REASON),
        )
        self.assertIsNone(compose_draft(brief, leaked))

        labeled = Brief.create(
            project_id="app-1",
            brief_id="b-village-kind-only",
            facts=(
                Fact(
                    kind="subreddit",
                    text=unnamed,
                    artifact_url=SHIP_PR,
                ),
                Fact(text=demo),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.REDDIT,
        )
        labeled_score = score_brief(labeled)
        self.assertEqual(labeled_score.verdict, Verdict.KILL)
        self.assertEqual(labeled_score.reason, REDDIT_NO_ROOM_REASON)
        self.assertIsNone(labeled_score.arena)
        self.assertIsNone(compose_draft(labeled, leaked))

        self.assertEqual(
            choose_arena(
                claims_ship=True,
                tryable=True,
                story_kind="major",
                clickable=True,
            ),
            ArenaId.HN,
        )
        no_pref = Brief.create(
            project_id="app-1",
            brief_id="b-village-falls-to-hn",
            facts=(
                Fact(text=unnamed, artifact_url=SHIP_PR),
                Fact(text=demo),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        no_pref_score = score_brief(no_pref)
        self.assertEqual(no_pref_score.verdict, Verdict.DRAFT)
        self.assertEqual(no_pref_score.arena, ArenaId.HN)
        self.assertNotEqual(no_pref_score.arena, ArenaId.REDDIT)
        no_pref_draft = compose_draft(no_pref, no_pref_score)
        assert no_pref_draft is not None
        self.assertEqual(no_pref_draft.costume, "seminar")
        self.assertNotEqual(no_pref_draft.costume, "village")
        self.assertNotIn("Costume:", no_pref_draft.body)

        self.assertTrue(has_named_subreddit("native self-post in r/SideProject"))
        self.assertNotEqual(
            reddit_reason(f"{unnamed}\n{SHIP_PR}"),
            reddit_reason(f"{unnamed}\nr/SideProject\n{SHIP_PR}"),
        )

    def test_reddit_without_disclosure_is_silence(self) -> None:
        empties = (
            "timeouts looked like success in r/SideProject",
            "bez ujawnienia, native self-post in r/SideProject",
        )
        for idx, text in enumerate(empties):
            with self.subTest(text=text):
                self.assertTrue(has_named_subreddit(text))
                self.assertEqual(reddit_reason(f"{text}\n{SHIP_PR}"), REDDIT_NO_DISCLOSURE_REASON)
                brief = Brief.create(
                    project_id="app-1",
                    brief_id=f"b-village-spam-{idx}",
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    story_kind="major",
                    claims_ship=True,
                    tryable=True,
                    preferred_arena=ArenaId.REDDIT,
                )
                self.assertEqual(
                    choose_arena(
                        preferred_arena=ArenaId.REDDIT,
                        claims_ship=True,
                        tryable=True,
                        story_kind="major",
                        clickable=True,
                    ),
                    ArenaId.REDDIT,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, REDDIT_NO_DISCLOSURE_REASON)
                self.assertIsNone(score.arena)
                leaked = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.REDDIT,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.REDDIT].wave,
                    canon_url=ARENAS[ArenaId.REDDIT].canon_url,
                )
                self.assertEqual(
                    _gate_violation(brief, ArenaId.REDDIT, f"{text}\n{SHIP_PR}"),
                    (Verdict.KILL, REDDIT_NO_DISCLOSURE_REASON),
                )
                self.assertIsNone(compose_draft(brief, leaked))

        nameless = "I built a local tick in r/SideProject"
        self.assertTrue(looks_like_reddit_disclose(nameless))
        self.assertTrue(has_named_subreddit(nameless))
        self.assertFalse(has_reddit_repo(nameless))
        self.assertEqual(reddit_reason(nameless), REDDIT_NO_DISCLOSURE_REASON)
        no_repo = Brief.create(
            project_id="app-1",
            brief_id="b-village-no-repo",
            facts=(
                Fact(text=nameless),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.REDDIT,
        )
        score = score_brief(no_repo)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, REDDIT_NO_DISCLOSURE_REASON)
        self.assertIsNone(compose_draft(no_repo, score))

        disclose = "I built a local tick that scores briefs"
        room = "native self-post in r/SideProject"
        living = (disclose, room, SHIP_PR)
        self.assertTrue(looks_like_reddit_disclose(disclose))
        self.assertTrue(has_named_subreddit(room))
        self.assertTrue(has_reddit_repo(SHIP_PR))
        self.assertIsNone(reddit_reason("\n".join(living)))
        self.assertFalse(looks_like_reddit_disclose("timeouts in r/SideProject"))
        self.assertFalse(looks_like_reddit_disclose("bez ujawnienia in r/SideProject"))
        self.assertFalse(has_reddit_repo(disclose))
        alive = Brief.create(
            project_id="app-1",
            brief_id="b-village-disclosed",
            facts=(
                Fact(text=disclose, artifact_url=SHIP_PR),
                Fact(text=room),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.REDDIT,
        )
        self.assertIsNone(_gate_violation(alive, ArenaId.REDDIT, "\n".join(living)))
        score = score_brief(alive)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.REDDIT)
        draft = compose_draft(alive, score)
        assert draft is not None
        self.assertEqual(draft.costume, "village")
        self.assertIn("I built", draft.body)
        self.assertIn(SHIP_PR, draft.body)
        self.assertIn("r/SideProject", draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_after_show_hn_score_does_not_pick_hn_again(self) -> None:
        human = "I built a local tick that scores briefs"
        first = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-first-show",
            facts=(
                Fact(text=human, artifact_url=SHIP_PR),
                Fact(text="I struggled with a queue that never scored a brief"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        first_score = score_brief(first)
        self.assertEqual(first_score.verdict, Verdict.DRAFT)
        self.assertEqual(first_score.arena, ArenaId.HN)
        first_draft = compose_draft(first, first_score)
        assert first_draft is not None
        self.assertTrue(first_draft.body.startswith("Show HN:"))

        again = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-second-show",
            facts=(
                Fact(text="I built a second local tick that scores briefs", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(again, stack_arena=ArenaId.HN)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, HN_CAMP_REASON)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(again, score))
        leaked = Score(
            brief_id=again.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        leaked_draft = compose_draft(again, leaked)
        assert leaked_draft is not None
        self.assertTrue(leaked_draft.body.startswith("Show HN:"))
        self.assertIn("A second Show is silence", " ".join(ARENAS[ArenaId.HN].wave))

    def test_readme_without_demo_is_changelog_not_a_github_launch(self) -> None:
        installable = "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n"
        visible = installable + "\n![demo](docs/demo.gif)\n"
        self.assertFalse(readme_has_visible_demo(installable))
        self.assertFalse(readme_has_visible_demo(installable + "\n![ci](https://img.shields.io/github/stars/mikolaj92/demo)\n"))
        self.assertTrue(readme_has_visible_demo(visible))

        survey = {
            "meta": {"description": "Local operator with a working install", "homepageUrl": ""},
            "prs": [
                {
                    "number": 12,
                    "title": "feat: local HoM operator scores briefs",
                    "url": "https://github.com/mikolaj92/demo/pull/12",
                }
            ],
            "releases": [{"tagName": "v0.1.0", "name": "v0.1.0"}],
            "tags": [{"name": "v0.1.0"}],
            "readme_text": installable,
            "readme_url": "https://github.com/mikolaj92/demo/blob/main/README.md",
        }
        dead = pack_survey({"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": survey})
        self.assertEqual(dead["status"], "noop")
        self.assertEqual(dead["reason"], README_WITHOUT_DEMO_REASON)
        self.assertTrue(dead["ok"])
        self.assertIsNone(dead["brief_id"])
        self.assertNotIn("facts", dead)

        living = dict(survey)
        living["readme_text"] = visible
        packed = pack_survey(
            {"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": living}
        )
        self.assertEqual(packed["status"], "ok")
        self.assertTrue(packed["claims_ship"])
        self.assertTrue(packed["tryable"])
        brief = Brief.create(
            project_id="app-1",
            brief_id=str(packed["brief_id"]),
            facts=tuple(
                Fact(
                    kind=str(item.get("kind") or "signal"),
                    text=str(item.get("text") or ""),
                    artifact_url=item.get("artifact_url"),
                )
                for item in packed["facts"]
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.GITHUB)
        draft = compose_draft(brief, score)
        assert draft is not None
        self.assertEqual(draft.costume, "workshop")
        self.assertNotIn("Costume:", draft.body)

    def test_readme_without_copyable_start_is_not_a_social_launch(self) -> None:
        prose = (
            "# Demo\n\nInstall with pip install influenzer, then uv run the tick.\n"
            "\n![demo](docs/demo.gif)\n"
        )
        copyable = "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n\n![demo](docs/demo.gif)\n"
        self.assertFalse(readme_has_copyable_start(prose))
        self.assertTrue(readme_has_copyable_start(copyable))

        survey = {
            "meta": {"description": "Local operator with a working install", "homepageUrl": ""},
            "prs": [
                {
                    "number": 12,
                    "title": "feat: local HoM operator scores briefs",
                    "url": "https://github.com/mikolaj92/demo/pull/12",
                }
            ],
            "releases": [{"tagName": "v0.1.0", "name": "v0.1.0"}],
            "tags": [{"name": "v0.1.0"}],
            "readme_text": prose,
            "readme_url": "https://github.com/mikolaj92/demo/blob/main/README.md",
        }
        dead = pack_survey(
            {"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": survey}
        )
        self.assertEqual(dead["status"], "noop")
        self.assertEqual(dead["reason"], README_WITHOUT_QUICKSTART_REASON)
        self.assertTrue(dead["ok"])
        self.assertIsNone(dead["brief_id"])
        self.assertNotIn("facts", dead)
        self.assertNotIn("claims_ship", dead)

        living = dict(survey)
        living["readme_text"] = copyable
        packed = pack_survey(
            {"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": living}
        )
        self.assertEqual(packed["status"], "ok")
        self.assertTrue(packed["claims_ship"])
        self.assertTrue(packed["tryable"])
        brief = Brief.create(
            project_id="app-1",
            brief_id=str(packed["brief_id"]),
            facts=tuple(
                Fact(
                    kind=str(item.get("kind") or "signal"),
                    text=str(item.get("text") or ""),
                    artifact_url=item.get("artifact_url"),
                )
                for item in packed["facts"]
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(brief, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertNotIn("Costume:", draft.body)

    def test_same_window_revert_is_not_a_ship_or_show_hn(self) -> None:
        survey = {
            "meta": {"description": "Local operator with a working install", "homepageUrl": ""},
            "prs": [
                {
                    "number": 12,
                    "title": "feat: local HoM operator scores briefs",
                    "url": "https://github.com/mikolaj92/demo/pull/12",
                },
                {
                    "number": 13,
                    "title": 'Revert "feat: local HoM operator scores briefs"',
                    "url": "https://github.com/mikolaj92/demo/pull/13",
                },
            ],
            "releases": [{"tagName": "v0.1.0", "name": "v0.1.0"}],
            "tags": [{"name": "v0.1.0"}],
            "readme_text": "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n\n![demo](docs/demo.gif)\n",
            "readme_url": "https://github.com/mikolaj92/demo/blob/main/README.md",
        }
        dead = pack_survey(
            {"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": survey}
        )
        self.assertEqual(dead["status"], "noop")
        self.assertEqual(dead["reason"], REVERTED_NOT_A_SHIP_REASON)
        self.assertTrue(dead["ok"])
        self.assertIsNone(dead["brief_id"])
        self.assertNotIn("claims_ship", dead)
        self.assertNotIn("facts", dead)

        living = dict(survey)
        living["prs"] = [survey["prs"][0]]
        packed = pack_survey(
            {"status": "ok", "ok": True, "repo": "mikolaj92/demo", "now": "2026-08-17T06:00:00Z", "survey": living}
        )
        self.assertEqual(packed["status"], "ok")
        self.assertTrue(packed["claims_ship"])
        self.assertTrue(packed["tryable"])
        brief = Brief.create(
            project_id="app-1",
            brief_id=str(packed["brief_id"]),
            facts=tuple(
                Fact(
                    kind=str(item.get("kind") or "signal"),
                    text=str(item.get("text") or ""),
                    artifact_url=item.get("artifact_url"),
                )
                for item in packed["facts"]
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(brief, score)
        assert draft is not None
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertNotIn("Costume:", draft.body)

    def test_open_story_on_one_project_silences_the_other_watch(self) -> None:
        pending = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-open-app",
            facts=(Fact(text="already working a story"),),
            story_kind="major",
        )
        self.repo.save_brief(pending)
        self.assertEqual(open_story_reason(self.repo, self.app.project_id), "pending_brief")
        self.assertEqual(open_story_reason(self.repo, self.builder.project_id), "pending_brief")

        social = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-open-hn",
            facts=(
                Fact(text="I built a local tick that scores briefs", artifact_url=SHIP_PR),
                Fact(text="I struggled with a queue that never scored a brief"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(social)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        draft = compose_draft(social, score)
        assert draft is not None
        self.repo.conn.execute("DELETE FROM briefs")
        self.repo.save_brief(social)
        self.repo.persist_operator_decision(social, score, draft, now="2026-08-17T06:00:00Z")
        self.assertEqual(open_story_reason(self.repo, self.app.project_id), "social_draft")
        self.assertEqual(open_story_reason(self.repo, self.builder.project_id), "social_draft")

        workshop = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-open-github",
            facts=(
                Fact(text="pip install influenzer", artifact_url=SHIP_PR),
                Fact(text="strangers opened issue #4 after the spike"),
            ),
            story_kind="major",
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        workshop_score = score_brief(workshop)
        self.assertEqual(workshop_score.verdict, Verdict.DRAFT)
        self.assertEqual(workshop_score.arena, ArenaId.GITHUB)
        workshop_draft = compose_draft(workshop, workshop_score, now="2026-08-17T06:00:00Z")
        assert workshop_draft is not None
        self.repo.conn.execute("DELETE FROM operator_drafts")
        self.repo.conn.execute("DELETE FROM operator_scores")
        self.repo.conn.execute("DELETE FROM briefs")
        self.repo.save_brief(workshop)
        self.repo.persist_operator_decision(
            workshop, workshop_score, workshop_draft, now="2026-08-17T06:00:00Z"
        )
        self.assertEqual(self.repo.living_stack_arena(self.app.project_id, "2026-08-17T06:00:00Z"), ArenaId.GITHUB)
        self.assertEqual(
            self.repo.living_stack_arena(self.builder.project_id, "2026-08-17T06:00:00Z"),
            ArenaId.GITHUB,
        )
        self.assertEqual(
            open_story_reason(self.repo, self.app.project_id, "2026-08-17T06:00:00Z"),
            LIVING_STACK_REASON,
        )
        self.assertEqual(
            open_story_reason(self.repo, self.builder.project_id, "2026-08-17T06:00:00Z"),
            LIVING_STACK_REASON,
        )
        again = Brief.create(
            project_id=self.app.project_id,
            brief_id="b-second-github",
            facts=(
                Fact(text="a stranger can click and run the demo from the README", artifact_url=SHIP_PR),
                Fact(text="Dry-run still default"),
            ),
            story_kind="major",
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        again_score = score_brief(again, stack_arena=ArenaId.GITHUB)
        self.assertEqual(again_score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(again_score.reason, LIVING_STACK_REASON)
        self.assertIsNone(again_score.arena)
        self.assertIsNone(compose_draft(again, again_score))
        self.assertIsNone(open_story_reason(self.repo, self.builder.project_id, "2026-08-19T06:00:01Z"))


if __name__ == "__main__":
    unittest.main()
