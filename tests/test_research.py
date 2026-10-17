import tempfile
import unittest
from pathlib import Path

from influenzer.domain import Project
from influenzer.research import authorize_research, run_research
from influenzer.storage import StateRepository


class ResearchTests(unittest.TestCase):
    def test_exception_details_are_not_returned_persisted_or_retained(self):
        import json
        from unittest.mock import patch
        from influenzer.tencent_records import retain_record
        secret = "Bearer PRIVATE_TOKEN https://private.example/path?key=PRIVATE_KEY"
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Example"))
            repo.record_radar_event("app", "radar.review_completed", {"record_type": "case", "case": {"need": "Verify source"}, "proposal_id": "p", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Verified source.")
            auth = authorize_research(repo, project_id="app", proposal_id="p", question="What is verified?", actor="Example", reason="test", sources=[{"evidence_id": "d", "content": "Verified source.", "url": "https://example.org", "raw_ref": artifact["digest"]}])
            class BrokenReader:
                calls = 0
                def complete(self, **kwargs):
                    self.calls += 1
                    raise ValueError(secret)
            reader = BrokenReader()
            for _ in range(2):
                result = run_research(repo, project_id="app", authorization_id=auth["authorization_id"], client=reader, model="reader")
                self.assertEqual(result["failure_message"], "ValueError")
                self.assertNotIn(secret, json.dumps(result))
                self.assertNotIn(secret, "".join(e["payload_json"] for e in repo.events("app")))
                with patch("influenzer.tencent_records.TencentRecords.put", return_value={}) as retained:
                    retain_record({"url": "https://records.example", "team_id": "team", "agent_id": "app", "user_id": "owner"}, result)
                self.assertNotIn(secret, json.dumps(retained.call_args.args))
            self.assertEqual(reader.calls, 1)

    def test_cli_exposes_explicit_research_authorization_and_execution(self):
        import argparse

        from influenzer.cli import setup_parser
        parser = argparse.ArgumentParser(); setup_parser(parser)
        args = parser.parse_args(["research", "authorize", "--project-id", "app", "--proposal-id", "p",
            "--question", "Can it run offline?", "--sources", "sources.json", "--actor", "Patryk", "--reason", "Check it"])
        self.assertEqual(args.research_command, "authorize")
        args = parser.parse_args(["research", "run", "--project-id", "app", "--id", "auth-id"])
        self.assertEqual(args.id, "auth-id")
        args = parser.parse_args(["research", "verdict", "--project-id", "app", "--id", "result-id", "--value", "useful",
            "--actor", "Alfred", "--reason", "Supports the narrow question", "--provisional"])
        self.assertTrue(args.provisional)
        self.assertEqual(parser.parse_args(["research", "list", "--project-id", "app"]).research_command, "list")

    def test_cli_executes_once_persists_result_and_labels_agent_verdict(self):
        import io
        import json
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from influenzer.cli import main
        from influenzer.model_review import ReviewConfig
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            home = Path(tmp)
            (home / "config.json").write_text(json.dumps({"home": str(home)}))
            models = ReviewConfig.model_validate({"base_url": "http://reader/v1", "interpretation_model": "reader",
                "decision": {"url": "http://gb10/v1/decisions", "model": "decider"}})
            (home / "radar.json").write_text(json.dumps({"models": models.model_dump(),
                "records": {"url": "http://records", "team_id": "team", "agent_id": "app", "user_id": "owner"}}))
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            repo.record_radar_event("app", "radar.review_completed", {"record_type": "case", "case": {"need": "Check local binding"},
                "proposal_id": "p", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Binds locally.")
            (home / "sources.json").write_text(json.dumps([{"evidence_id": "d", "content": "Binds locally.", "url": "https://example.org", "raw_ref": artifact["digest"]}]))
            prefix = ["--config", str(home / "config.json"), "research"]
            with patch("influenzer.tencent_records.TencentRecords.put", return_value={"backend": "tencentdb", "digest": "a" * 64}) as storage:
                with redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(main(prefix + ["authorize", "--project-id", "app", "--proposal-id", "p", "--sources", str(home / "sources.json"),
                        "--question", "Does it bind locally?", "--actor", "Alfred", "--reason", "authorized test"]), 0)
                auth = json.loads(out.getvalue())
                class Reader:
                    calls = 0
                    def complete(self, **kwargs):
                        self.calls += 1
                        return {"findings": [{"claim": "Binding is local.", "fragment_ids": [kwargs["payload"]["fragments"][0]["fragment_id"]]}], "uncertainty": []}, {}
                reader = Reader()
                with patch("influenzer.model_review.OpenAIModels", return_value=reader):
                    for _ in range(2):
                        with redirect_stdout(io.StringIO()) as out:
                            self.assertEqual(main(prefix + ["run", "--project-id", "app", "--id", auth["authorization_id"]]), 0)
                        result = json.loads(out.getvalue())
                        self.assertEqual(result["record"]["status"], "confirmed")
                        self.assertEqual(result["snapshot"]["configuration"]["base_url"], "http://reader/v1")
                self.assertEqual(reader.calls, 1)
                with redirect_stdout(io.StringIO()) as out:
                    self.assertEqual(main(prefix + ["verdict", "--project-id", "app", "--id", result["proposal_id"], "--value", "useful",
                        "--actor", "Alfred", "--reason", "narrow sourced answer", "--provisional"]), 0)
                self.assertTrue(json.loads(out.getvalue())["provisional"])
                self.assertEqual(storage.call_count, 4)

    def test_legacy_batch_research_is_not_authorization_for_one_case(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            repo.record_radar_event("app", "radar.review_completed", {"proposal_id": "legacy", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Verified source.")
            with self.assertRaisesRegex(ValueError, "research_requires_proposed_research_case"):
                authorize_research(repo, project_id="app", proposal_id="legacy", question="Run everything?", actor="Alfred", reason="test",
                    sources=[{"evidence_id": "d", "content": "Verified source.", "url": "https://example.org", "raw_ref": artifact["digest"]}])

    def test_insufficient_evidence_is_named_not_an_empty_success(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            repo.record_radar_event("app", "radar.review_completed", {"record_type": "case", "case": {"need": "Verify source"},
                "proposal_id": "p", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Documentation only.")
            auth = authorize_research(repo, project_id="app", proposal_id="p", question="Is the detector deployed?", actor="Alfred", reason="test",
                sources=[{"evidence_id": "d", "content": "Documentation only.", "url": "https://example.org", "raw_ref": artifact["digest"]}])
            class Reader:
                calls = 0
                def complete(self, **kwargs):
                    self.calls += 1
                    return {"findings": [], "uncertainty": ["No deployment evidence."]}, {}
            reader = Reader()
            for _ in range(2):
                result = run_research(repo, project_id="app", authorization_id=auth["authorization_id"], client=reader, model="reader")
                self.assertEqual(result["status"], "insufficient_evidence")
                self.assertEqual(result["uncertainty"], ["No deployment evidence."])
            self.assertEqual(reader.calls, 1)

    def test_authorized_sources_are_reverified_before_execution(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            repo.record_radar_event("app", "radar.review_completed", {"record_type": "case", "case": {"need": "Verify source", "evidence_ids": ["post:1"]}, "proposal_id": "p", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Retained evidence.")
            auth = authorize_research(repo, project_id="app", proposal_id="p", question="What is retained?", actor="Alfred", reason="test",
                sources=[{"evidence_id": "d", "content": "Retained evidence.", "url": "https://example.org", "raw_ref": artifact["digest"]}])
            from unittest.mock import Mock, patch
            reader = Mock()
            with patch.object(repo.artifacts, "verify", side_effect=OSError("artifact missing")):
                result = run_research(repo, project_id="app", authorization_id=auth["authorization_id"], client=reader, model="reader")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["failed_stage"], "source_verification")
            reader.complete.assert_not_called()

    def test_unknown_research_citation_is_failed_and_never_retried(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            repo.record_radar_event("app", "radar.review_completed", {"record_type": "case", "case": {"need": "Verify source", "evidence_ids": ["post:1"]}, "proposal_id": "p", "status": "proposed", "decision": {"kind": "research"}})
            artifact = repo.artifacts.put(b"Verified source.")
            auth = authorize_research(repo, project_id="app", proposal_id="p", question="What is verified?", actor="Alfred", reason="integration test",
                sources=[{"evidence_id": "d", "content": "Verified source.", "url": "https://example.org", "raw_ref": artifact["digest"]}])
            class Invalid:
                calls = 0
                def complete(self, **kwargs):
                    self.calls += 1
                    return {"findings": [{"claim": "unsupported", "fragment_ids": ["unknown"]}], "uncertainty": []}, {}
            reader = Invalid()
            for _ in range(2):
                result = run_research(repo, project_id="app", authorization_id=auth["authorization_id"], client=reader, model="reader")
                self.assertEqual(result["status"], "failed")
                self.assertEqual(result["failure_message"], "ValueError")
            self.assertEqual(reader.calls, 1)
            run_research(repo, project_id="app", authorization_id=auth["authorization_id"], client=reader, model="reader",
                configuration={"base_url": "http://explicitly-changed", "json_mode": False})
            self.assertEqual(reader.calls, 2)

    def test_research_requires_exact_authorization_then_one_cited_result_without_publication(self):
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            repo.save_project(Project.create(project_id="app", slug="app", name="App", display_name="App", voice="practical", audience="builders", maintainer="Patryk"))
            proposal = {"record_type": "case", "proposal_id": "proposal", "project_id": "app", "status": "proposed",
                        "case": {"need": "Run offline", "evidence_ids": ["post:1"]}, "decision": {"kind": "research"}}
            repo.record_radar_event("app", "radar.review_completed", proposal)
            content = "A local server binds to localhost by default."
            artifact = repo.artifacts.put(content.encode())
            sources = [{"evidence_id": "doc:1", "content": content, "url": "https://example.org/docs", "raw_ref": artifact["digest"]}]
            authorization = authorize_research(repo, project_id="app", proposal_id="proposal", question="Can this run locally?",
                                               sources=sources, actor="Patryk", reason="Check before claiming offline operation")
            class Reader:
                def __init__(self):
                    self.calls = []
                def complete(self, **kwargs):
                    self.calls.append(kwargs)
                    fragment = kwargs["payload"]["fragments"][0]
                    return {"findings": [{"claim": "The default binding is local.", "fragment_ids": [fragment["fragment_id"]]}],
                            "uncertainty": ["Local binding alone does not prove zero outbound traffic."]}, {"model": "reader"}
            reader = Reader()
            with self.assertRaises(ValueError):
                run_research(repo, project_id="app", authorization_id="missing", client=reader, model="reader")
            for _ in range(2):
                result = run_research(repo, project_id="app", authorization_id=authorization["authorization_id"], client=reader, model="reader")
                self.assertEqual(result["status"], "completed")
                self.assertEqual(result["findings"][0]["citations"][0]["quote"], sources[0]["content"])
                self.assertFalse(result["published"])
            self.assertEqual(len(reader.calls), 1)
            from influenzer.research import record_result_verdict, research_results
            verdict = record_result_verdict(repo, project_id="app", result_id=result["proposal_id"], value="useful",
                actor="Alfred", reason="Evidence answers the authorized narrow question", provisional=True)
            record_result_verdict(repo, project_id="app", result_id=result["proposal_id"], value="useful",
                actor="Alfred", reason="Evidence answers the authorized narrow question", provisional=True)
            self.assertEqual(research_results(repo, "app")[0]["verdict"], verdict)
            self.assertEqual(len([e for e in repo.events("app") if e["event_type"] == "radar.research_verdict"]), 1)
            self.assertEqual(repo.conn.execute("SELECT count(*) FROM briefs").fetchone()[0], 0)
            with self.assertRaises((ValueError, OSError)):
                authorize_research(repo, project_id="app", proposal_id="proposal", question="Another question?",
                    sources=[{**sources[0], "content": "Invented text not in artifact"}], actor="Patryk", reason="check")
