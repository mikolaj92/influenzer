from __future__ import annotations

import json
import sys
import textwrap
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from influenzer.adapters.base import AdapterRequest
from influenzer.adapters.contract import PLATFORM_CONTRACTS, assert_contract_result
from influenzer.adapters.http_fake import FakeHTTPServer
from influenzer.adapters.subprocess_harness import run_adapter_subprocess


class SubprocessHTTPConformanceTests(unittest.TestCase):
    def _req(self, platform: str, **kwargs) -> AdapterRequest:
        defaults = dict(
            platform=platform,
            project_id="app-1",
            account_id=f"{platform}-1",
            body="subprocess contract",
            operation_key=f"op-{platform}",
            dry_run=True,
            host="mastodon.social" if platform == "mastodon" else None,
            media=("artifact:sha256:" + "cd" * 32,),
            credential_ref="env:TOKEN",
        )
        defaults.update(kwargs)
        return AdapterRequest(**defaults)

    def _script_argv(self, source: str) -> list[str]:
        path = Path(self.id().replace(".", "_") + ".child.py")
        # Keep under tmp via write to cwd is messy; use inline -c for tiny scripts.
        return [sys.executable, "-c", textwrap.dedent(source)]

    def test_each_platform_create_via_loopback_http_subprocess(self) -> None:
        for platform in PLATFORM_CONTRACTS:
            with self.subTest(platform=platform):
                with FakeHTTPServer() as server:
                    server.enqueue(
                        {
                            "http_status": 200,
                            "provider_id": f"{platform}-http-1",
                            "provider_url": f"https://example.test/{platform}/1",
                        }
                    )
                    out = run_adapter_subprocess(self._req(platform), base_url=server.base_url)
                    assert_contract_result(out, platform)
                    self.assertTrue(out.get("subprocess") or out.get("status") == "planned")
                    self.assertEqual(len(server.calls), 1)
                    self.assertEqual(server.calls[0].method, "POST")
                    body = server.calls[0].body.decode("utf-8")
                    self.assertNotIn("sk-", body)
                    self.assertIn("operation_key", body)

    def test_failure_taxonomy_over_http_subprocess(self) -> None:
        cases = [
            ("rate_limited", {"http_status": 429}),
            ("auth_expired", {"http_status": 401}),
            ("permanent", {"http_status": 422, "error": "rejected"}),
            (
                "pre_send_validation",
                {"http_status": 400, "failure_class": "pre_send_validation", "error": "bad media"},
            ),
            ("ambiguous", {"http_status": 503}),
            ("multi_result", {"http_status": 200, "failure_class": "multi_result"}),
        ]
        for failure_class, scripted in cases:
            with self.subTest(failure=failure_class):
                with FakeHTTPServer() as server:
                    server.enqueue(scripted)
                    out = run_adapter_subprocess(self._req("x"), base_url=server.base_url)
                    if failure_class == "ambiguous":
                        self.assertEqual(out["status"], "unknown")
                        self.assertEqual(out["failure_class"], "ambiguous")
                    else:
                        self.assertFalse(out.get("ok", False) and out.get("status") == "planned")
                        self.assertEqual(out.get("failure_class"), failure_class)
                    self.assertEqual(len(server.calls), 1)

    def test_secret_on_wire_returns_secret_leak(self) -> None:
        with FakeHTTPServer() as server:
            token = "Bearer " + "sk" + "-" + "leak-test-value-123456"
            req = urllib.request.Request(
                server.base_url + "/2/tweets",
                data=b'{"text":"hi"}',
                method="POST",
                headers={"Authorization": token, "Content-Type": "application/json"},
            )
            try:
                with urllib.request.urlopen(req, timeout=2) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                    status = resp.status
            except urllib.error.HTTPError as exc:
                status = exc.code
                payload = json.loads(exc.read().decode("utf-8"))
            self.assertEqual(len(server.calls), 1)
            self.assertEqual(payload.get("failure_class"), "secret_leak")
            self.assertIn(status, {200, 400})

    def test_subprocess_timeout_kills_sleeping_child(self) -> None:
        # Deterministic sleep child — must hit TimeoutExpired and kill.
        out = run_adapter_subprocess(
            self._req("bluesky"),
            base_url="http://127.0.0.1:9",
            deadline_s=0.3,
            child_argv=self._script_argv(
                """
                import sys, time, os
                # Write pid so parent can observe termination indirectly via killed flag.
                sys.stderr.write(f"pid={os.getpid()}\\n")
                time.sleep(5)
                sys.stdout.write('{"status":"ok","ok":true,"mutated":false}')
                """
            ),
        )
        self.assertEqual(out["failure_class"], "timeout")
        self.assertTrue(out.get("killed"), out)
        self.assertEqual(out.get("returncode"), -1)
        self.assertFalse(out.get("mutated", False))

    def test_malformed_stdout_is_permanent(self) -> None:
        out = run_adapter_subprocess(
            self._req("x"),
            base_url="http://127.0.0.1:9",
            child_argv=self._script_argv(
                """
                import sys
                sys.stdout.write('not-json-at-all')
                """
            ),
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_class"], "permanent")
        self.assertIn("not JSON", out["reason"])

    def test_oversized_stdout_is_permanent(self) -> None:
        out = run_adapter_subprocess(
            self._req("x"),
            base_url="http://127.0.0.1:9",
            max_stdout=64,
            child_argv=self._script_argv(
                """
                import sys
                sys.stdout.write('{"status":"ok","ok":true,"mutated":false,"pad":"' + ('x'*200) + '"}')
                """
            ),
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_class"], "permanent")
        self.assertIn("stdout exceeds", out["reason"])

    def test_multiple_json_values_on_stdout_fail(self) -> None:
        out = run_adapter_subprocess(
            self._req("x"),
            base_url="http://127.0.0.1:9",
            child_argv=self._script_argv(
                """
                import sys
                sys.stdout.write('{"status":"ok","ok":true,"mutated":false}{"extra":true}')
                """
            ),
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_class"], "multi_result")

    def test_secret_on_stderr_is_secret_leak(self) -> None:
        out = run_adapter_subprocess(
            self._req("x"),
            base_url="http://127.0.0.1:9",
            child_argv=self._script_argv(
                """
                import sys
                # Split tokens so repo hygiene does not flag the test source.
                sys.stderr.write('Auth' + 'orization: Bea' + 'rer ' + 'sk' + '-' + 'stderr-secret-999')
                sys.stdout.write('{"status":"planned","ok":true,"mutated":false,"dry_run":true}')
                """
            ),
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["failure_class"], "secret_leak")

    def test_live_request_fails_in_child_without_http_call(self) -> None:
        with FakeHTTPServer() as server:
            out = run_adapter_subprocess(
                self._req("x", dry_run=False),
                base_url=server.base_url,
            )
            self.assertFalse(out.get("ok", False))
            self.assertFalse(out.get("mutated", False))
            self.assertEqual(len(server.calls), 0)


if __name__ == "__main__":
    unittest.main()
