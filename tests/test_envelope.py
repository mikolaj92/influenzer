from __future__ import annotations

import unittest
from unittest.mock import patch

from influenzer import effector, envelope


class EnvelopeTests(unittest.TestCase):
    def test_helpers_have_stable_envelope_shape(self) -> None:
        self.assertEqual(envelope.ok(), {"status": "ok", "ok": True, "mutated": False})
        self.assertEqual(
            envelope.planned(job="publish"),
            {"status": "planned", "ok": True, "mutated": False, "dry_run": True, "job": "publish"},
        )
        self.assertEqual(envelope.noop("already done")["status"], "noop")
        self.assertEqual(envelope.fail("denied")["ok"], False)

    def test_run_defaults_to_dry_run_and_normalizes_result(self) -> None:
        result = effector.run({"handler": "noop"})
        self.assertEqual(result["status"], "noop")
        self.assertTrue(result["ok"])
        self.assertFalse(result["mutated"])
        self.assertTrue(result["dry_run"])

    def test_unknown_handler_and_malformed_output_fail_closed(self) -> None:
        unknown = effector.run({"handler": "not-allowlisted"})
        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["reason"], "effector_boundary_failed")

        with patch.object(effector, "resolve", return_value=lambda request: ["not", "an", "object"]):
            malformed = effector.run({"handler": "noop"})
        self.assertFalse(malformed["ok"])
        self.assertEqual(malformed["reason"], "effector_boundary_failed")

    def test_dry_run_mutation_is_rejected(self) -> None:
        with patch.object(effector, "resolve", return_value=lambda request: {"status": "ok", "ok": True, "mutated": True}):
            result = effector.run({"handler": "noop", "input": {"dry_run": True}})
        self.assertFalse(result["ok"])
        self.assertEqual(result["reason"], "effector_boundary_failed")
        self.assertFalse(result["mutated"])

    def test_look_pass_angle_stay_dry_run_even_when_live_enabled(self) -> None:
        """Look/pass/angle cannot leave dry-run. live_enabled is not an override."""

        def planned(_request):
            return {"status": "ok", "ok": True, "mutated": False, "published": False}

        for name in ("score_brief", "look", "pass", "angle", "hom_pass", "hom_outbox"):
            with self.subTest(handler=name):
                with patch.object(effector, "resolve", return_value=planned):
                    result = effector.run(
                        {
                            "handler": name,
                            "input": {"dry_run": False, "live_enabled": True},
                            "config": {"dry_run": False, "scheduler_live_enabled": True},
                            "dry_run": False,
                        }
                    )
                self.assertTrue(result["ok"], result)
                self.assertTrue(result["dry_run"])
                self.assertFalse(result["mutated"])
                self.assertFalse(result.get("published", False))

    def test_secret_keys_and_credential_references_are_redacted(self) -> None:
        secret = "sentinel-secret"
        with patch.object(
            effector,
            "resolve",
            return_value=lambda request: {
                "status": "ok",
                "ok": True,
                "mutated": False,
                "api_token": secret,
                "credential_ref": "env:INFLUENZER_TOKEN",
                "message": f"token={secret}",
            },
        ):
            result = effector.run({"handler": "noop", "config": {"credential_ref": "env:INFLUENZER_TOKEN"}})
        self.assertNotIn(secret, str(result))
        self.assertEqual(result["api_token"], "<redacted>")
        self.assertEqual(result["credential_ref"], "<redacted>")
        self.assertIn("<redacted>", result["message"])

    def test_score_brief_with_secret_fact_is_kill_not_almost_redacted(self) -> None:
        leak = "env:INFLUENZER_TOKEN"
        result = effector.run(
            {
                "handler": "score_brief",
                "input": {
                    "project_id": "app-1",
                    "brief_id": "b-secret",
                    "story_kind": "major",
                    "claims_ship": True,
                    "tryable": True,
                    "facts": [
                        {
                            "text": f"docs mention {leak}",
                            "artifact_url": "https://github.com/mikolaj92/influenzer/pull/12",
                        },
                        {"text": "strangers can click and run the demo today"},
                    ],
                },
            }
        )
        self.assertTrue(result["ok"], result)
        self.assertEqual(result["verdict"], "kill")
        self.assertEqual(result["reason"], "secret")
        self.assertIsNone(result.get("arena"))
        self.assertIsNone(result.get("draft_id"))
        self.assertNotIn("body", result)
        self.assertFalse(result.get("published", False))
        self.assertFalse(result["mutated"])
        self.assertNotIn(leak, str(result))


if __name__ == "__main__":
    unittest.main()
