import json
import unittest
from unittest.mock import patch

import httpx

from influenzer.tencent_records import TencentConfig, TencentRecords


class TencentTests(unittest.TestCase):
    def test_gateway_config_rejects_credentials_redirect_parameters_and_non_http(self):
        for url in ("file:///tmp/data", "http://token@local", "http://local/?api_key=secret", "http://local/#other", "http://"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                TencentConfig(url=url, team_id="team", agent_id="app", user_id="owner")

    def test_redirects_and_503_do_not_retry_or_follow(self):
        for status in (302, 503):
            calls = []
            def handler(request, status=status, calls=calls):
                calls.append(request)
                return httpx.Response(status, headers={"location": "http://elsewhere"})
            with self.subTest(status=status), patch.dict("os.environ", {"TDAI_MEMORY_USER_KEY": "secret", "TDAI_MEMORY_API_KEY": "bearer"}):
                port = TencentRecords(TencentConfig(url="http://local", team_id="team", agent_id="app", user_id="owner"), transport=httpx.MockTransport(handler))
                with self.assertRaises(httpx.HTTPError):
                    port.put({"data": "value"})
            self.assertEqual(len(calls), 1)

    def test_missing_scope_is_not_silently_empty_or_written(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(404, json={"code": 404, "message": "Memory scope not found"})
        with patch.dict("os.environ", {"TDAI_MEMORY_USER_KEY": "secret", "TDAI_MEMORY_API_KEY": "bearer"}):
            port = TencentRecords(TencentConfig(url="http://local", team_id="team", agent_id="app", user_id="owner"), transport=httpx.MockTransport(handler))
            with self.assertRaises(httpx.HTTPError):
                port.put({"data": "value"})
        self.assertEqual(len(calls), 1)

    def test_corrupt_or_missing_chunks_fail_exact_readback(self):
        for messages in ([{"role": "assistant", "content": "not-json"}], []):
            def handler(request, messages=messages):
                return httpx.Response(200, json={"code": 0, "data": {"messages": messages, "total": 1}})
            with self.subTest(messages=messages), patch.dict("os.environ", {"TDAI_MEMORY_USER_KEY": "secret", "TDAI_MEMORY_API_KEY": "bearer"}):
                port = TencentRecords(TencentConfig(url="http://local", team_id="team", agent_id="app", user_id="owner"), transport=httpx.MockTransport(handler))
                with self.assertRaises(ValueError):
                    port.get("a" * 64)

    def test_app_data_is_exact_content_addressed_and_not_user_memory_capture(self):
        rows = []
        calls = []
        def handler(request):
            body = json.loads(request.content); calls.append((request.url.path, body))
            self.assertEqual(body["agent_id"], "app-agent")
            self.assertEqual(body["user_id"], "owner")
            if request.url.path.endswith("/query"):
                return httpx.Response(200, json={"code": 0, "data": {"messages": rows, "total": len(rows)}})
            rows.extend({"role": m["role"], "content": m["content"], "id": str(n)} for n, m in enumerate(body["messages"]))
            return httpx.Response(200, json={"code": 0, "data": {"accepted_ids": [str(n) for n in range(len(rows))], "total_count": len(rows)}})
        config = TencentConfig(url="http://local", team_id="team", agent_id="app-agent", user_id="owner")
        with patch.dict("os.environ", {"TDAI_MEMORY_USER_KEY": "secret", "TDAI_MEMORY_API_KEY": "bearer"}):
            port = TencentRecords(config, transport=httpx.MockTransport(handler))
            data = {"untrusted_evidence": "External post &amp; " + "x" * 16000, "disclosures": ("local demo",)}
            receipt = port.put(data)
            self.assertEqual(port.get(receipt["digest"]), json.loads(json.dumps(data)))
            self.assertEqual(port.put(data)["digest"], receipt["digest"])
        writes = [b for p, b in calls if p.endswith("/add")]
        self.assertEqual(len(writes), 1)
        self.assertTrue(all(m["role"] == "assistant" and len(m["content"]) <= 8192 for m in writes[0]["messages"]))
        self.assertTrue(writes[0]["session_id"].startswith("influenzer:record:"))
        self.assertNotIn("secret", json.dumps(receipt))
