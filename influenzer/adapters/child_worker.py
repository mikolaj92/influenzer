"""Child process entry: one JSON request on stdin, one JSON result on stdout."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from typing import Any, Mapping

from influenzer.adapters.base import AdapterRequest
from influenzer.adapters.contract import PLATFORM_CONTRACTS, planned_create, validate_request
from influenzer.envelope import fail, result


def _paths(platform: str) -> str:
    return {
        "bluesky": "/xrpc/com.atproto.repo.createRecord",
        "mastodon": "/api/v1/statuses",
        "x": "/2/tweets",
        "linkedin": "/v2/ugcPosts",
        "instagram": "/v19.0/me/media",
        "facebook_pages": "/v19.0/me/feed",
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


def _http_json(method: str, url: str, body: Mapping[str, Any] | None, headers: Mapping[str, str], timeout_s: float) -> dict[str, Any]:
    data = None if body is None else json.dumps(body, sort_keys=True).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    for key, value in headers.items():
        if value:
            req.add_header(key, value)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read()
            status = getattr(resp, "status", 200)
            payload = json.loads(raw.decode("utf-8")) if raw else {}
            return {"http_status": status, **(payload if isinstance(payload, dict) else {"body": payload})}
    except urllib.error.HTTPError as exc:
        raw = exc.read()
        try:
            payload = json.loads(raw.decode("utf-8")) if raw else {}
        except json.JSONDecodeError:
            payload = {"error": raw.decode("utf-8", errors="replace")}
        if not isinstance(payload, dict):
            payload = {"error": str(payload)}
        return {"http_status": exc.code, **payload}
    except Exception as exc:  # timeout, connection, etc.
        return {
            "http_status": 0,
            "failure_class": "ambiguous",
            "error": f"transport: {exc.__class__.__name__}",
        }


def _map_http(payload: Mapping[str, Any]) -> dict[str, Any]:
    status = int(payload.get("http_status") or 0)
    failure_class = payload.get("failure_class")
    if failure_class == "secret_leak" or status == 400 and "secret" in str(payload.get("error", "")).lower():
        return fail(str(payload.get("error") or "secret leak"), failure_class="secret_leak", retry_safe=False, schema_version=1)
    if status == 429 or failure_class == "rate_limited":
        return fail("rate limited", failure_class="rate_limited", retry_safe=True, schema_version=1)
    if status in (401, 403) or failure_class == "auth_expired":
        return fail("auth expired or forbidden", failure_class="auth_expired", retry_safe=False, schema_version=1)
    if failure_class == "multi_result":
        return fail("provider returned multiple results", failure_class="multi_result", retry_safe=False, schema_version=1)
    if failure_class == "pre_send_validation" or status == 400:
        return fail(str(payload.get("error") or "pre-send validation"), failure_class="pre_send_validation", retry_safe=False, schema_version=1)
    if status >= 500 or failure_class == "ambiguous" or status == 0:
        return result(
            status="unknown",
            ok=False,
            mutated=False,
            failure_class="ambiguous",
            reason=str(payload.get("error") or "ambiguous provider outcome"),
            schema_version=1,
            retry_safe=False,
        )
    if status >= 400 or failure_class == "permanent":
        return fail(str(payload.get("error") or f"http {status}"), failure_class="permanent", retry_safe=False, schema_version=1)
    return result(
        status="ok",
        ok=True,
        mutated=False,  # child is dry-run only in v1
        schema_version=1,
        provider_id=payload.get("provider_id") or payload.get("id"),
        provider_url=payload.get("provider_url") or payload.get("url"),
    )


def handle(message: Mapping[str, Any]) -> dict[str, Any]:
    req_raw = message.get("request") or {}
    if not isinstance(req_raw, Mapping):
        return fail("invalid request object", failure_class="pre_send_validation")
    try:
        request = AdapterRequest(
            platform=str(req_raw["platform"]),
            project_id=str(req_raw["project_id"]),
            account_id=str(req_raw["account_id"]),
            body=str(req_raw.get("body") or ""),
            operation_key=str(req_raw.get("operation_key") or ""),
            dry_run=bool(req_raw.get("dry_run", True)),
            host=req_raw.get("host"),
            media=tuple(req_raw.get("media") or ()),
            credential_ref=req_raw.get("credential_ref"),
        )
    except Exception as exc:
        return fail(f"invalid request fields: {exc}", failure_class="pre_send_validation")

    platform = request.platform
    if platform not in PLATFORM_CONTRACTS:
        return fail(f"unknown platform: {platform}", failure_class="permanent")

    err = validate_request(request, platform)
    if err is not None:
        return err

    base_url = str(message.get("base_url") or "").rstrip("/")
    if not base_url.startswith("http://127.0.0.1:") and not base_url.startswith("http://localhost:"):
        return fail("child worker only talks to loopback fake HTTP", failure_class="permanent")

    deadline_ms = int(message.get("deadline_ms") or 5000)
    timeout_s = max(0.1, deadline_ms / 1000.0)

    # Optional pre-seed via control path for multi-step scripts (parent usually enqueues on server).
    for item in message.get("scripted") or []:
        if isinstance(item, Mapping):
            _http_json("POST", f"{base_url}/__enqueue", item, {"x-control": "1"}, timeout_s)

    body = {
        "text": request.body,
        "operation_key": request.operation_key,
        "media": list(request.media),
        "account_id": request.account_id,
    }
    headers = {
        "x-operation-key": request.operation_key,
        "x-platform": platform,
        "x-credential-ref": request.credential_ref or "",
    }
    if request.host:
        headers["x-account-host"] = request.host

    http_payload = _http_json("POST", f"{base_url}{_paths(platform)}", body, headers, timeout_s)
    mapped = _map_http(http_payload)
    if mapped.get("status") in {"failed", "unknown"} or not mapped.get("ok", False):
        # If fake had no script and returned permanent empty, fall back to pure planned dry-run.
        if mapped.get("failure_class") == "permanent" and "no scripted" in str(mapped.get("reason", "")):
            return planned_create(request, platform, planned_id=_planned_id(platform, request))
        return mapped

    planned_id = str(mapped.get("provider_id") or _planned_id(platform, request))
    out = planned_create(request, platform, planned_id=planned_id)
    out["schema_version"] = 1
    out["subprocess"] = True
    out["http_status"] = http_payload.get("http_status")
    return out


def main() -> int:
    raw = sys.stdin.read()
    try:
        message = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        sys.stdout.write(json.dumps(fail("stdin is not JSON", failure_class="permanent"), sort_keys=True))
        return 2
    if not isinstance(message, Mapping):
        sys.stdout.write(json.dumps(fail("stdin must be object", failure_class="permanent"), sort_keys=True))
        return 2
    out = handle(message)
    # Exactly one JSON object, no trailing logs on stdout.
    sys.stdout.write(json.dumps(out, sort_keys=True, separators=(",", ":")))
    return 0 if out.get("ok") or out.get("status") in {"planned", "unknown"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
