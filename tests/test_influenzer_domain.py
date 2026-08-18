from __future__ import annotations

import unittest

from influenzer.domain import (
    AccountStatus,
    ContentRevision,
    ContentStatus,
    DomainError,
    PlanStatus,
    PlatformAccount,
    PARKED_DOMAIN_REASON,
    Project,
    PublishPlan,
    assert_same_project,
    looks_like_parked_domain,
    parked_domain_reason,
    transition_plan,
)


class ProjectProfileTests(unittest.TestCase):
    def test_each_app_and_builder_owns_an_isolated_profile(self) -> None:
        app = Project.create(
            project_id="app-1",
            slug="my-app",
            name="My App",
            display_name="My App",
            voice="product voice",
            audience="customers",
            maintainer="mikolaj92",
            kind="app",
        )
        builder = Project.create(
            project_id="builder-1",
            slug="mikolaj",
            name="Mikolaj",
            display_name="Mikolaj",
            voice="builder voice",
            audience="builders",
            maintainer="mikolaj92",
            kind="builder",
        )
        self.assertNotEqual(app.brand.profile_hash, builder.brand.profile_hash)
        self.assertEqual(app.brand.project_id, app.project_id)
        self.assertEqual(builder.brand.project_id, builder.project_id)
        with self.assertRaises(DomainError):
            assert_same_project(app.project_id, builder.brand.project_id)

    def test_plaintext_credential_reference_is_rejected(self) -> None:
        with self.assertRaises(DomainError):
            PlatformAccount(
                project_id="app-1",
                account_id="x-1",
                platform="x",
                handle="@app",
                host=None,
                credential_ref="secret.txt",
                status=AccountStatus.DISCONNECTED,
            )

    def test_plan_transition_allows_schedule_cancel(self) -> None:
        plan = PublishPlan(
            project_id="app-1",
            plan_id="p",
            content_revision_id="r",
            content_hash="h",
            platform_account_id="a",
            platform="x",
            body="hello",
            status=PlanStatus.SCHEDULED,
            scheduled_at=None,
            created_at="2026-01-01T00:00:00Z",
            operation_key="op",
        )
        cancelled = transition_plan(plan, PlanStatus.CANCELLED)
        self.assertEqual(cancelled.status, PlanStatus.CANCELLED)
        with self.assertRaises(DomainError):
            transition_plan(plan, PlanStatus.SUCCEEDED)

    def test_parked_domain_is_not_a_website(self) -> None:
        parked = (
            "This domain is parked.",
            "Example.com is for sale.",
            "Buy this domain today.",
            "Registrar placeholder page.",
            "Coming soon from your hosting provider.",
            "Parking page by the host.",
            "Zaparkowana domena na sprzedaż.",
            "Placeholder od rejestratora.",
        )
        for text in parked:
            with self.subTest(text=text):
                self.assertTrue(looks_like_parked_domain(text))
                self.assertEqual(parked_domain_reason(text), PARKED_DOMAIN_REASON)

        for text in (
            "Our product is coming soon.",
            "The host runs the application.",
            "Parking spaces near the office are full.",
            "A domain model is immutable.",
            "Produkt wkrótce dostępny.",
        ):
            with self.subTest(text=text):
                self.assertFalse(looks_like_parked_domain(text))
                self.assertIsNone(parked_domain_reason(text))

    def test_content_hash_changes_with_body(self) -> None:
        base = dict(
            project_id="app-1",
            content_id="c",
            revision_id="r",
            kind="post",
            status=ContentStatus.DRAFT,
            source="manual",
            source_digest="src",
            created_at="2026-01-01T00:00:00Z",
        )
        one = ContentRevision(body="one", **base).with_hash()
        two = ContentRevision(body="two", **base).with_hash()
        self.assertNotEqual(one.content_hash, two.content_hash)


if __name__ == "__main__":
    unittest.main()
