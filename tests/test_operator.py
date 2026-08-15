from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from influenzer.adapters.base import AdapterRequest, run_adapter
from influenzer.adapters.registry import get_adapter
from influenzer.campaigns import create_campaign, export_campaign_plan, persist_campaign
from influenzer.config import Config, write_config
from influenzer import content as content_mod
from influenzer.content import create_revision, persist_revision
from influenzer.domain import (
    AccountStatus,
    AttemptStatus,
    CampaignKind,
    ContentStatus,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    Project,
    PublicationAttempt,
    PublishPlan,
    PlanStatus,
    transition_plan,
)
from influenzer.scheduler import DueWork, resolve_live_intent, tick
from influenzer.storage import StateRepository


class OperatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cfg = Config(home=self.home, scheduler_live_enabled=False)
        write_config(self.home / "config.json", self.cfg)
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

    def test_content_revision_is_project_scoped_and_immutable_hash(self) -> None:
        rev = create_revision(
            project_id="app-1",
            content_id="c1",
            revision_id="r1",
            body="shipping dry-run",
            status=ContentStatus.READY,
        )
        persist_revision(self.repo, rev)
        other = create_revision(
            project_id="builder-1",
            content_id="c1",
            revision_id="r1",
            body="builder note",
            status=ContentStatus.READY,
        )
        persist_revision(self.repo, other)
        self.assertNotEqual(rev.content_hash, other.content_hash)

    def test_content_revision_statuses_are_explicit_modern_path_only(self) -> None:
        """Content uses create_revision only; no legacy importer or unverified status."""
        self.assertFalse(hasattr(content_mod, "import_legacy_card"))
        self.assertFalse(hasattr(content_mod, "import_legacy_directory"))
        self.assertNotIn("legacy_unverified", {s.value for s in ContentStatus})
        self.assertEqual(
            {s.value for s in ContentStatus},
            {"draft", "in_review", "ready", "archived"},
        )
        rev = create_revision(
            project_id="app-1",
            content_id="c-modern",
            revision_id="r-modern",
            body="modern draft body",
            source="manual",
            status=ContentStatus.DRAFT,
        )
        persist_revision(self.repo, rev)
        self.assertEqual(rev.status, ContentStatus.DRAFT)
        self.assertEqual(rev.source, "manual")
        # Creating content never invents a remote publish outcome.
        self.assertNotIn(rev.status.value, {"succeeded", "published_confirmed", "reconciled_succeeded"})

    def test_paid_campaign_is_plan_only_no_spend(self) -> None:
        campaign = create_campaign(
            project_id="app-1",
            campaign_id="camp-1",
            name="Launch",
            kind=CampaignKind.PAID,
            budget_amount=100.0,
            budget_currency="USD",
            disclosures=("ad",),
        )
        persist_campaign(self.repo, campaign)
        export_path = export_campaign_plan(campaign, self.home / "export.json")
        data = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertFalse(data["executable_spend"])
        self.assertEqual(data["kind"], "paid")

    def test_tick_all_ignores_cli_live_without_scheduler_flag(self) -> None:
        self.assertFalse(resolve_live_intent(scheduler=True, cli_live=True, config=self.cfg))
        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        self.assertTrue(resolve_live_intent(scheduler=True, cli_live=False, config=live_cfg))
        out = tick(self.repo, self.cfg, due=(), cli_live=True)
        self.assertTrue(out["cli_live_ignored"])
        self.assertFalse(out["scheduler_live_enabled"])
        self.assertFalse(out["mutated"])

    def test_adapter_dry_run_never_mutates(self) -> None:
        req = AdapterRequest(
            platform="bluesky",
            project_id="app-1",
            account_id="bsky-1",
            body="hello",
            operation_key="op-1",
            dry_run=True,
        )
        out = run_adapter(get_adapter("bluesky"), req)
        self.assertTrue(out["ok"])
        self.assertTrue(out["dry_run"])
        self.assertFalse(out["mutated"])
        self.assertEqual(out["status"], "planned")

        def bad(_req: AdapterRequest) -> dict:
            return {"status": "ok", "ok": True, "mutated": True}

        rejected = run_adapter(bad, req)
        self.assertFalse(rejected["ok"])

    def _scheduled_fixture(self, *, plan_id: str, operation_key: str):
        account = PlatformAccount(
            project_id="app-1",
            account_id=f"x-{plan_id}",
            platform="x",
            handle="@app",
            host=None,
            credential_ref="env:X_TOKEN",
            status=AccountStatus.CONNECTED,
        )
        self.repo.save_account(account)
        policy = PolicyVersion(
            project_id="app-1",
            policy_version_id=f"pol-{plan_id}",
            account_ids=(account.account_id,),
            actions=("publish",),
            content_kinds=("post",),
            max_posts_per_day=5,
            require_disclosures=False,
        ).with_hash()
        self.repo.save_policy(policy)
        grant = PolicyActivationGrant(
            project_id="app-1",
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
            project_id="app-1",
            content_id=f"c-{plan_id}",
            revision_id=f"r-{plan_id}",
            body="hello live",
            status=ContentStatus.READY,
        )
        persist_revision(self.repo, rev)
        plan = PublishPlan(
            project_id="app-1",
            plan_id=plan_id,
            content_revision_id=rev.revision_id,
            content_hash=rev.content_hash,
            platform_account_id=account.account_id,
            platform="x",
            body="hello live",
            status=PlanStatus.SCHEDULED,
            scheduled_at=None,
            created_at="2026-01-01T00:00:00Z",
            operation_key=operation_key,
        )
        self.repo.save_plan(plan)
        return account, policy, grant, plan

    def test_scheduler_dry_run_does_not_claim_or_dispatch(self) -> None:
        account, policy, grant, plan = self._scheduled_fixture(plan_id="plan-dry", operation_key="op-dry")
        called = {"n": 0}

        def handler(_req: AdapterRequest) -> dict:
            called["n"] += 1
            return {"status": "ok", "ok": True, "mutated": True}

        out = tick(
            self.repo,
            self.cfg,
            due=[DueWork(plan=plan, account=account, policy=policy, grant=grant)],
            cli_live=True,
            now="2026-01-02T00:00:00Z",
            handlers={"x": handler},
        )
        self.assertEqual(out["outcomes"][0]["status"], "planned")
        self.assertEqual(called["n"], 0)
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-dry",)
            ).fetchone()["status"],
            PlanStatus.SCHEDULED.value,
        )
        self.assertIsNone(
            self.repo.conn.execute(
                "SELECT 1 FROM publication_attempts WHERE plan_id=?", ("plan-dry",)
            ).fetchone()
        )

    def test_score_only_tick_ignores_live_enabled_and_due_plans(self) -> None:
        account, policy, grant, plan = self._scheduled_fixture(plan_id="plan-look", operation_key="op-look")
        called = {"n": 0}

        def handler(_req: AdapterRequest) -> dict:
            called["n"] += 1
            return {"status": "ok", "ok": True, "mutated": True}

        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            live_cfg,
            due=[DueWork(plan=plan, account=account, policy=policy, grant=grant)],
            cli_live=True,
            now="2026-01-02T00:00:00Z",
            handlers={"x": handler},
            score_only=True,
        )
        self.assertEqual(called["n"], 0)
        self.assertFalse(out["mutated"])
        self.assertNotIn("outcomes", out)
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-look",)
            ).fetchone()["status"],
            PlanStatus.SCHEDULED.value,
        )
        self.assertIsNone(
            self.repo.conn.execute(
                "SELECT 1 FROM publication_attempts WHERE plan_id=?", ("plan-look",)
            ).fetchone()
        )

    def test_scheduler_denies_without_grant_even_when_live_enabled(self) -> None:
        account, policy, _grant, plan = self._scheduled_fixture(plan_id="plan-1", operation_key="op-1")
        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            live_cfg,
            due=[DueWork(plan=plan, account=account, policy=policy, grant=None)],
            cli_live=True,
            now="2026-01-02T00:00:00Z",
        )
        self.assertEqual(out["outcomes"][0]["status"], "denied")
        self.assertFalse(out["mutated"])

    def test_live_success_updates_plan_and_attempt(self) -> None:
        account, policy, grant, plan = self._scheduled_fixture(plan_id="plan-ok", operation_key="op-ok")

        def succeed(_req: AdapterRequest) -> dict:
            return {
                "status": "ok",
                "ok": True,
                "mutated": True,
                "provider_id": "prov-1",
                "provider_url": "https://example.test/1",
            }

        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        out = tick(
            self.repo,
            live_cfg,
            due=[DueWork(plan=plan, account=account, policy=policy, grant=grant)],
            now="2026-01-02T00:00:00Z",
            handlers={"x": succeed},
        )
        self.assertTrue(out["mutated"])
        row = self.repo.conn.execute(
            "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-ok",)
        ).fetchone()
        self.assertEqual(row["status"], PlanStatus.SUCCEEDED.value)
        attempt = self.repo.conn.execute(
            "SELECT status, provider_id FROM publication_attempts WHERE plan_id=?",
            ("plan-ok",),
        ).fetchone()
        self.assertEqual(attempt["status"], AttemptStatus.SUCCEEDED.value)
        self.assertEqual(attempt["provider_id"], "prov-1")

    def test_live_unknown_and_failed_outcomes_persist(self) -> None:
        account, policy, grant, plan_u = self._scheduled_fixture(plan_id="plan-u", operation_key="op-u")

        def unknown(_req: AdapterRequest) -> dict:
            return {"status": "unknown", "ok": False, "mutated": False, "reason": "timeout"}

        live_cfg = Config(home=self.home, scheduler_live_enabled=True)
        out_u = tick(
            self.repo,
            live_cfg,
            due=[DueWork(plan=plan_u, account=account, policy=policy, grant=grant)],
            now="2026-01-02T00:00:00Z",
            handlers={"x": unknown},
        )
        self.assertFalse(out_u["mutated"])
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-u",)
            ).fetchone()["status"],
            PlanStatus.UNKNOWN.value,
        )

        account2, policy2, grant2, plan_f = self._scheduled_fixture(plan_id="plan-f", operation_key="op-f")

        def fail(_req: AdapterRequest) -> dict:
            return {
                "status": "failed",
                "ok": False,
                "mutated": False,
                "failure_class": "terminal",
                "reason": "denied by provider",
            }

        out_f = tick(
            self.repo,
            live_cfg,
            due=[DueWork(plan=plan_f, account=account2, policy=policy2, grant=grant2)],
            now="2026-01-03T00:00:00Z",
            handlers={"x": fail},
        )
        self.assertFalse(out_f["mutated"])
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-f",)
            ).fetchone()["status"],
            PlanStatus.FAILED.value,
        )

    def test_reserve_attempt_is_atomic_and_cas_safe(self) -> None:
        _account, _policy, _grant, plan = self._scheduled_fixture(plan_id="plan-r", operation_key="op-r")
        executing = transition_plan(plan, PlanStatus.EXECUTING)
        attempt = PublicationAttempt(
            project_id=plan.project_id,
            attempt_id="att-r",
            plan_id=plan.plan_id,
            operation_key=plan.operation_key,
            status=AttemptStatus.PENDING,
            created_at="2026-01-02T00:00:00Z",
        )
        self.repo.reserve_attempt(executing, attempt)
        self.assertEqual(
            self.repo.conn.execute(
                "SELECT status FROM publish_plans WHERE plan_id=?", ("plan-r",)
            ).fetchone()["status"],
            PlanStatus.EXECUTING.value,
        )
        with self.assertRaises(Exception):
            self.repo.reserve_attempt(
                executing,
                PublicationAttempt(
                    project_id=plan.project_id,
                    attempt_id="att-r-2",
                    plan_id=plan.plan_id,
                    operation_key=plan.operation_key,
                    status=AttemptStatus.PENDING,
                    created_at="2026-01-02T00:00:01Z",
                ),
            )
        attempts = list(
            self.repo.conn.execute(
                "SELECT attempt_id,status FROM publication_attempts WHERE plan_id=?",
                ("plan-r",),
            )
        )
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["attempt_id"], "att-r")
        self.assertEqual(attempts[0]["status"], AttemptStatus.PENDING.value)

    def test_cli_project_create_persists_and_reopens(self) -> None:
        from influenzer.cli import main

        code = main(
            [
                "--config",
                str(self.home / "config.json"),
                "project",
                "create",
                "--id",
                "app-2",
                "--slug",
                "other-app",
                "--name",
                "Other",
                "--display-name",
                "Other",
                "--voice",
                "v",
                "--audience",
                "a",
                "--maintainer",
                "m",
                "--kind",
                "app",
            ]
        )
        self.assertEqual(code, 0)
        reopened = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        try:
            stored = reopened.get_project("app-2")
            self.assertIsNotNone(stored)
            assert stored is not None
            self.assertEqual(stored.kind, "app")
            self.assertTrue(stored.brand.profile_hash)
        finally:
            reopened.close()


if __name__ == "__main__":
    unittest.main()
