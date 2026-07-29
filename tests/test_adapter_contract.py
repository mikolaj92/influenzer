from __future__ import annotations

import json
import unittest
from pathlib import Path

from influenzer.adapters.base import AdapterRequest, run_adapter
from influenzer.adapters.contract import PLATFORM_CONTRACTS, assert_contract_result
from influenzer.adapters.fake_provider import (
    CONTRACT_SCHEMA_VERSION,
    FAILURE_TAXONOMY,
    normalize_subprocess_output,
)
from influenzer.adapters import platforms as plat
from influenzer.adapters.registry import ADAPTERS, get_adapter


READBACK = {
    "bluesky": plat.bluesky_readback,
    "mastodon": plat.mastodon_readback,
    "x": plat.x_readback,
    "linkedin": plat.linkedin_readback,
    "instagram": plat.instagram_readback,
    "facebook_pages": plat.facebook_pages_readback,
}

SPIKE_PATH = Path(__file__).resolve().parents[1] / "influenzer" / "adapters" / "spike_scores.json"


class AdapterContractConformanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.spikes = json.loads(SPIKE_PATH.read_text(encoding="utf-8"))

    def setUp(self) -> None:
        plat.reset_providers()

    def tearDown(self) -> None:
        plat.reset_providers()

    def _req(
        self,
        platform: str,
        *,
        host: str | None = None,
        dry_run: bool = True,
        body: str | None = None,
        media: tuple[str, ...] = (),
    ) -> AdapterRequest:
        return AdapterRequest(
            platform=platform,
            project_id="app-1",
            account_id=f"{platform}-1",
            body=body if body is not None else "shipping dry-run contract",
            operation_key=f"op-{platform}",
            dry_run=dry_run,
            host=host or ("mastodon.social" if platform == "mastodon" else None),
            media=media,
            credential_ref="env:TOKEN",
        )

    def test_platforms_match_contracts_registry_and_spike_evidence(self) -> None:
        self.assertEqual(set(ADAPTERS), set(PLATFORM_CONTRACTS))
        self.assertEqual(set(self.spikes["platforms"]), set(PLATFORM_CONTRACTS))
        self.assertEqual(self.spikes["schema_version"], 1)

    def test_each_platform_create_media_readback_and_selected_spike(self) -> None:
        for platform, contract in PLATFORM_CONTRACTS.items():
            with self.subTest(platform=platform):
                media = ("artifact:sha256:" + "ab" * 32,)
                out = run_adapter(get_adapter(platform), self._req(platform, media=media))
                assert_contract_result(out, platform)
                self.assertEqual(out["media_count"], 1)
                self.assertEqual(out["access"]["host_required"], contract["host_required"])
                self.assertEqual(out["readback"]["reconcile"], "read_only")
                selected = self.spikes["platforms"][platform]["selected"]
                candidates = " ".join(out["spike_candidates"])
                self.assertTrue(
                    any(selected.split()[0].lower() in c.lower() or selected.lower() in c.lower() for c in out["spike_candidates"])
                    or selected.lower() in candidates.lower(),
                    f"{platform}: selected {selected!r} not reflected in {out['spike_candidates']}",
                )
                evidence = self.spikes["platforms"][platform]
                self.assertTrue(evidence["candidates"])
                chosen = next(c for c in evidence["candidates"] if c["name"] == selected or selected.startswith(c["name"]))
                self.assertGreaterEqual(chosen["total"], 0.7)
                self.assertTrue(chosen["source"])
                self.assertTrue(chosen["license"])
                probe = READBACK[platform](self._req(platform), out["planned_id"])
                self.assertTrue(probe["ok"])
                self.assertFalse(probe["mutated"])
                self.assertEqual(probe["operation"], "readback")

    def test_failure_taxonomy_via_fake_provider(self) -> None:
        cases = [
            ("rate_limited", {"http_status": 429}),
            ("auth_expired", {"http_status": 401}),
            ("permanent", {"http_status": 422, "error": "rejected"}),
            ("pre_send_validation", {"failure_class": "pre_send_validation", "error": "bad media"}),
            ("ambiguous", {"http_status": 503}),
            ("multi_result", {"failure_class": "multi_result"}),
        ]
        for platform in PLATFORM_CONTRACTS:
            for failure_class, scripted in cases:
                with self.subTest(platform=platform, failure=failure_class):
                    plat.reset_providers()
                    provider = plat.get_provider(platform)
                    provider.enqueue(scripted)
                    out = get_adapter(platform)(self._req(platform))
                    if failure_class == "ambiguous":
                        self.assertEqual(out["status"], "unknown")
                        self.assertEqual(out["failure_class"], "ambiguous")
                    else:
                        self.assertFalse(out["ok"])
                        self.assertEqual(out["failure_class"], failure_class)
                    self.assertIn(out["failure_class"], FAILURE_TAXONOMY)
                    self.assertEqual(out.get("schema_version"), CONTRACT_SCHEMA_VERSION)
                    self.assertIn("request_digest", out)
                    self.assertEqual(len(provider.calls), 1)

    def test_secret_material_in_request_is_rejected(self) -> None:
        provider = plat.get_provider("x")
        token = "Bearer " + "sk" + "-" + "this-is-not-allowed-123456"
        out = provider.request(
            method="POST",
            path="/2/tweets",
            body={"text": "hi"},
            headers={"Authorization": token},
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_class"], "secret_leak")

    def test_deadline_and_output_bounds(self) -> None:
        provider = plat.get_provider("bluesky")
        provider.deadline_ms = 100
        out = provider.request(method="GET", path="/x", deadline_ms=500)
        self.assertEqual(out["failure_class"], "timeout")
        provider2 = plat.get_provider("mastodon")
        provider2.max_output_bytes = 16
        provider2.enqueue({"http_status": 200, "provider_id": "x" * 100})
        out2 = provider2.request(method="GET", path="/y")
        self.assertFalse(out2["ok"])
        self.assertIn("max_output_bytes", out2["reason"])

    def test_subprocess_output_normalization(self) -> None:
        good = normalize_subprocess_output(json.dumps({"status": "planned", "ok": True, "mutated": False}))
        self.assertTrue(good["ok"])
        self.assertFalse(normalize_subprocess_output(b"not-json")["ok"])
        self.assertFalse(normalize_subprocess_output(json.dumps([1, 2, 3]))["ok"])
        self.assertFalse(normalize_subprocess_output(json.dumps({"status": "ok"}))["ok"])
        huge = json.dumps({"status": "ok", "ok": True, "mutated": False, "pad": "x" * 100}).encode()
        self.assertFalse(normalize_subprocess_output(huge, max_bytes=32)["ok"])

    def test_live_create_and_readback_fail_closed(self) -> None:
        for platform in PLATFORM_CONTRACTS:
            with self.subTest(platform=platform):
                create = get_adapter(platform)(self._req(platform, dry_run=False))
                self.assertFalse(create["ok"])
                self.assertFalse(create["mutated"])
                rb = READBACK[platform](self._req(platform, dry_run=False), "id-1")
                self.assertFalse(rb["ok"])
                self.assertIn("live readback not enabled", rb["reason"])

    def test_meta_handlers_independent_permissions_payloads(self) -> None:
        ig = run_adapter(get_adapter("instagram"), self._req("instagram"))
        fb = run_adapter(get_adapter("facebook_pages"), self._req("facebook_pages"))
        assert_contract_result(ig, "instagram")
        assert_contract_result(fb, "facebook_pages")
        self.assertNotEqual(ig["official_api"], fb["official_api"])
        self.assertTrue(ig["meta_family"] and fb["meta_family"])


if __name__ == "__main__":
    unittest.main()
