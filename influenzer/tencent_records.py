"""Exact application records in an isolated TencentDB L0 scope, not extracted memory.

L0 add has no compare-and-set or caller ID: local journal claims remain the
execution authority. Writes are content-addressed, read-verified and never
blindly retried. Assistant-only records do not trigger user-round extraction.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from urllib.parse import urlsplit

import httpx
from pydantic import BaseModel, ConfigDict, Field, field_validator


class TencentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    url: str
    team_id: str = Field(min_length=1)
    agent_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    service_id: str = "default"
    user_key_env: str = "TDAI_MEMORY_USER_KEY"
    api_key_env: str = "TDAI_MEMORY_API_KEY"

    @field_validator("url")
    @classmethod
    def gateway_origin(cls, value: str) -> str:
        url = urlsplit(value)
        if url.scheme not in {"http", "https"} or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in {"", "/"}:
            raise ValueError("tencent_gateway_requires_http_origin_without_credentials")
        return value.rstrip("/")


def retain_record(config: dict, payload: dict) -> dict:
    """Report storage independently of model status; retain the journal result on failure."""
    cfg = TencentConfig.model_validate(config)
    try:
        return {**TencentRecords(cfg).put(payload), "status": "confirmed"}
    except (httpx.HTTPError, ValueError, TypeError, KeyError, OSError) as exc:
        return {"backend": "tencentdb", "status": "unconfirmed", "reason": "record_persistence_failed_no_retry",
                "failure_class": type(exc).__name__}


class TencentRecords:
    def __init__(self, config: TencentConfig, *, transport: httpx.BaseTransport | None = None):
        self.config = config
        self.transport = transport

    def _post(self, path: str, body: dict) -> dict:
        cfg = self.config
        headers = {"x-tdai-service-id": cfg.service_id, "x-tdai-user-key": os.environ[cfg.user_key_env],
                   "Authorization": "Bearer " + os.environ[cfg.api_key_env]}
        scope = {"team_id": cfg.team_id, "agent_id": cfg.agent_id, "user_id": cfg.user_id}
        with httpx.Client(transport=self.transport, timeout=30, trust_env=False, follow_redirects=False) as client:
            response = client.post(cfg.url.rstrip("/") + path, json={**scope, **body}, headers=headers)
            response.raise_for_status()
            envelope = response.json()
        if envelope["code"] != 0:
            raise ValueError("tencent_request_rejected")
        return envelope["data"]

    def get(self, digest: str) -> dict | None:
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ValueError("invalid_record_digest")
        data = self._post("/v3/conversation/query", {"session_id": "influenzer:record:" + digest, "limit": 100, "offset": 0})
        rows = data["messages"]
        if not rows and data["total"] == 0:
            return None
        if data["total"] != len(rows):
            raise ValueError("tencent_record_incomplete")
        chunks = {}
        total = None
        for row in rows:
            chunk = json.loads(row["content"])
            if row["role"] != "assistant" or chunk["schema"] != "influenzer-record-v1" or chunk["digest"] != digest:
                raise ValueError("tencent_record_scope_or_identity_mismatch")
            if total is not None and total != chunk["count"]:
                raise ValueError("tencent_record_chunk_count_mismatch")
            total = chunk["count"]
            if chunk["index"] in chunks and chunks[chunk["index"]] != chunk["data"]:
                raise ValueError("tencent_record_conflicting_chunks")
            chunks[chunk["index"]] = chunk["data"]
        if total is None or set(chunks) != set(range(total)):
            raise ValueError("tencent_record_incomplete")
        raw = base64.b64decode("".join(chunks[i] for i in range(total)), validate=True)
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("tencent_record_digest_mismatch")
        return json.loads(raw)

    def put(self, payload: dict) -> dict:
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        digest = hashlib.sha256(raw).hexdigest()
        receipt = {"backend": "tencentdb", "digest": digest, "agent_id": self.config.agent_id,
                   "session_id": "influenzer:record:" + digest}
        canonical = json.loads(raw)
        previous = self.get(digest)
        if previous is not None:
            if previous != canonical:
                raise ValueError("tencent_record_collision")
            return receipt
        encoded = base64.b64encode(raw).decode()
        parts = [encoded[i:i + 6000] for i in range(0, len(encoded), 6000)]
        if len(parts) > 100:
            raise ValueError("tencent_record_too_large")
        messages = [{"role": "assistant", "content": json.dumps({"schema": "influenzer-record-v1", "digest": digest,
                     "index": i, "count": len(parts), "data": text})} for i, text in enumerate(parts)]
        response = self._post("/v3/conversation/add", {"session_id": receipt["session_id"], "messages": messages})
        if response["total_count"] != len(parts) or len(response["accepted_ids"]) != len(parts):
            raise ValueError("tencent_write_unconfirmed")
        if self.get(digest) != canonical:
            raise ValueError("tencent_readback_mismatch")
        return receipt
