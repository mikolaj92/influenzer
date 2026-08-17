from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from influenzer.adapters.base import AdapterRequest, run_adapter
from influenzer.config import Config
from influenzer.content import ContentError, create_revision, persist_revision
from influenzer.domain import (
    EVENT_NOT_A_SHIP,
    AccountStatus,
    AttemptStatus,
    ContentRevision,
    ContentStatus,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    Project,
    PublishPlan,
    PlanStatus,
    content_hash,
    looks_like_event,
)
from influenzer.hom import Brief, Fact
from influenzer.scheduler import DueWork, tick
from influenzer.storage import StateRepository


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


SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"


class EventIsNotAShipTests(unittest.TestCase):
    """Webinar / meetup / calendar / join us Thursday is cisza, not a ship."""

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
        self.repo.save_project(self.app)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def test_event_phrases_are_not_a_ship(self) -> None:
        vapor = (
            "webinar Thursday",
            "join us Thursday",
            "meetup next week",
            "add it to the calendar",
            "wydarzenie w czwartek",
            "dołącz w czwartek",
        )
        for text in vapor:
            with self.subTest(text=text):
                self.assertTrue(looks_like_event(text))
        self.assertFalse(looks_like_event("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_event("as soon as you install, the local tick scores"))

    def test_event_body_cannot_become_a_revision(self) -> None:
        with self.assertRaises(ContentError) as err:
            create_revision(
                project_id="app-1",
                content_id="c-event",
                revision_id="r-event",
                body="join us Thursday for the webinar",
                status=ContentStatus.READY,
            )
        self.assertEqual(str(err.exception), EVENT_NOT_A_SHIP)

        leftover = ContentRevision(
            project_id="app-1",
            content_id="c-left",
            revision_id="r-left",
            body="meetup on the calendar",
            kind="post",
            status=ContentStatus.READY,
            source="manual",
            source_digest=content_hash({"source": "manual", "body": "meetup on the calendar"}),
            created_at="2026-01-01T00:00:00Z",
        ).with_hash()
        with self.assertRaises(ContentError) as leftover_err:
            persist_revision(self.repo, leftover)
        self.assertEqual(str(leftover_err.exception), EVENT_NOT_A_SHIP)

    def test_webinar_brief_is_killed_not_drafted(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="webinar-1",
            facts=(Fact(text="join us Thursday for the webinar", artifact_url=SHIP_PR),),
            story_kind="major",
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        cfg = Config(home=self.home, scheduler_live_enabled=False)
        out = tick(self.repo, cfg, due=(), now="2026-01-02T00:00:00Z")
        outcome = out["operator"]["outcomes"][0]
        self.assertEqual(outcome["verdict"], "kill")
        self.assertEqual(outcome["reason"], EVENT_NOT_A_SHIP)
        self.assertIsNone(outcome.get("draft_id") or None)
        self.assertIsNone(self.repo.get_operator_draft("app-1", "webinar-1"))
        score = self.repo.get_operator_score("app-1", "webinar-1")
        assert score is not None
        self.assertEqual(score.reason, EVENT_NOT_A_SHIP)
        self.assertEqual(score.verdict.value, "kill")

    def test_live_event_plan_is_denied_without_adapter(self) -> None:
        body = "join us Thursday for the webinar"
        leftover = ContentRevision(
            project_id="app-1",
            content_id="c-live-event",
            revision_id="r-live-event",
            body=body,
            kind="post",
            status=ContentStatus.READY,
            source="manual",
            source_digest=content_hash({"source": "manual", "body": body}),
            created_at="2026-01-01T00:00:00Z",
        ).with_hash()
        self.repo.save_content_revision(leftover)
        account = PlatformAccount(
            project_id="app-1",
            account_id="bluesky-event",
            platform="bluesky",
            handle="@app-1",
            host=None,
            credential_ref="env:TOKEN",
            status=AccountStatus.CONNECTED,
        )
        self.repo.save_account(account)
        policy = PolicyVersion(
            project_id="app-1",
            policy_version_id="pol-event",
            account_ids=(account.account_id,),
            actions=("publish",),
            content_kinds=("post",),
            max_posts_per_day=10,
            require_disclosures=False,
        ).with_hash()
        self.repo.save_policy(policy)
        grant = PolicyActivationGrant(
            project_id="app-1",
            grant_id="grant-event",
            policy_version_id=policy.policy_version_id,
            policy_hash=policy.policy_hash,
            platform_account_id=account.account_id,
            actions=("publish",),
            actor="tester",
            created_at="2026-01-01T00:00:00Z",
            expires_at=None,
        )
        self.repo.save_grant(grant)
        plan = PublishPlan(
            project_id="app-1",
            plan_id="p-event",
            content_revision_id=leftover.revision_id,
            content_hash=leftover.content_hash,
            platform_account_id=account.account_id,
            platform="bluesky",
            body=body,
            status=PlanStatus.SCHEDULED,
            scheduled_at=None,
            created_at="2026-01-01T00:00:00Z",
            operation_key="op-event",
        )
        self.repo.save_plan(plan)
        called: list[AdapterRequest] = []

        def fake(req: AdapterRequest) -> dict:
            called.append(req)
            return {"status": "ok", "ok": True, "mutated": True, "provider_id": "should-not"}

        cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            cfg,
            due=[DueWork(plan=plan, account=account, policy=policy, grant=grant)],
            now="2026-01-02T00:00:00Z",
            handlers={"bluesky": fake},
        )
        self.assertEqual(called, [])
        self.assertFalse(out["mutated"])
        self.assertEqual(out["outcomes"][0]["reason"], EVENT_NOT_A_SHIP)
        self.assertEqual(out["outcomes"][0]["status"], "denied")
        stored = self.repo.conn.execute(
            "SELECT status FROM publish_plans WHERE plan_id=?", ("p-event",)
        ).fetchone()["status"]
        self.assertEqual(stored, PlanStatus.SCHEDULED.value)

    def test_adapter_refuses_event_body(self) -> None:
        req = AdapterRequest(
            platform="bluesky",
            project_id="app-1",
            account_id="bluesky-1",
            body="join us Thursday for the meetup",
            operation_key="op-event",
            dry_run=False,
        )

        def fake(_req: AdapterRequest) -> dict:
            return {"status": "ok", "ok": True, "mutated": True, "provider_id": "should-not"}

        out = run_adapter(fake, req)
        self.assertFalse(out["ok"])
        self.assertFalse(out["mutated"])
        self.assertEqual(out["reason"], EVENT_NOT_A_SHIP)


if __name__ == "__main__":
    unittest.main()
