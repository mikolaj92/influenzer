import unittest
from datetime import datetime, timezone

from influenzer.domain import AccountStatus, ContentRevision, ContentStatus, PlatformAccount, PolicyActivationGrant, PolicyVersion
from influenzer.policy import evaluate_policy, policy_hash


NOW = datetime(2026, 1, 2, 12, 0, tzinfo=timezone.utc)
CONTENT_HASH = "content-1"


class PolicyEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.policy = PolicyVersion(
            project_id="project-a",
            policy_version_id="policy-1",
            account_ids=("account-a",),
            actions=("publish",),
            content_kinds=("post",),
            max_posts_per_day=2,
            require_disclosures=True,
        ).with_hash()
        self.grant = PolicyActivationGrant(
            project_id="project-a",
            grant_id="grant-1",
            policy_version_id="policy-1",
            policy_hash=self.policy.policy_hash,
            platform_account_id="account-a",
            actions=("publish",),
            actor="operator",
            created_at="2026-01-01T00:00:00Z",
            expires_at="2026-01-03T00:00:00Z",
        )

    def decide(self, **kwargs):
        policy = kwargs.pop("policy", self.policy)
        grant = kwargs.pop("grant", self.grant)
        defaults = dict(
            project_id="project-a",
            account_id="account-a",
            content_hash=CONTENT_HASH,
            content_kind="post",
            disclosures=("#ad",),
            live_intent=True,
            now=NOW,
            expected_content_hash=CONTENT_HASH,
        )
        defaults.update(kwargs)
        return evaluate_policy(policy, grant, **defaults)

    def test_grant_and_one_shot_live_intent_are_both_required(self):
        self.assertTrue(self.decide().allowed)
        self.assertEqual(self.decide(grant=None).reason, "grant_required")
        self.assertEqual(self.decide(live_intent=False).reason, "live_intent_required")

    def test_scheduler_ignores_cli_live_flag(self):
        self.assertEqual(
            self.decide(scheduler=True, live_intent=True).reason,
            "scheduler_live_disabled",
        )
        self.assertTrue(
            self.decide(scheduler=True, live_intent=False, scheduler_live_enabled=True).allowed
        )

    def test_policy_and_content_hash_bindings_are_fail_closed(self):
        self.assertEqual(self.decide(expected_content_hash="stale").reason, "stale_content_hash")
        changed = PolicyVersion(
            project_id=self.policy.project_id,
            policy_version_id=self.policy.policy_version_id,
            account_ids=self.policy.account_ids,
            actions=self.policy.actions,
            content_kinds=("recap",),
            max_posts_per_day=self.policy.max_posts_per_day,
            require_disclosures=self.policy.require_disclosures,
            policy_hash=self.policy.policy_hash,
        )
        # A stale stored hash cannot authorize a changed policy.
        self.assertEqual(
            evaluate_policy(
                changed,
                self.grant,
                project_id="project-a",
                account_id="account-a",
                content_hash=CONTENT_HASH,
                content_kind="post",
                disclosures=("#ad",),
                live_intent=True,
                now=NOW,
                expected_content_hash=CONTENT_HASH,
            ).reason,
            "stale_policy_hash",
        )

    def test_wrong_project_and_account_are_denied(self):
        self.assertEqual(self.decide(project_id="project-b").reason, "project_mismatch")
        self.assertEqual(self.decide(account_id="account-b").reason, "grant_account_mismatch")

    def test_expiry_and_revocation_are_denied(self):
        self.assertEqual(
            self.decide(now=datetime(2026, 1, 3, tzinfo=timezone.utc)).reason,
            "grant_expired",
        )
        revoked = PolicyActivationGrant(**{**self.grant.__dict__, "revoked_at": "2026-01-02T11:00:00Z"})
        self.assertEqual(self.decide(grant=revoked).reason, "grant_revoked")

    def test_daily_rate_and_disclosure_gates(self):
        self.assertEqual(self.decide(posts_today=2).reason, "daily_rate_exceeded")
        self.assertEqual(self.decide(disclosures=()).reason, "disclosure_required")

    def test_paid_copy_requires_an_audience_facing_label_even_when_policy_is_optional(self):
        optional = PolicyVersion(
            project_id=self.policy.project_id,
            policy_version_id="policy-optional",
            account_ids=self.policy.account_ids,
            actions=self.policy.actions,
            content_kinds=self.policy.content_kinds,
            max_posts_per_day=self.policy.max_posts_per_day,
            require_disclosures=False,
        ).with_hash()
        optional_grant = PolicyActivationGrant(
            project_id=self.grant.project_id,
            grant_id="grant-optional",
            policy_version_id=optional.policy_version_id,
            policy_hash=optional.policy_hash,
            platform_account_id=self.grant.platform_account_id,
            actions=self.grant.actions,
            actor=self.grant.actor,
            created_at=self.grant.created_at,
            expires_at=self.grant.expires_at,
        )
        self.assertEqual(
            self.decide(
                policy=optional,
                grant=optional_grant,
                disclosures=("internal note",),
                body="Affiliate link to the local tick",
            ).reason,
            "paid_undisclosed",
        )
        self.assertTrue(
            self.decide(
                policy=optional,
                grant=optional_grant,
                body="#affiliate Affiliate link to the local tick",
            ).allowed
        )

    def test_typed_account_and_content_must_belong_to_bindings(self):
        account = PlatformAccount(
            project_id="project-b",
            account_id="account-a",
            platform="x",
            handle="@a",
            host=None,
            credential_ref="env:X_TOKEN",
            status=AccountStatus.CONNECTED,
        )
        self.assertEqual(self.decide(account=account).reason, "account_mismatch")
        content = ContentRevision(
            project_id="project-b",
            content_id="content",
            revision_id="revision",
            body="hello",
            kind="post",
            status=ContentStatus.READY,
            source="test",
            source_digest="source",
            created_at="2026-01-01T00:00:00Z",
            content_hash=CONTENT_HASH,
        )
        self.assertEqual(self.decide(content=content).reason, "content_mismatch")

    def test_invalid_clock_fails_closed(self):
        self.assertEqual(self.decide(now=None).reason, "invalid_clock")
        self.assertEqual(self.decide(now="not-a-time").reason, "invalid_clock")


if __name__ == "__main__":
    unittest.main()
