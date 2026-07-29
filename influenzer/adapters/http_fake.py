"""Loopback HTTP fake provider for adapter contract tests (stdlib only)."""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse


@dataclass
class RecordedHTTPCall:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class FakeHTTPServer:
    """127.0.0.1-only scripted HTTP server. One scripted response per request."""

    scripted: list[dict[str, Any]] = field(default_factory=list)
    calls: list[RecordedHTTPCall] = field(default_factory=list)
    _server: ThreadingHTTPServer | None = field(default=None, init=False, repr=False)
    _thread: threading.Thread | None = field(default=None, init=False, repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def enqueue(self, response: dict[str, Any]) -> None:
        with self._lock:
            self.scripted.append(dict(response))

    @property
    def base_url(self) -> str:
        if self._server is None:
            raise RuntimeError("server not started")
        host, port = self._server.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "FakeHTTPServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A003
                return

            def _read_body(self) -> bytes:
                length = int(self.headers.get("Content-Length") or 0)
                return self.rfile.read(length) if length else b""

            def _dispatch(self) -> None:
                body = self._read_body()
                headers = {k.lower(): v for k, v in self.headers.items()}
                with owner._lock:
                    owner.calls.append(
                        RecordedHTTPCall(
                            method=self.command,
                            path=self.path,
                            headers=headers,
                            body=body,
                        )
                    )
                    # Secret material must never appear on the wire in contract tests.
                    blob = body.decode("utf-8", errors="replace").lower() + json.dumps(headers, sort_keys=True).lower()
                    if "bearer sk-" in blob or "api_key=" in blob or "password=" in blob:
                        payload = {
                            "http_status": 400,
                            "failure_class": "secret_leak",
                            "error": "secret material in provider request",
                        }
                    elif not owner.scripted:
                        payload = {
                            "http_status": 500,
                            "failure_class": "permanent",
                            "error": "no scripted provider response",
                        }
                    else:
                        payload = owner.scripted.pop(0)
                status = int(payload.get("http_status", 200))
                raw = json.dumps(payload, sort_keys=True).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_GET(self) -> None:  # noqa: N802
                self._dispatch()

            def do_POST(self) -> None:  # noqa: N802
                self._dispatch()

            def do_PUT(self) -> None:  # noqa: N802
                self._dispatch()

        # Bind loopback only.
        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        return self

    def stop(self) -> None:
        if self._server is not None:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        if self._thread is not None:
            self._thread.join(timeout=2)
            self._thread = None

    def __enter__(self) -> "FakeHTTPServer":
        return self.start()

    def __exit__(self, *_: Any) -> None:
        self.stop()
