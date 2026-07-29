"""Dry-run/contract shapes shared by platform adapters."""

from __future__ import annotations

from typing import Any, Mapping

from influenzer.adapters.base import AdapterRequest, AdapterResult
from influenzer.envelope import fail, planned, result

# Official API selection notes for v1 dry-run (re-verify at live spike).
PLATFORM_CONTRACTS: dict[str, dict[str, Any]] = {
    "bluesky": {
        "official_api": "AT Protocol createRecord app.bsky.feed.post",
        "spike_candidates": ("goat", "atproto"),
        "capabilities": ("text", "images", "readback"),
        "host_required": False,
        "media_limit": 4,
        "max_body_chars": 300,
        "readback_kind": "at_uri",
    },
    "mastodon": {
        "official_api": "Mastodon REST POST /api/v1/statuses",
        "spike_candidates": ("Mastodon.py==2.2.1@halcy/Mastodon.py",),
        "capabilities": ("text", "images", "readback"),
        "host_required": True,
        "media_limit": 4,
        "max_body_chars": 500,
        "readback_kind": "status_url",
    },
    "x": {
        "official_api": "X API v2 POST /2/tweets",
        "spike_candidates": ("xurl", "tweepy"),
        "capabilities": ("text", "images", "readback"),
        "host_required": False,
        "media_limit": 4,
        "max_body_chars": 280,
        "readback_kind": "tweet_id",
    },
    "linkedin": {
        "official_api": "LinkedIn UGC/Posts API",
        "spike_candidates": ("thin HTTPS", "crosspost substrate scored only"),
        "capabilities": ("text", "images", "readback"),
        "host_required": False,
        "media_limit": 9,
        "max_body_chars": 3000,
        "readback_kind": "share_urn",
    },
    "instagram": {
        "official_api": "Meta Instagram Graph content publishing",
        "spike_candidates": ("thin HTTPS",),
        "capabilities": ("text", "images", "readback"),
        "host_required": False,
        "media_limit": 10,
        "max_body_chars": 2200,
        "readback_kind": "media_id",
        "meta_family": True,
    },
    "facebook_pages": {
        "official_api": "Meta Graph Page feed",
        "spike_candidates": ("thin HTTPS",),
        "capabilities": ("text", "images", "readback"),
        "host_required": False,
        "media_limit": 10,
        "max_body_chars": 63206,
        "readback_kind": "post_id",
        "meta_family": True,
    },
}


def validate_request(request: AdapterRequest, platform: str) -> AdapterResult | None:
    contract = PLATFORM_CONTRACTS[platform]
    if request.platform != platform:
        return fail(f"handler/platform mismatch: {request.platform}", failure_class="terminal")
    if not request.body.strip():
        return fail("body must not be empty", failure_class="terminal")
    if not request.operation_key:
        return fail("operation_key required", failure_class="terminal")
    if not request.project_id or not request.account_id:
        return fail("project_id and account_id required", failure_class="terminal")
    if contract["host_required"] and not request.host:
        return fail(f"{platform} requires account host", failure_class="terminal")
    if len(request.body) > int(contract["max_body_chars"]):
        return fail(
            f"body exceeds {platform} max_body_chars={contract['max_body_chars']}",
            failure_class="terminal",
            retry_safe=False,
        )
    if len(request.media) > int(contract["media_limit"]):
        return fail(
            f"media exceeds {platform} media_limit={contract['media_limit']}",
            failure_class="terminal",
            retry_safe=False,
        )
    for item in request.media:
        if not isinstance(item, str) or not item.startswith(("artifact:sha256:", "https://")):
            return fail(
                "media refs must be artifact:sha256:... or https://...",
                failure_class="terminal",
            )
    if not request.dry_run:
        return fail(
            f"{platform} live path not enabled in this build; dry-run only",
            failure_class="terminal",
            retry_safe=False,
        )
    return None


def planned_create(request: AdapterRequest, platform: str, *, planned_id: str) -> AdapterResult:
    contract = PLATFORM_CONTRACTS[platform]
    return planned(
        platform=platform,
        project_id=request.project_id,
        account_id=request.account_id,
        operation_key=request.operation_key,
        planned_id=planned_id,
        body_chars=len(request.body),
        media_count=len(request.media),
        media=list(request.media),
        capabilities=list(contract["capabilities"]),
        official_api=contract["official_api"],
        spike_candidates=list(contract["spike_candidates"]),
        readback={
            "kind": contract["readback_kind"],
            "planned_id": planned_id,
            "reconcile": "read_only",
        },
        rate={
            "retry_safe": False,
            "idempotency_key": request.operation_key,
        },
        access={
            "credential_ref_required": True,
            "credential_ref_present": request.credential_ref is not None,
            "host": request.host,
            "host_required": contract["host_required"],
        },
        meta_family=bool(contract.get("meta_family", False)),
    )


def readback_probe(request: AdapterRequest, platform: str, provider_id: str) -> AdapterResult:
    """Read-only reconcile shape. Live readback is rejected until Wave 4 canaries."""
    if not request.dry_run:
        return fail(
            f"{platform} live readback not enabled in this build",
            failure_class="terminal",
            retry_safe=False,
        )
    contract = PLATFORM_CONTRACTS[platform]
    return result(
        status="ok",
        ok=True,
        mutated=False,
        dry_run=True,
        platform=platform,
        operation="readback",
        provider_id=provider_id,
        readback_kind=contract["readback_kind"],
        found=None,
        reason="dry-run readback probe only",
    )


def assert_contract_result(out: Mapping[str, Any], platform: str) -> None:
    """Raise AssertionError if a dry-run create result misses required fields."""
    required = (
        "status",
        "ok",
        "mutated",
        "dry_run",
        "platform",
        "planned_id",
        "capabilities",
        "official_api",
        "readback",
        "rate",
        "access",
        "operation_key",
    )
    missing = [key for key in required if key not in out]
    if missing:
        raise AssertionError(f"{platform} missing contract fields: {missing}")
    if out.get("status") != "planned" or out.get("mutated") is not False or out.get("ok") is not True:
        raise AssertionError(f"{platform} invalid planned envelope: {out}")
    if out.get("platform") != platform:
        raise AssertionError(f"{platform} platform field mismatch")
    if "reconcile" not in (out.get("readback") or {}):
        raise AssertionError(f"{platform} readback missing reconcile")
