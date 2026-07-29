"""Run platform adapters as isolated child processes with strict stdout JSON."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping, Sequence

from influenzer.adapters.base import AdapterRequest
from influenzer.adapters.fake_provider import normalize_subprocess_output
from influenzer.envelope import fail

DEFAULT_DEADLINE_S = 5.0
DEFAULT_MAX_STDOUT = 64_000
DEFAULT_MAX_STDERR = 16_000
CHILD_MODULE = "influenzer.adapters.child_worker"


def request_to_dict(request: AdapterRequest) -> dict[str, Any]:
    return {
        "platform": request.platform,
        "project_id": request.project_id,
        "account_id": request.account_id,
        "body": request.body,
        "operation_key": request.operation_key,
        "dry_run": request.dry_run,
        "host": request.host,
        "media": list(request.media),
        "credential_ref": request.credential_ref,
    }


def run_adapter_subprocess(
    request: AdapterRequest,
    *,
    base_url: str,
    scripted: list[Mapping[str, Any]] | None = None,
    deadline_s: float = DEFAULT_DEADLINE_S,
    max_stdout: int = DEFAULT_MAX_STDOUT,
    max_stderr: int = DEFAULT_MAX_STDERR,
    env: Mapping[str, str] | None = None,
    child_argv: Sequence[str] | None = None,
    stdin_payload: bytes | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Spawn child worker; require exactly one JSON object on stdout.

    ``child_argv`` is test-only injection for deterministic timeout/malformed
    output cases. Production callers leave it None.
    """
    payload = {
        "request": request_to_dict(request),
        "base_url": base_url,
        "scripted": list(scripted or []),
        "deadline_ms": int(deadline_s * 1000),
    }
    child_env = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHONPATH": os.environ.get("PYTHONPATH", str(Path.cwd())),
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if env:
        child_env.update({k: str(v) for k, v in env.items()})

    argv = list(child_argv) if child_argv is not None else [sys.executable, "-m", CHILD_MODULE]
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=child_env,
        cwd=str(Path.cwd()),
    )
    if stdin_payload is None:
        raw_in = json.dumps(payload, sort_keys=True).encode("utf-8")
    elif isinstance(stdin_payload, (bytes, bytearray)):
        raw_in = bytes(stdin_payload)
    else:
        raw_in = json.dumps(stdin_payload, sort_keys=True).encode("utf-8")

    try:
        stdout, stderr = proc.communicate(raw_in, timeout=deadline_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        try:
            stdout, stderr = proc.communicate(timeout=1)
        except Exception:
            stdout, stderr = b"", b""
        return fail(
            "adapter subprocess deadline exceeded",
            failure_class="timeout",
            retry_safe=True,
            returncode=-1,
            stdout_bytes=len(stdout or b""),
            stderr_bytes=len(stderr or b""),
            killed=True,
        )

    if len(stdout) > max_stdout:
        return fail(
            "adapter stdout exceeds max size",
            failure_class="permanent",
            retry_safe=False,
            stdout_bytes=len(stdout),
        )
    if len(stderr) > max_stderr:
        return fail(
            "adapter stderr exceeds max size",
            failure_class="permanent",
            retry_safe=False,
            stderr_bytes=len(stderr),
        )

    text = stdout.decode("utf-8", errors="replace").strip()
    if not text:
        return fail(
            "empty adapter stdout",
            failure_class="permanent",
            retry_safe=False,
            returncode=proc.returncode,
            stderr=stderr.decode("utf-8", errors="replace")[:500],
        )
    try:
        decoder = json.JSONDecoder()
        data, idx = decoder.raw_decode(text)
        trailing = text[idx:].strip()
        if trailing:
            return fail(
                "adapter stdout contained multiple JSON values",
                failure_class="multi_result",
                retry_safe=False,
            )
    except json.JSONDecodeError:
        return fail(
            "adapter stdout is not JSON",
            failure_class="permanent",
            retry_safe=False,
            stderr=stderr.decode("utf-8", errors="replace")[:500],
        )

    normalized = normalize_subprocess_output(json.dumps(data))
    if (
        not normalized.get("ok")
        and normalized.get("status") == "failed"
        and "missing" in str(normalized.get("reason", ""))
    ):
        return normalized
    if not isinstance(data, Mapping):
        return fail("adapter stdout must be object", failure_class="permanent", retry_safe=False)
    out = dict(data)
    out.setdefault("subprocess", True)
    out.setdefault("returncode", proc.returncode)
    out.setdefault("stderr_bytes", len(stderr))
    if b"Bearer sk-" in stderr or b"api_key=" in stderr:
        return fail(
            "secret material on adapter stderr",
            failure_class="secret_leak",
            retry_safe=False,
        )
    if request.dry_run and out.get("mutated") is True:
        return fail("dry-run subprocess claimed mutation", failure_class="terminal", retry_safe=False)
    return out
