from __future__ import annotations

import unittest

from influenzer.adapters.base import AdapterRequest, run_adapter
from influenzer.adapters.contract import PLATFORM_CONTRACTS, assert_contract_result
from influenzer.adapters.platforms import (
    bluesky_readback,
    facebook_pages_readback,
    instagram_readback,
    linkedin_readback,
    mastodon_readback,
    x_readback,
)
from influenzer.adapters.registry import ADAPTERS, get_adapter

READBACK = {
    "bluesky": bluesky_readback,
    "mastodon": mastodon_readback,
    "x": x_readback,
    "linkedin": linkedin_readback,
    "instagram": instagram_readback,
    "facebook_pages": facebook_pages_readback,
}


class DryRunContractTests(unittest.TestCase):
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
            host=host,
            media=media,
            credential_ref="env:TOKEN",
        )

    def test_all_platforms_are_registered_with_contracts(self) -> None:
        self.assertEqual(set(ADAPTERS), set(PLATFORM_CONTRACTS))
        self.assertEqual(
            set(ADAPTERS),
            {"x", "bluesky", "mastodon", "linkedin", "instagram", "facebook_pages"},
        )

    def test_each_platform_dry_run_create_media_readback_contract(self) -> None:
        for platform, contract in PLATFORM_CONTRACTS.items():
            host = "mastodon.social" if contract["host_required"] else None
            media = ("artifact:sha256:" + "a" * 64,)
            out = run_adapter(
                get_adapter(platform),
                self._req(platform, host=host, media=media),
            )
            assert_contract_result(out, platform)
            self.assertEqual(out["media_count"], 1)
            self.assertIn("text", out["capabilities"])
            self.assertIn("images", out["capabilities"])
            self.assertIn("readback", out["capabilities"])
            self.assertTrue(out["official_api"])
            self.assertEqual(out["rate"]["idempotency_key"], f"op-{platform}")
            self.assertEqual(out["access"]["host_required"], contract["host_required"])
            self.assertEqual(out["readback"]["kind"], contract["readback_kind"])
            self.assertEqual(out["readback"]["reconcile"], "read_only")
            probe = READBACK[platform](self._req(platform, host=host), out["planned_id"])
            self.assertTrue(probe["ok"])
            self.assertFalse(probe["mutated"])
            self.assertEqual(probe["operation"], "readback")
            self.assertEqual(probe["provider_id"], out["planned_id"])

    def test_mastodon_requires_host(self) -> None:
        out = run_adapter(get_adapter("mastodon"), self._req("mastodon", host=None))
        self.assertFalse(out["ok"])
        self.assertIn("host", out["reason"])

    def test_body_and_media_limits(self) -> None:
        out = get_adapter("x")(self._req("x", body="x" * 281))
        self.assertFalse(out["ok"])
        self.assertIn("max_body_chars", out["reason"])
        too_many = tuple(f"artifact:sha256:{i:064d}" for i in range(5))
        out_media = get_adapter("x")(self._req("x", media=too_many))
        self.assertFalse(out_media["ok"])
        self.assertIn("media_limit", out_media["reason"])

    def test_invalid_media_ref_rejected(self) -> None:
        out = get_adapter("bluesky")(self._req("bluesky", media=("/tmp/secret.png",)))
        self.assertFalse(out["ok"])
        self.assertIn("media refs", out["reason"])

    def test_live_path_fails_closed_in_v1_dry_run_build(self) -> None:
        out = get_adapter("x")(self._req("x", dry_run=False))
        self.assertFalse(out["ok"])
        self.assertFalse(out["mutated"])
        self.assertIn("dry-run only", out["reason"])

    def test_meta_handlers_are_independent(self) -> None:
        ig = run_adapter(get_adapter("instagram"), self._req("instagram"))
        fb = run_adapter(get_adapter("facebook_pages"), self._req("facebook_pages"))
        assert_contract_result(ig, "instagram")
        assert_contract_result(fb, "facebook_pages")
        self.assertTrue(ig["meta_family"])
        self.assertTrue(fb["meta_family"])
        self.assertNotEqual(ig["planned_id"], fb["planned_id"])
        self.assertNotEqual(ig["official_api"], fb["official_api"])

    def test_empty_body_rejected(self) -> None:
        out = get_adapter("bluesky")(self._req("bluesky", body="   "))
        self.assertFalse(out["ok"])


if __name__ == "__main__":
    unittest.main()
