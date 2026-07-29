"""Per-platform dry-run/contract handlers using FakeProvider protocol."""

from __future__ import annotations

from typing import Any

from influenzer.adapters.base import AdapterRequest, AdapterResult
from influenzer.adapters.contract import PLATFORM_CONTRACTS, planned_create, validate_request
from influenzer.adapters.fake_provider import FakeProvider
from influenzer.envelope import fail, result

# Process-local scriptable providers for contract tests. Live SDKs land later.
_PROVIDERS: dict[str, FakeProvider] = {}


def get_provider(platform: str) -> FakeProvider:
    if platform not in _PROVIDERS:
        _PROVIDERS[platform] = FakeProvider(platform=platform)
    return _PROVIDERS[platform]


def reset_providers() -> None:
    _PROVIDERS.clear()


def _paths(platform: str) -> dict[str, str]:
    return {
        "bluesky": "/xrpc/com.atproto.repo.createRecord",
        "mastodon": "/api/v1/statuses",
        "x": "/2/tweets",
        "linkedin": "/v2/ugcPosts",
        "instagram": "/v19.0/me/media",
        "facebook_pages": "/v19.0/me/feed",
    }[platform]


def _read_paths(platform: str) -> dict[str, str]:
    return {
        "bluesky": "/xrpc/com.atproto.repo.getRecord",
        "mastodon": "/api/v1/statuses/{id}",
        "x": "/2/tweets/{id}",
        "linkedin": "/v2/ugcPosts/{id}",
        "instagram": "/v19.0/{id}",
        "facebook_pages": "/v19.0/{id}",
    }[platform]


def _planned_id(platform: str, request: AdapterRequest) -> str:
    if platform == "bluesky":
        return f"at://did:plc:dryrun/app.bsky.feed.post/{request.operation_key}"
    if platform == "mastodon":
        return f"https://{request.host}/api/v1/statuses/dryrun-{request.operation_key}"
    if platform == "x":
        return f"x:tweet:dryrun:{request.operation_key}"
    if platform == "linkedin":
        return f"urn:li:share:dryrun-{request.operation_key}"
    if platform == "instagram":
        return f"ig:media:dryrun:{request.operation_key}"
    return f"fb:post:dryrun:{request.operation_key}"


def _publish(platform: str, request: AdapterRequest) -> AdapterResult:
    err = validate_request(request, platform)
    if err is not None:
        return err
    provider = get_provider(platform)
    # Dry-run contract path: plan first; if a scripted response exists, exercise taxonomy.
    if not provider.scripted:
        return planned_create(request, platform, planned_id=_planned_id(platform, request))
    body: dict[str, Any] = {
        "text": request.body,
        "operation_key": request.operation_key,
        "media": list(request.media),
        "account_id": request.account_id,
    }
    headers = {
        "x-operation-key": request.operation_key,
        "x-platform": platform,
        # credential_ref only — never a resolved secret
        "x-credential-ref": request.credential_ref or "",
    }
    if request.host:
        headers["x-account-host"] = request.host
    out = provider.request(method="POST", path=_paths(platform), body=body, headers=headers)
    if out.get("status") == "unknown":
        return out
    if not out.get("ok"):
        return out
    # Scripted success still stays dry-run for v1 adapters (no real mutation).
    planned_id = str(out.get("provider_id") or _planned_id(platform, request))
    base = planned_create(request, platform, planned_id=planned_id)
    base["request_digest"] = out.get("request_digest")
    base["payload_digest"] = out.get("payload_digest")
    base["schema_version"] = out.get("schema_version")
    return base


def _readback(platform: str, request: AdapterRequest, provider_id: str) -> AdapterResult:
    if not request.dry_run:
        return fail(
            f"{platform} live readback not enabled in this build",
            failure_class="terminal",
            retry_safe=False,
        )
    if not provider_id:
        return fail("provider_id required for readback", failure_class="pre_send_validation")
    provider = get_provider(platform)
    path = _read_paths(platform).format(id=provider_id)
    if not provider.scripted:
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
            schema_version=1,
        )
    out = provider.request(
        method="GET",
        path=path,
        body={"provider_id": provider_id, "operation_key": request.operation_key},
        headers={"x-platform": platform},
    )
    out["operation"] = "readback"
    out["dry_run"] = True
    out["mutated"] = False
    out["platform"] = platform
    return out


def bluesky_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("bluesky", request)


def bluesky_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("bluesky", request, provider_id)


def mastodon_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("mastodon", request)


def mastodon_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("mastodon", request, provider_id)


def x_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("x", request)


def x_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("x", request, provider_id)


def linkedin_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("linkedin", request)


def linkedin_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("linkedin", request, provider_id)


def instagram_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("instagram", request)


def instagram_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("instagram", request, provider_id)


def facebook_pages_publish(request: AdapterRequest) -> AdapterResult:
    return _publish("facebook_pages", request)


def facebook_pages_readback(request: AdapterRequest, provider_id: str) -> AdapterResult:
    return _readback("facebook_pages", request, provider_id)
