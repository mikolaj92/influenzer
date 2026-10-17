import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

import httpx
from pydantic import ValidationError

from influenzer.gb10_decisions import (
    ACTIONS,
    DecisionResponseError,
    GB10Config,
    GB10Decisions,
)

MODEL = "GLM-5.3-Flash-EXL3"


def response(choice="research", confidence=0.8):
    probabilities = dict.fromkeys(ACTIONS, (1 - confidence) / (len(ACTIONS) - 1))
    probabilities[choice] = confidence
    return {"object": "decisions", "model": MODEL, "prompt_format_version": 1,
            "answers": {"action": {"type": "choice", "choice": choice,
                "probabilities": probabilities, "label_mass": 0.95}},
            "usage": {"prompt_tokens": 120, "completion_tokens": 0, "total_tokens": 120}}


def payload():
    return {"case": {"need": "Read PDFs offline", "evidence_ids": ["x:1"]},
            "interpretations": {"items": [{"evidence_id": "x:1", "category": "question", "need": "Read PDFs offline", "quote": "How?"}]}}


def config():
    return GB10Config(url="http://localhost:8888/v1/decisions", model=MODEL)


class GB10Tests(unittest.TestCase):
    def test_gb10_one_typed_question_no_chat_or_systemone(self):
        calls = []
        def handler(request):
            calls.append(request)
            return httpx.Response(200, json=response())
        port = GB10Decisions(config(), transport=httpx.MockTransport(handler))
        decision, audit = port.decide(payload=payload())
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].url.path, "/v1/decisions")
        request = json.loads(calls[0].content)
        self.assertEqual(request["model"], MODEL)
        self.assertEqual(request["prompt_format_version"], 1)
        self.assertEqual(request["chat_template_kwargs"], {"enable_thinking": False})
        self.assertEqual(json.loads(request["input"]), payload())
        self.assertEqual(len(request["questions"]), 1)
        self.assertEqual(request["questions"][0]["id"], "action")
        self.assertEqual(request["questions"][0]["type"], "choice")
        self.assertEqual({o["name"] for o in request["questions"][0]["options"]}, set(ACTIONS))
        self.assertNotIn("state", request)
        self.assertNotIn("messages", request)
        self.assertEqual(decision["kind"], "research")
        self.assertEqual(decision["evidence_ids"], ["x:1"])
        self.assertEqual(decision["evidence_scope"], "validated_case_not_model_selected")
        self.assertEqual(audit["protocol"], "decisions")
        self.assertEqual(audit["label_mass"], 0.95)
        self.assertEqual(audit["confidence"], 0.8)
        self.assertEqual(audit["usage"]["completion_tokens"], 0)
        self.assertGreaterEqual(audit["latency_ms"], 0)

    def test_decision_question_states_capability_and_project_kind_constraints(self):
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=response())
        GB10Decisions(config(), transport=httpx.MockTransport(handler)).decide(payload=payload())
        instructions = sent[0]["questions"][0]["question"]
        self.assertIn("An empty capabilities list forbids product, material and reply", instructions)
        self.assertIn("product requires kind=app", instructions)
        self.assertIn("research for a relevant unresolved need", instructions)

    def test_runtime_system_curl_posts_once_and_never_uses_httpx(self):
        import subprocess
        calls = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                calls.append((self.path, json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                body = json.dumps(response()).encode()
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *_):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            port = GB10Decisions(GB10Config(url=f"http://127.0.0.1:{server.server_port}/v1/decisions", model=MODEL))
            with patch("influenzer.gb10_decisions.httpx.Client", side_effect=AssertionError("transport fallback")), patch(
                "influenzer.gb10_decisions.subprocess.run", wraps=subprocess.run
            ) as run:
                decision, _ = port.decide(payload=payload())
            self.assertEqual(decision["kind"], "research")
            self.assertEqual(run.call_count, 1)
            command = run.call_args.args[0]
            self.assertEqual(command[0], "/usr/bin/curl")
            self.assertNotIn("--retry", command)
            self.assertNotIn("--location", command)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][0], "/v1/decisions")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()

    def test_runtime_transport_failure_retains_named_request_audit_without_retry(self):
        import subprocess
        for status, code in ((503, 0), (307, 0), (0, 28)):
            with self.subTest(status=status), patch("influenzer.gb10_decisions.subprocess.run", return_value=
                subprocess.CompletedProcess([], code, stdout=str(status).encode(), stderr=b"offline")) as run:
                with self.assertRaises(OSError) as caught:
                    GB10Decisions(config()).decide(payload=payload())
                self.assertEqual(run.call_count, 1)
                self.assertEqual(caught.exception.audit["http_status"], status)
                self.assertEqual(caught.exception.audit["transport_exit"], code)
                self.assertEqual(caught.exception.audit["request"]["questions"][0]["id"], "action")

    def test_subprocess_timeout_is_audited_without_a_second_transport(self):
        import subprocess
        with patch("influenzer.gb10_decisions.subprocess.run", side_effect=subprocess.TimeoutExpired("curl", 2)) as run, self.assertRaises(OSError) as caught:
            GB10Decisions(config()).decide(payload=payload())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(caught.exception.audit["transport_error"], "TimeoutExpired")

    def test_runtime_non_json_response_retains_exact_diagnostic_bytes(self):
        import subprocess
        def broken(command, **kwargs):
            from pathlib import Path
            Path(command[command.index("--output") + 1]).write_bytes(b"not-json-response")
            return subprocess.CompletedProcess(command, 0, stdout=b"200", stderr=b"")
        with patch("influenzer.gb10_decisions.subprocess.run", side_effect=broken) as run, self.assertRaises(DecisionResponseError) as caught:
            GB10Decisions(config()).decide(payload=payload())
        self.assertEqual(run.call_count, 1)
        self.assertEqual(caught.exception.audit["raw_response"], "not-json-response")

    def test_configuration_rejects_plumb_chat_and_embedded_credentials(self):
        for url in ("http://localhost:8090/v1/systemone", "http://localhost:8888/v1/chat/completions",
                    "http://user:secret@localhost:8888/v1/decisions", "file:///v1/decisions", "http://localhost:8888/v1/decisions?x=1"):
            with self.subTest(url=url), self.assertRaises(ValidationError):
                GB10Config(url=url, model=MODEL)
        for changed in ({"protocol": "systemone"}, {"min_confidence": float("nan")}):
            with self.subTest(changed=changed), self.assertRaises(ValidationError):
                GB10Config.model_validate({**config().model_dump(), **changed})

    def test_all_actions_are_receipts_not_generated_rationales(self):
        for choice in ACTIONS:
            with self.subTest(choice=choice):
                port = GB10Decisions(config(), transport=httpx.MockTransport(
                    lambda request, choice=choice: httpx.Response(200, json=response(choice=choice))))
                decision, audit = port.decide(payload=payload())
                self.assertEqual(decision["kind"], choice)
                self.assertEqual(decision["reason_source"], "protocol_receipt")
                self.assertEqual(decision["evidence_ids"], ["x:1"])
                self.assertEqual(audit["usage"]["completion_tokens"], 0)

    def test_decider_rejects_batch_without_case_before_http(self):
        calls = []
        port = GB10Decisions(config(), transport=httpx.MockTransport(
            lambda request: (calls.append(request), httpx.Response(200, json=response()))[1]))
        with self.assertRaisesRegex(ValueError, "one concrete case"):
            port.decide(payload={"interpretations": {"items": []}})
        self.assertEqual(calls, [])

    def test_timeout_503_and_redirect_are_one_attempt(self):
        for failure in (503, 307, "timeout"):
            with self.subTest(failure=failure):
                calls = []
                def handler(request, failure=failure, calls=calls):
                    calls.append(request)
                    if failure == "timeout":
                        raise httpx.ReadTimeout("offline", request=request)
                    return httpx.Response(failure, headers={"Location": "http://other/v1/decisions"})
                port = GB10Decisions(config(), transport=httpx.MockTransport(handler))
                with self.assertRaises(httpx.HTTPError):
                    port.decide(payload=payload())
                self.assertEqual(len(calls), 1)

    def test_protocol_model_mass_and_probabilities_are_validated(self):
        invalid = []
        for field, value in (("model", "foreign"), ("object", "chat.completion"),
                             ("prompt_format_version", 2), ("prompt_format_version", True)):
            raw = response(); raw[field] = value; invalid.append(raw)
        for field, value in (("label_mass", float("nan")), ("label_mass", -1), ("label_mass", 1.5), ("label_mass", True),
                             ("choice", "unknown"), ("choice", "skip")):
            raw = response(); raw["answers"]["action"][field] = value; invalid.append(raw)
        raw = response(); del raw["answers"]["action"]["label_mass"]; invalid.append(raw)
        raw = response(); raw["answers"]["other"] = raw["answers"].pop("action"); invalid.append(raw)
        raw = response(); raw["answers"]["action"]["probabilities"]["skip"] = float("nan"); invalid.append(raw)
        raw = response(); raw["answers"]["action"]["probabilities"]["skip"] = 0.8; invalid.append(raw)
        for field, value in (("completion_tokens", 1), ("completion_tokens", False), ("prompt_tokens", -1), ("total_tokens", 121)):
            raw = response(); raw["usage"][field] = value; invalid.append(raw)
        for raw in invalid:
            with self.subTest(raw=raw):
                port = GB10Decisions(config(), transport=httpx.MockTransport(
                    lambda request, raw=raw: httpx.Response(200, content=json.dumps(raw))))
                with self.assertRaises(DecisionResponseError) as caught:
                    port.decide(payload=payload())
                self.assertEqual(json.dumps(caught.exception.audit["response"]), json.dumps(raw))

    def test_uncertain_or_tied_choice_is_not_skip(self):
        for confidence in (0.4, 0.2):
            with self.subTest(confidence=confidence):
                port = GB10Decisions(config(), transport=httpx.MockTransport(
                    lambda request, confidence=confidence: httpx.Response(200, json=response(confidence=confidence))))
                decision, audit = port.decide(payload=payload())
                self.assertIsNone(decision)
                self.assertEqual(audit["status"], "abstained")
                self.assertEqual(audit["reason"], "decision_uncertain")
                self.assertEqual(audit["choice"], "research")


if __name__ == "__main__":
    unittest.main()
