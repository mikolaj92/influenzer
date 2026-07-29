"""In-process fake provider for dry-run/contract conformance (no network)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Mapping

from influenzer.envelope import fail, result

CONTRACT_SCHEMA_VERSION = 1

FAILURE_TAXONOMY = frozenset(
    {
        "rate_limited",
        "auth_expired",
        "permanent",
        "pre_send_validation",
        "ambiguous",
        "multi_result",
        "secret_leak",
        "timeout",
        "not_found",
    }
)


@dataclass
class FakeCall:
    method: str
    path: str
    body: Mapping[str, Any]
    headers: Mapping[str, str]
    digest: str


@dataclass
class FakeProvider:
    """Scripted HTTP-ish provider. Adapters never import real SDKs in dry-run tests."""

    platform: str
    scripted: list[dict[str, Any]] = field(default_factory=list)
    calls: list[FakeCall] = field(default_factory=list)
    deadline_ms: int = 5_000
    max_output_bytes: int = 64_000

    def enqueue(self, response: Mapping[str, Any]) -> None:
        self.scripted.append(dict(response))

    def request(
        self,
        *,
        method: str,
        path: str,
        body: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        deadline_ms: int | None = None,
    ) -> dict[str, Any]:
        payload = dict(body or {})
        hdrs = dict(headers or {})
        # Never accept raw secrets in headers/body for contract tests.
        blob = json.dumps({"m": method, "p": path, "b": payload, "h": hdrs}, sort_keys=True)
        if any(token in blob.lower() for token in ("bearer sk-", "api_key=", "password=")):
            return fail(
                "secret material in provider request",
                failure_class="secret_leak",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
            )
        digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        self.calls.append(FakeCall(method=method, path=path, body=payload, headers=hdrs, digest=digest))
        if deadline_ms is not None and deadline_ms > self.deadline_ms:
            return fail(
                "deadline exceeds provider budget",
                failure_class="timeout",
                retry_safe=True,
                schema_version=CONTRACT_SCHEMA_VERSION,
            )
        if not self.scripted:
            return fail(
                "no scripted provider response",
                failure_class="permanent",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
            )
        raw = self.scripted.pop(0)
        encoded = json.dumps(raw, sort_keys=True).encode("utf-8")
        if len(encoded) > self.max_output_bytes:
            return fail(
                "provider output exceeds max_output_bytes",
                failure_class="permanent",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
            )
        status = int(raw.get("http_status", 200))
        failure_class = raw.get("failure_class")
        if failure_class is not None and failure_class not in FAILURE_TAXONOMY:
            return fail(
                f"unknown failure_class: {failure_class}",
                failure_class="permanent",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
            )
        if status == 429 or failure_class == "rate_limited":
            return fail(
                "rate limited",
                failure_class="rate_limited",
                retry_safe=True,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
            )
        if status in (401, 403) or failure_class == "auth_expired":
            return fail(
                "auth expired or forbidden",
                failure_class="auth_expired",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
            )
        if status >= 500 or failure_class == "ambiguous":
            return result(
                status="unknown",
                ok=False,
                mutated=False,
                failure_class="ambiguous",
                reason="ambiguous provider outcome",
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
                retry_safe=False,
            )
        if failure_class == "multi_result":
            return fail(
                "provider returned multiple results for one operation_key",
                failure_class="multi_result",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
            )
        if failure_class == "pre_send_validation" or status == 400:
            return fail(
                str(raw.get("error") or "pre-send validation"),
                failure_class="pre_send_validation",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
            )
        if failure_class == "not_found" or status == 404:
            return result(
                status="ok",
                ok=True,
                mutated=False,
                found=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
                provider_id=None,
            )
        if status >= 400 or failure_class == "permanent":
            return fail(
                str(raw.get("error") or f"http {status}"),
                failure_class="permanent",
                retry_safe=False,
                schema_version=CONTRACT_SCHEMA_VERSION,
                request_digest=digest,
            )
        provider_id = raw.get("provider_id") or raw.get("id")
        provider_url = raw.get("provider_url") or raw.get("url")
        return result(
            status="ok",
            ok=True,
            mutated=bool(raw.get("mutated", method.upper() != "GET")),
            schema_version=CONTRACT_SCHEMA_VERSION,
            request_digest=digest,
            provider_id=provider_id,
            provider_url=provider_url,
            payload_digest=hashlib.sha256(encoded).hexdigest(),
            platform=self.platform,
        )


def normalize_subprocess_output(raw: bytes | str, *, max_bytes: int = 64_000) -> dict[str, Any]:
    """Strict object normalization for adapter child output."""
    if isinstance(raw, bytes):
        if len(raw) > max_bytes:
            return fail("adapter output too large", failure_class="permanent", retry_safe=False)
        text = raw.decode("utf-8", errors="replace")
    else:
        text = raw
        if len(text.encode("utf-8")) > max_bytes:
            return fail("adapter output too large", failure_class="permanent", retry_safe=False)
    text = text.strip()
    if not text:
        return fail("empty adapter output", failure_class="permanent", retry_safe=False)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return fail("adapter output is not JSON", failure_class="permanent", retry_safe=False)
    if not isinstance(data, Mapping):
        return fail("adapter output must be object", failure_class="permanent", retry_safe=False)
    out = dict(data)
    for key in ("status", "ok", "mutated"):
        if key not in out:
            return fail(f"adapter output missing {key}", failure_class="permanent", retry_safe=False)
    return out
