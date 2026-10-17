import io
import json
import tempfile
import unittest
from contextlib import contextmanager, redirect_stdout
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import httpx
from openai import APITimeoutError, OpenAI

from influenzer.domain import Project
from influenzer.gb10_decisions import ACTIONS, GB10Config, GB10Decisions
from influenzer.model_review import (
    ModelOutputError,
    OpenAIModels,
    ReviewConfig,
    proposals,
    record_verdict,
    review_evidence,
)
from influenzer.storage import StateRepository

EVIDENCE = [{"evidence_id": "x:1", "content": "How do I run local AI offline?", "url": "https://x.com/a/status/1", "raw_ref": "abc"}]


def config(**kwargs):
    return ReviewConfig(base_url="http://localhost:1234/v1", interpretation_model="reader",
                        decision=GB10Config(url="http://localhost:8888/v1/decisions", model="GLM-5.3-Flash-EXL3"), **kwargs)


@contextmanager
def repository():
    with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
        repo.save_project(Project.create(project_id="builder", slug="builder", name="Builder", display_name="Builder",
            voice="practical", audience="builders", maintainer="Patryk", kind="builder"))
        yield repo


class FakeReader:
    def __init__(self, change=None):
        self.calls = []
        self.change = change or {}

    def complete(self, *, model, system, payload):
        self.calls.append((model, system, payload))
        item = {"evidence_id": "x:1", "category": "question", "need": "Run local AI offline",
                "fragment_id": payload["fragments"][0]["fragment_id"], "uncertainty": [], **self.change}
        cases = [{"need": item["need"], "evidence_ids": [item["evidence_id"]]}] if item["need"] else []
        return {"items": [item], "cases": cases}, {"model": model, "usage": {"total_tokens": 12}}


class FakeDecider:
    def __init__(self, change=None):
        self.calls = []
        self.change = change or {}

    def decide(self, *, payload):
        self.calls.append(payload)
        return {"kind": "research", "evidence_ids": ["x:1"], "reason": "Typed choice; no generated rationale",
                "reason_source": "protocol_receipt", "evidence_scope": "validated_case_not_model_selected", **self.change}, {"model": "GLM-5.3-Flash-EXL3", "protocol": "decisions", "usage": {"total_tokens": 5}}


SCOPE = {"id": "builder", "kind": "builder", "audience": "Local AI builders",
         "problem": "Understand and run local inference, hardware and offline workflows",
         "capabilities": [], "not_offered": ["Hardware sales", "Hosted inference"]}


def run(repo, reader=None, decider=None, **kwargs):
    return review_evidence(repo, project_id="builder", evidence=kwargs.pop("evidence", EVIDENCE), coverage=[],
                           config=config(), client=reader or FakeReader(), decision_client=decider or FakeDecider(),
                           project_scope=kwargs.pop("project_scope", SCOPE), **kwargs)


def completion(content, finish="stop"):
    return {"id": "test", "object": "chat.completion", "created": 1, "model": "actual-model",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": finish}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13}}


class ModelReviewTests(unittest.TestCase):
    def test_exception_details_are_not_returned_persisted_or_retained(self):
        secret = "Bearer PRIVATE_TOKEN https://private.example/path?key=PRIVATE_KEY"
        class BrokenReader:
            calls = 0
            def complete(self, **kwargs):
                self.calls += 1
                raise ValueError(secret)
        class BrokenDecider:
            calls = 0
            def decide(self, **kwargs):
                self.calls += 1
                raise OSError(secret)
        for stage in ("interpretation", "decision"):
            with self.subTest(stage=stage), repository() as repo:
                broken = BrokenReader() if stage == "interpretation" else BrokenDecider()
                kwargs = {"reader": broken} if stage == "interpretation" else {"decider": broken}
                for _ in range(2):
                    result = run(repo, **kwargs)
                    failed = result if stage == "interpretation" else result["cases"][0]
                    self.assertEqual(failed["failure_message"], failed["failure_class"])
                    self.assertEqual(failed["failed_stage"], stage)
                    self.assertNotIn(secret, json.dumps(result))
                    self.assertNotIn(secret, "".join(e["payload_json"] for e in repo.events("builder")))
                    with patch("influenzer.tencent_records.TencentRecords.put", return_value={}) as retained:
                        from influenzer.tencent_records import retain_record
                        retain_record({"url": "https://records.example", "team_id": "team", "agent_id": "app", "user_id": "owner"}, result)
                    self.assertNotIn(secret, json.dumps(retained.call_args.args))
                self.assertEqual(broken.calls, 1)

    def test_model_selects_fragment_id_and_host_restores_exact_quote(self):
        with repository() as repo:
            evidence = [{**EVIDENCE[0], "content": "You need private &amp; offline AI?"}]
            class Reader:
                def complete(self, **kwargs):
                    fragment = kwargs["payload"]["fragments"][0]
                    return {"items": [{"evidence_id": "x:1", "category": "question", "need": "Private offline AI",
                                       "fragment_id": fragment["fragment_id"], "uncertainty": []}],
                            "cases": [{"need": "Private offline AI", "evidence_ids": ["x:1"]}]}, {}
            result = run(repo, Reader(), evidence=evidence)
            self.assertEqual(result["status"], "proposed")
            self.assertEqual(result["interpretations"][0]["quote"], evidence[0]["content"])
            self.assertNotIn("quote", result["audits"][0]["response"]["items"][0])

    def test_valid_fragment_from_other_evidence_is_rejected_without_decisions(self):
        with repository() as repo:
            evidence = [EVIDENCE[0], {**EVIDENCE[0], "evidence_id": "x:2", "content": "Another need?"}]
            class Reader:
                def complete(self, **kwargs):
                    spans = kwargs["payload"]["fragments"]
                    return {"items": [{"evidence_id": s["evidence_id"], "category": "question", "need": "Offline AI",
                        "fragment_id": spans[1]["fragment_id"], "uncertainty": []} for s in spans],
                        "cases": [{"need": "Offline AI", "evidence_ids": ["x:1", "x:2"]}]}, {}
            decider = FakeDecider()
            result = run(repo, Reader(), evidence=evidence, decider=decider)
            self.assertEqual(result["failure_message"], "ValueError")
            self.assertEqual(decider.calls, [])

    def test_unrelated_needs_get_separate_cited_decisions_after_one_llm_call(self):
        with repository() as repo:
            evidence = EVIDENCE + [{"evidence_id": "x:2", "content": "Which GPU should I buy?", "url": "https://x.com/a/status/2"}]
            class Reader:
                calls = 0
                def complete(self, **kwargs):
                    self.calls += 1
                    return {"items": [
                        {"evidence_id": e["evidence_id"], "category": "question", "need": need, "fragment_id": next(f["fragment_id"] for f in kwargs["payload"]["fragments"] if f["evidence_id"] == e["evidence_id"]), "uncertainty": []}
                        for e, need in zip(evidence, ["Run local AI offline", "Choose a GPU"], strict=True)],
                        "cases": [{"need": "Run local AI offline", "evidence_ids": ["x:1"]},
                                  {"need": "Choose a GPU", "evidence_ids": ["x:2"]}]}, {"model": "reader"}
            class Decider:
                def __init__(self):
                    self.calls = []
                def decide(self, *, payload):
                    self.calls.append(payload)
                    return {"kind": "research", "evidence_ids": payload["case"]["evidence_ids"],
                            "reason": "receipt", "reason_source": "protocol_receipt",
                            "evidence_scope": "validated_case_not_model_selected"}, {"model": "GLM-5.3-Flash-EXL3"}
            reader, decider = Reader(), Decider()
            result = run(repo, reader, decider, evidence=evidence)
            self.assertEqual(result["status"], "proposed")
            self.assertIsNone(result["decision"])
            self.assertEqual(len(result["cases"]), 2)
            self.assertEqual(reader.calls, 1)
            self.assertEqual(len(decider.calls), 2)
            for case, sent in zip(result["cases"], decider.calls, strict=True):
                self.assertEqual(case["case"]["evidence_ids"], case["decision"]["evidence_ids"])
                self.assertEqual({i["evidence_id"] for i in sent["interpretations"]["items"]}, set(sent["case"]["evidence_ids"]))
            self.assertEqual(len(proposals(repo, "builder")), 2)
            again = run(repo, reader, decider, evidence=evidence)
            self.assertEqual(json.dumps(again, sort_keys=True), json.dumps(result, sort_keys=True))
            self.assertEqual(reader.calls, 1)
            self.assertEqual(len(decider.calls), 2)

    def test_gb10_is_the_only_decider_after_one_llm_interpretation(self):
        requests = []
        def handler(request):
            requests.append(request)
            probabilities = dict.fromkeys(ACTIONS, 0.05); probabilities["research"] = 0.8
            return httpx.Response(200, json={"model": "GLM-5.3-Flash-EXL3", "object": "decisions", "prompt_format_version": 1,
                "answers": {"action": {"type": "choice", "choice": "research", "probabilities": probabilities, "label_mass": 0.9}},
                "usage": {"prompt_tokens": 50, "completion_tokens": 0, "total_tokens": 50}})
        with repository() as repo:
            reader = FakeReader()
            first = run(repo, reader, GB10Decisions(config().decision, transport=httpx.MockTransport(handler)))
            self.assertEqual(first["status"], "proposed")
            self.assertEqual(first["cases"][0]["decision"]["kind"], "research")
            self.assertEqual(len(reader.calls), 1)
            self.assertEqual(len(requests), 1)
            self.assertEqual(first["audits"][1]["protocol"], "decisions")
            self.assertEqual(repo.conn.execute("SELECT count(*) FROM briefs").fetchone()[0], 0)

    def test_gb10_timeout_never_calls_llm_or_heuristic_fallback(self):
        with repository() as repo:
            reader = FakeReader()
            calls = []
            def offline(request):
                calls.append(request)
                raise httpx.ReadTimeout("offline", request=request)
            decider = GB10Decisions(config().decision, transport=httpx.MockTransport(offline))
            with patch("influenzer.review_evaluation.lexical_category", side_effect=AssertionError("heuristic fallback")):
                for _ in range(2):
                    result = run(repo, reader, decider)
                    self.assertEqual(result["status"], "partial")
                    case = result["cases"][0]
                    self.assertIsNone(case["decision"])
                    self.assertEqual(case["reason"], "decision_failed_no_fallback")
                    self.assertEqual(case["failed_stage"], "decision")
            self.assertEqual(len(reader.calls), 1)
            self.assertEqual(len(calls), 1)
            self.assertEqual(proposals(repo, "builder"), [])

    def test_gb10_curl_failure_is_durable_and_repeated_review_does_not_retry(self):
        import subprocess
        with repository() as repo, patch("influenzer.gb10_decisions.subprocess.run", return_value=
            subprocess.CompletedProcess([], 0, stdout=b"503", stderr=b"offline")) as transport:
            reader = FakeReader()
            for _ in range(2):
                result = run(repo, reader, GB10Decisions(config().decision))
                self.assertEqual(result["status"], "partial")
                case = result["cases"][0]
                self.assertIsNone(case["decision"])
                self.assertEqual(case["reason"], "decision_failed_no_fallback")
                self.assertEqual(case["audits"][0]["http_status"], 503)
                self.assertEqual(case["audits"][0]["protocol"], "decisions")
            self.assertEqual(len(reader.calls), 1)
            self.assertEqual(transport.call_count, 1)
            self.assertEqual(proposals(repo, "builder"), [])

    def test_gb10_abstention_is_not_skip_and_is_retained_without_retry(self):
        with repository() as repo:
            calls = []
            def uncertain(request):
                calls.append(request)
                return httpx.Response(200, json={"model": "GLM-5.3-Flash-EXL3", "object": "decisions", "prompt_format_version": 1,
                    "answers": {"action": {"type": "choice", "choice": "research",
                    "probabilities": {"research": 0.4, "skip": 0.3, "product": 0.1, "material": 0.1, "reply": 0.1}, "label_mass": 0.9}},
                    "usage": {"prompt_tokens": 50, "completion_tokens": 0, "total_tokens": 50}})
            decider = GB10Decisions(config().decision, transport=httpx.MockTransport(uncertain))
            for _ in range(2):
                result = run(repo, decider=decider)
                self.assertEqual(result["status"], "abstained")
                self.assertEqual(result["cases"][0]["decision_status"], "decision_uncertain")
                self.assertIsNone(result["decision"])
            self.assertEqual(len(calls), 1)
            self.assertEqual(proposals(repo, "builder")[0]["status"], "abstained")

    def test_legacy_llm_decision_configuration_is_rejected(self):
        from pydantic import ValidationError
        with self.assertRaises(ValidationError):
            ReviewConfig(base_url="http://local/v1", interpretation_model="reader", decision_model="old-decider")

    def test_transport_has_no_retries_and_json_contract(self):
        requests = []
        def handler(request):
            requests.append(json.loads(request.content))
            return httpx.Response(200, json=completion('{"ready":true}'))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http, patch(
            "influenzer.model_review.OpenAI", return_value=OpenAI(base_url="http://local/v1", api_key="local", max_retries=0, http_client=http)
        ) as factory:
            data, audit = OpenAIModels(config()).complete(model="reader", system="System", payload={"untrusted": "text"})
        self.assertEqual(factory.call_args.kwargs["max_retries"], 0)
        self.assertTrue(data["ready"])
        self.assertEqual(audit["model"], "actual-model")
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["reasoning_effort"], "low")
        self.assertEqual(requests[0]["response_format"], {"type": "json_object"})

    def test_transport_json_fence_and_malformed_output_audits(self):
        for text, valid in (('```json\n{"ready":true}\n```', True), ('not JSON', False)):
            with self.subTest(text=text), httpx.Client(transport=httpx.MockTransport(
                lambda request, text=text: httpx.Response(200, json=completion(text))
            )) as http, patch("influenzer.model_review.OpenAI", return_value=OpenAI(base_url="http://local/v1", api_key="local", http_client=http)):
                port = OpenAIModels(config(json_mode=False))
                if valid:
                    data, audit = port.complete(model="reader", system="JSON only", payload={})
                    self.assertTrue(data["ready"])
                else:
                    with self.assertRaises(ModelOutputError) as caught:
                        port.complete(model="reader", system="JSON only", payload={})
                    audit = caught.exception.audit
                self.assertEqual(audit["raw_response"], text)

    def test_provider_without_json_mode_has_no_response_format(self):
        sent = []
        def handler(request):
            sent.append(json.loads(request.content))
            return httpx.Response(200, json=completion('{"ready":true}'))
        with httpx.Client(transport=httpx.MockTransport(handler)) as http, patch(
            "influenzer.model_review.OpenAI", return_value=OpenAI(base_url="http://local/v1", api_key="local", http_client=http)
        ):
            OpenAIModels(config(json_mode=False)).complete(model="reader", system="JSON only", payload={})
        self.assertNotIn("response_format", sent[0])

    def test_atomic_claim_and_overlap_do_not_repeat_calls(self):
        with repository() as repo, StateRepository(repo.db_path) as second:
            payload = {"proposal_id": "same-input", "status": "incomplete"}
            self.assertIsNone(repo.claim_radar_review("builder", payload))
            self.assertEqual(second.claim_radar_review("builder", payload), payload)
            reader, decider = FakeReader(), FakeDecider()
            first = run(repo, reader, decider)
            repeated = run(second, reader, decider)
            self.assertEqual(first["proposal_id"], repeated["proposal_id"])
            self.assertEqual(len(reader.calls), 1)
            self.assertEqual(len(decider.calls), 1)

    def test_overlapping_review_is_incomplete(self):
        with repository() as repo:
            overlap = []
            class Overlap(FakeReader):
                def complete(self, **kwargs):
                    if not self.calls:
                        overlap.append(run(repo, self))
                    return super().complete(**kwargs)
            self.assertEqual(run(repo, Overlap())["status"], "proposed")
            self.assertEqual(overlap[0]["status"], "incomplete")

    def test_review_cap_uses_recency_not_url_order_or_need_keywords(self):
        with repository() as repo:
            captured = []
            class Reader:
                def complete(self, **kwargs):
                    captured.extend(kwargs["payload"]["evidence"])
                    return {"items": [{"evidence_id": e["evidence_id"], "category": "other", "need": None,
                                       "fragment_id": next(f["fragment_id"] for f in kwargs["payload"]["fragments"] if f["evidence_id"] == e["evidence_id"]), "uncertainty": []} for e in captured], "cases": []}, {"model": "reader"}
            evidence = [{"evidence_id": f"https://old/{i}", "content": "Need older post", "url": f"https://old/{i}",
                         "published_at": "2026-09-01T00:00:00+00:00"} for i in range(30)] + [
                        {"evidence_id": "x:new", "content": "Advertisement without need", "url": "https://x.com/a/status/new",
                         "published_at": "2026-10-01T00:00:00+00:00"}]
            run(repo, Reader(), FakeDecider({"kind": "skip", "evidence_ids": []}), evidence=evidence)
            self.assertIn("x:new", [e["evidence_id"] for e in captured])
            self.assertEqual(len(captured), 30)

    def test_capability_claim_requires_quote_in_retained_artifact(self):
        with repository() as repo:
            artifact = repo.artifacts.put(b"Offline PDF extraction demo passed on this machine.")
            capability = {"claim": "Offline PDF extraction demo", "artifact_digest": artifact["digest"],
                          "quote": "Offline PDF extraction demo passed"}
            decider = FakeDecider({"kind": "material"})
            result = run(repo, decider=decider, project_scope={**SCOPE, "capabilities": [capability]})
            self.assertEqual(result["status"], "proposed")
            self.assertEqual(decider.calls[0]["project_scope"]["capabilities"][0]["provenance"], "artifact_verified_not_semantic_proof")
            reader = FakeReader()
            for changed in ({"quote": "Invented capability"}, {"artifact_digest": "a" * 64}):
                with self.subTest(changed=changed), self.assertRaises((ValueError, OSError)):
                    run(repo, reader, project_scope={**SCOPE, "capabilities": [{**capability, **changed}]})
            self.assertEqual(reader.calls, [])

    def test_product_change_requires_app_even_with_documented_capability(self):
        with repository() as repo:
            artifact = repo.artifacts.put(b"Measured offline extraction works.")
            capability = {"claim": "Measured extraction", "artifact_digest": artifact["digest"], "quote": "Measured offline extraction works."}
            result = run(repo, decider=FakeDecider({"kind": "product"}), project_scope={**SCOPE, "capabilities": [capability]})
            self.assertEqual(result["cases"][0]["failure_message"], "ValueError")
            repo.save_project(Project.create(project_id="documents", slug="documents", name="Documents", display_name="Documents",
                voice="practical", audience="document workers", maintainer="Patryk", kind="app"))
            app_scope = {**SCOPE, "id": "documents", "kind": "app", "problem": "Extract PDFs offline", "capabilities": [capability]}
            decider = FakeDecider({"kind": "product"})
            result = review_evidence(repo, project_id="documents", evidence=EVIDENCE, coverage=[], config=config(), client=FakeReader(),
                                     decision_client=decider, project_scope=app_scope)
            self.assertEqual(result["cases"][0]["decision"]["kind"], "product")
            self.assertEqual(decider.calls[0]["project_scope"]["id"], "documents")

    def test_unverified_solution_claim_is_failed_not_replaced_by_research(self):
        for kind in ("material", "reply", "product"):
            with self.subTest(kind=kind), repository() as repo:
                decider = FakeDecider({"kind": kind})
                result = run(repo, decider=decider)
                case = result["cases"][0]
                self.assertEqual(case["status"], "failed")
                self.assertIsNone(case["decision"])
                self.assertEqual(case["reason"], "decision_failed_no_fallback")
                self.assertEqual(len(decider.calls), 1)

    def test_same_concrete_need_is_one_case_with_two_citations_not_two_decisions(self):
        with repository() as repo:
            evidence = EVIDENCE + [{"evidence_id": "x:2", "content": "I need to run AI offline too", "url": "https://x.com/b/status/2"}]
            class Reader:
                def complete(self, **kwargs):
                    return {"items": [{"evidence_id": e["evidence_id"], "category": "request", "need": "Run AI offline",
                                       "fragment_id": next(f["fragment_id"] for f in kwargs["payload"]["fragments"] if f["evidence_id"] == e["evidence_id"]), "uncertainty": []} for e in evidence],
                            "cases": [{"need": "Run AI offline", "evidence_ids": ["x:1", "x:2"]}]}, {}
            class Decider:
                def __init__(self):
                    self.calls = []
                def decide(self, *, payload):
                    self.calls.append(payload)
                    return {"kind": "research", "evidence_ids": ["x:1", "x:2"], "reason": "receipt", "reason_source": "protocol_receipt",
                            "evidence_scope": "validated_case_not_model_selected"}, {}
            decider = Decider()
            result = run(repo, Reader(), decider, evidence=evidence)
            self.assertEqual(result["counts"]["cases"], 1)
            self.assertEqual(len(decider.calls), 1)
            self.assertEqual(len(proposals(repo, "builder")[0]["snapshot"]["evidence"]), 2)

    def test_case_partition_rejects_missing_duplicate_or_non_need_references(self):
        for cases in ([], [{"need": "Offline AI", "evidence_ids": ["unknown"]}],
                      [{"need": "Offline AI", "evidence_ids": ["x:1", "x:1"]}]):
            with self.subTest(cases=cases), repository() as repo:
                class Reader(FakeReader):
                    def complete(self, cases=cases, **kwargs):
                        data, audit = super().complete(**kwargs)
                        return {**data, "cases": cases}, audit
                decider = FakeDecider()
                result = run(repo, Reader(), decider)
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["failed_stage"], "interpretation")
                self.assertEqual(decider.calls, [])

    def test_one_case_failure_does_not_erase_another_case_decision(self):
        with repository() as repo:
            evidence = EVIDENCE + [{"evidence_id": "x:2", "content": "Which GPU should I buy?", "url": "https://x.com/a/status/2"}]
            class Reader:
                def complete(self, **kwargs):
                    return {"items": [{"evidence_id": e["evidence_id"], "category": "question", "need": e["content"],
                                       "fragment_id": next(f["fragment_id"] for f in kwargs["payload"]["fragments"] if f["evidence_id"] == e["evidence_id"]), "uncertainty": []} for e in evidence],
                            "cases": [{"need": e["content"], "evidence_ids": [e["evidence_id"]]} for e in evidence]}, {}
            class Decider:
                def __init__(self):
                    self.calls = []
                def decide(self, *, payload):
                    self.calls.append(payload)
                    if payload["case"]["evidence_ids"] == ["x:1"]:
                        raise httpx.ReadTimeout("offline")
                    return {"kind": "skip", "evidence_ids": ["x:2"], "reason": "receipt", "reason_source": "protocol_receipt",
                            "evidence_scope": "validated_case_not_model_selected"}, {}
            decider = Decider()
            result = run(repo, Reader(), decider, evidence=evidence)
            self.assertEqual(result["status"], "partial")
            self.assertEqual(result["counts"], {"cases": 2, "proposed": 1, "failed": 1, "abstained": 0, "incomplete": 0})
            self.assertEqual(len(proposals(repo, "builder")), 1)
            run(repo, Reader(), decider, evidence=evidence)
            self.assertEqual(len(decider.calls), 2)

    def test_case_verdict_cannot_target_whole_review_or_change_other_case(self):
        with repository() as repo:
            result = run(repo)
            with self.assertRaises(ValueError):
                record_verdict(repo, project_id="builder", proposal_id=result["proposal_id"], verdict="useful", reason="yes", actor="Patryk")
            case = result["cases"][0]
            record_verdict(repo, project_id="builder", proposal_id=case["proposal_id"], verdict="useful", reason="yes", actor="Patryk")
            self.assertEqual(proposals(repo, "builder")[0]["verdict"]["verdict"], "useful")

    def test_input_ids_unique_before_calls(self):
        with repository() as repo:
            reader = FakeReader()
            with self.assertRaises(ValueError):
                run(repo, reader, evidence=EVIDENCE + EVIDENCE)
            self.assertEqual(reader.calls, [])

    def test_cli_uses_current_report_and_existing_project(self):
        from influenzer.cli import main
        with repository() as repo:
            home = repo.db_path.parent
            (home / "radar.json").write_text(json.dumps({"models": config().model_dump(), "project": SCOPE}))
            (home / "radar-latest.json").write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "evidence": EVIDENCE, "coverage": []}))
            with patch("influenzer.model_review.OpenAIModels", return_value=FakeReader()), patch(
                "influenzer.model_review.GB10Decisions", return_value=FakeDecider()
            ), redirect_stdout(io.StringIO()) as out:
                code = main(["--config", str(home / "config.json"), "review", "run", "--project-id", "builder"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())["status"], "proposed")

    def test_cli_can_review_same_evidence_for_separate_app_profile_without_builder_scope(self):
        from influenzer.cli import main
        with repository() as repo:
            home = repo.db_path.parent
            repo.save_project(Project.create(project_id="documents", slug="documents", name="Documents", display_name="Documents",
                voice="practical", audience="document workers", maintainer="Patryk", kind="app"))
            scope = {"id": "documents", "kind": "app", "audience": "People processing private PDFs",
                     "problem": "Offline extraction of text from PDFs", "capabilities": [], "not_offered": ["Hardware advice"]}
            (home / "documents.json").write_text(json.dumps(scope))
            (home / "radar.json").write_text(json.dumps({"models": config().model_dump(), "project": SCOPE}))
            (home / "radar-latest.json").write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "project_id": "builder",
                                                              "evidence": EVIDENCE, "coverage": []}))
            decider = FakeDecider()
            with patch("influenzer.model_review.OpenAIModels", return_value=FakeReader()), patch(
                "influenzer.model_review.GB10Decisions", return_value=decider
            ), redirect_stdout(io.StringIO()) as out:
                code = main(["--config", str(home / "config.json"), "review", "run", "--project-id", "documents",
                             "--profile", str(home / "documents.json")])
            self.assertEqual(code, 0)
            self.assertEqual(decider.calls[0]["project_scope"]["id"], "documents")
            self.assertEqual(json.loads(out.getvalue())["project_id"], "documents")

    def test_review_latest_retains_full_record_in_configured_tencent_backend(self):
        from influenzer.model_review import review_latest
        from influenzer.tencent_records import TencentConfig
        with repository() as repo:
            home = repo.db_path.parent
            backend = TencentConfig(url="http://local", team_id="team", agent_id="app", user_id="owner")
            (home / "radar.json").write_text(json.dumps({"models": config().model_dump(), "project": SCOPE, "records": backend.model_dump()}))
            (home / "radar-latest.json").write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "evidence": EVIDENCE, "coverage": []}))
            class Records:
                def __init__(self):
                    self.saved = []
                def put(self, payload):
                    self.saved.append(payload)
                    return {"backend": "tencentdb", "digest": "a" * 64}
            records = Records()
            with patch("influenzer.model_review.OpenAIModels", return_value=FakeReader()), patch(
                "influenzer.model_review.GB10Decisions", return_value=FakeDecider()
            ), patch("influenzer.tencent_records.TencentRecords", return_value=records):
                result = review_latest(home, project_id="builder")
            self.assertEqual(result["record"]["backend"], "tencentdb")
            self.assertEqual(records.saved[0]["cases"][0]["case"]["evidence_ids"], ["x:1"])
            self.assertEqual(records.saved[0]["snapshot"]["fragments"][0]["text"], EVIDENCE[0]["content"])

    def test_latest_preserves_review_with_named_storage_failure_without_model_retry(self):
        import httpx

        from influenzer.model_review import review_latest
        with repository() as repo:
            home = repo.db_path.parent
            (home / "radar.json").write_text(json.dumps({"records": {"url": "http://local", "team_id": "team", "agent_id": "app", "user_id": "owner"},
                "models": config().model_dump(), "project": SCOPE}))
            (home / "radar-latest.json").write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "evidence": EVIDENCE, "coverage": []}))
            reader = FakeReader()
            with patch("influenzer.model_review.OpenAIModels", return_value=reader), patch(
                "influenzer.model_review.GB10Decisions", return_value=FakeDecider()
            ), patch("influenzer.tencent_records.TencentRecords.put", side_effect=httpx.ReadTimeout("timeout")):
                for _ in range(2):
                    result = review_latest(home, project_id="builder")
                    self.assertEqual(result["status"], "proposed")
                    self.assertEqual(result["record"]["status"], "unconfirmed")
                    self.assertEqual(result["record"]["reason"], "record_persistence_failed_no_retry")
                    self.assertEqual(json.loads((home / "review-latest.json").read_text())["record"], result["record"])
            self.assertEqual(len(reader.calls), 1)

    def test_cli_updates_latest_review_file_also_when_model_fails(self):
        from influenzer.model_review import review_latest
        with repository() as repo:
            home = repo.db_path.parent
            (home / "radar.json").write_text(json.dumps({"models": config().model_dump()}))
            (home / "radar-latest.json").write_text(json.dumps({"generated_at": datetime.now(UTC).isoformat(), "evidence": EVIDENCE, "coverage": []}))
            for status in ("proposed", "failed"):
                with patch("influenzer.model_review.review_evidence", return_value={"status": status, "decision": None}):
                    review_latest(home, project_id="builder")
                self.assertEqual(json.loads((home / "review-latest.json").read_text())["status"], status)

    def test_cli_partial_review_is_non_success(self):
        from influenzer.cli import main
        with repository() as repo, patch("influenzer.model_review.review_latest", return_value={
            "status": "partial", "decision": None, "counts": {"failed": 1}
        }), redirect_stdout(io.StringIO()):
            self.assertEqual(main(["--config", str(repo.db_path.parent / "config.json"), "review", "run", "--project-id", "builder"]), 1)

    def test_cli_abstention_returns_named_non_success_without_decision(self):
        from influenzer.cli import main
        with repository() as repo, patch("influenzer.model_review.review_latest", return_value={
            "status": "abstained", "decision": None, "decision_status": "decision_uncertain"
        }), redirect_stdout(io.StringIO()) as out:
            code = main(["--config", str(repo.db_path.parent / "config.json"), "review", "run", "--project-id", "builder"])
        self.assertEqual(code, 2)
        self.assertIsNone(json.loads(out.getvalue())["decision"])

    def test_evaluation_cli_replays_labels_without_model_calls(self):
        from influenzer.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            (home / "proposal.json").write_text(json.dumps({"snapshot": {"evidence": EVIDENCE}, "interpretations": [{"evidence_id": "x:1", "category": "question"}], "audits": []}))
            (home / "labels.json").write_text(json.dumps({"reviewer": "Patryk", "cases": [{"evidence_id": "x:1", "is_need": True}]}))
            with redirect_stdout(io.StringIO()) as out:
                code = main(["review", "evaluate", "--proposal", str(home / "proposal.json"), "--labels", str(home / "labels.json")])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(out.getvalue())["model"]["tp"], 1)

    def test_evaluation_counts_and_usage(self):
        from influenzer.review_evaluation import measure
        cases = [{"evidence_id": "a", "is_need": True, "heuristic_need": False}, {"evidence_id": "b", "is_need": False, "heuristic_need": True}]
        proposal = {"interpretations": [{"evidence_id": "a", "category": "request"}, {"evidence_id": "b", "category": "advertisement"}],
                    "audits": [{"latency_ms": 100, "usage": {"total_tokens": 12}}]}
        result = measure(cases, proposal)
        self.assertEqual(result["heuristic"], {"tp": 0, "fp": 1, "fn": 1, "tn": 0})
        self.assertEqual(result["model"], {"tp": 1, "fp": 0, "fn": 0, "tn": 1})
        self.assertEqual(result["total_tokens"], 12)
        self.assertIsNone(result["cost"])
        with self.assertRaises(ValueError):
            measure(cases + cases, proposal)

    def test_scope_requires_explicit_audience_problem_capabilities_and_exclusions(self):
        with repository() as repo:
            scope = {"id": "builder", "kind": "builder", "audience": "Local AI builders",
                     "problem": "Understand and run local inference, hardware and offline workflows",
                     "capabilities": [], "not_offered": ["Hardware sales", "Hosted inference"]}
            for field in ("audience", "problem", "capabilities", "not_offered", "kind"):
                reader = FakeReader()
                with self.subTest(field=field), self.assertRaises(ValueError):
                    run(repo, reader, project_scope={k: v for k, v in scope.items() if k != field})
                self.assertEqual(reader.calls, [])
            decider = FakeDecider()
            self.assertEqual(run(repo, decider=decider, project_scope=scope)["status"], "proposed")
            sent = decider.calls[0]["project_scope"]
            self.assertEqual(sent["problem"], scope["problem"])
            self.assertEqual(sent["not_offered"], scope["not_offered"])
            for changed in ({"id": "another"}, {"kind": "app"}):
                with self.assertRaises(ValueError):
                    run(repo, project_scope={**scope, **changed})

    def test_whitespace_alignment_retains_original(self):
        with repository() as repo:
            evidence = [{**EVIDENCE[0], "content": "How do I run  local AI offline?"}]
            result = run(repo, evidence=evidence)
            self.assertEqual(result["status"], "proposed")
            self.assertEqual(result["interpretations"][0]["quote"], evidence[0]["content"])
            self.assertNotIn("quote", result["audits"][0]["response"]["items"][0])

    def test_verdict_durable_and_idempotent_without_execution(self):
        with repository() as repo:
            result = run(repo)["cases"][0]
            for _ in range(2):
                record_verdict(repo, project_id="builder", proposal_id=result["proposal_id"], verdict="useful", reason="Worth checking", actor="Patryk")
            self.assertEqual(proposals(repo, "builder")[0]["verdict"]["verdict"], "useful")
            self.assertEqual(sum(e["event_type"] == "radar.review_verdict" for e in repo.events()), 1)
            self.assertEqual(repo.conn.execute("SELECT count(*) FROM briefs").fetchone()[0], 0)
            with self.assertRaises(ValueError):
                record_verdict(repo, project_id="builder", proposal_id="missing", verdict="useful", reason="yes", actor="Patryk")

    def test_non_needs_do_not_create_a_case_or_call_decider(self):
        with repository() as repo:
            decider = FakeDecider()
            result = run(repo, FakeReader({"category": "advertisement", "need": None}), decider)
            self.assertEqual(result["status"], "no_needs")
            self.assertEqual(result["cases"], [])
            self.assertEqual(decider.calls, [])
            self.assertIsNone(result["decision"])

    def test_timeout_fails_once_and_does_not_propose(self):
        with repository() as repo:
            class Offline:
                calls = 0
                def complete(self, **kwargs):
                    self.calls += 1
                    raise APITimeoutError(request=httpx.Request("POST", "http://local/v1"))
            reader, decider = Offline(), FakeDecider()
            for _ in range(2):
                result = run(repo, reader, decider)
                self.assertEqual(result["status"], "failed")
            self.assertEqual(reader.calls, 1)
            self.assertEqual(decider.calls, [])
            self.assertEqual(proposals(repo, "builder"), [])

    def test_non_skip_cannot_cite_unknown_or_non_need_items(self):
        for kind, ids in (("material", ["missing"]), ("material", []), ("reply", ["x:1", "x:1"])):
            with self.subTest(ids=ids), repository() as repo:
                self.assertEqual(run(repo, decider=FakeDecider({"kind": kind, "evidence_ids": ids}))["cases"][0]["status"], "failed")

    def test_interpreter_preserves_quote_case_and_html_entities_in_contract(self):
        with repository() as repo:
            reader = FakeReader()
            result = run(repo, reader)
            self.assertEqual(result["status"], "proposed")
            self.assertIn("Never return quote text", reader.calls[0][1])
            self.assertIn("supplied fragment_id", reader.calls[0][1])

    def test_interpretation_contract_failure_has_named_cause_in_journal(self):
        with repository() as repo:
            result = run(repo, FakeReader({"fragment_id": "unknown"}))
            self.assertEqual(result["failure_message"], "ValueError")
            self.assertEqual(result["reason"], "interpretation_failed_no_fallback")
            again = run(repo, FakeReader({"fragment_id": "unknown"}))
            self.assertEqual(again["failure_message"], result["failure_message"])

    def test_invalid_interpretation_stops_before_decision(self):
        for change in ({"fragment_id": "unknown"}, {"evidence_id": "missing"}, {"category": "advertisement", "need": "fake need"}):
            with self.subTest(change=change), repository() as repo:
                reader, decider = FakeReader(change), FakeDecider()
                for _ in range(2):
                    self.assertEqual(run(repo, reader, decider)["status"], "failed")
                self.assertEqual(len(reader.calls), 1)
                self.assertEqual(decider.calls, [])


if __name__ == "__main__":
    unittest.main()
