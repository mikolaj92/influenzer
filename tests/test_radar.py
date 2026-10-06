import tempfile
import unittest
from pathlib import Path

from influenzer.radar import build_report, collect_due
from influenzer.sources import ObservationStore, Source, observe


class RadarTests(unittest.TestCase):
    def test_tick_runs_enabled_radar_without_publishing(self):
        import io
        from contextlib import redirect_stdout
        from unittest.mock import patch

        from influenzer.tick import main
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "radar.json").write_text("{}")
            with patch("influenzer.radar.run_radar", return_value={"status": "ok"}) as radar, redirect_stdout(io.StringIO()):
                main(["--config", str(Path(tmp) / "config.json"), "--once"])
            radar.assert_called_once_with(Path(tmp))

    def test_cli_radar_disabled_is_explicit(self):
        import io
        import json
        from contextlib import redirect_stdout

        from influenzer.cli import main
        with tempfile.TemporaryDirectory() as tmp, redirect_stdout(io.StringIO()) as out:
            result = main(["--config", str(Path(tmp) / "config.json"), "radar"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(out.getvalue())["status"], "disabled")

    def test_radar_collects_evidence_without_heuristic_interpretation_or_decision(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, ObservationStore(Path(tmp) / "obs.db") as store:
            source = Source("a", "x_search", "local AI")
            payload = {"posts": [{"id": "1", "text": "How do I read a PDF offline?"},
                                 {"id": "2", "text": "I need local AI for documents"}]}
            observe(source, store, read=lambda url: json.dumps(payload).encode(), observed_at="2026-09-30T10:00:00+00:00")
            report = build_report([source], store, project={"id": "docs", "topics": ["local AI"]}, now="2026-09-30T11:00:00+00:00")
            self.assertIsNone(report["decision"])
            self.assertEqual(report["decision_status"], "not_evaluated")
            self.assertNotIn("signals", report)
            self.assertEqual(len(report["evidence"]), 2)

    def test_unrelated_questions_do_not_trigger_project_decision(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, ObservationStore(Path(tmp) / "obs.db") as store:
            source = Source("a", "x_search", "local AI")
            payload = {"posts": [{"id": "1", "text": "Local AI hardware ships to Europe?"},
                                 {"id": "2", "text": "Local AI scenes were broken"}]}
            observe(source, store, read=lambda url: json.dumps(payload).encode(), observed_at="2026-09-30T10:00:00+00:00")
            report = build_report([source], store, project={"id": "docs", "topics": ["local AI"],
                                  "need_terms": ["document", "offline"]}, now="2026-09-30T11:00:00+00:00")
            self.assertIsNone(report["decision"])
            self.assertEqual(len(report["evidence"]), 2)

    def test_topic_evidence_includes_success_posts_for_semantic_review(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, ObservationStore(Path(tmp) / "obs.db") as store:
            source = Source("a", "x_search", "local AI")
            observe(source, store, read=lambda url: json.dumps({"posts": [{"id": "1", "text": "I built local AI for offline PDF"}]}).encode(),
                    observed_at="2026-09-30T10:00:00+00:00")
            report = build_report([source], store, project={"id": "builder", "topics": ["local AI"]}, now="2026-09-30T11:00:00+00:00")
            self.assertNotIn("signals", report)
            self.assertEqual(report["evidence"][0]["content"], "I built local AI for offline PDF")

    def test_due_reads_once_and_failure_waits_for_interval(self):
        with tempfile.TemporaryDirectory() as tmp, ObservationStore(Path(tmp) / "obs.db") as store:
            calls = []
            def broken(url):
                calls.append(url)
                raise TimeoutError("offline")
            sources = [Source("x", "x_search", '"local AI"', 2)]
            first = collect_due(sources, store, interval_seconds=3600, now="2026-09-30T10:00:00+00:00", read=broken)
            second = collect_due(sources, store, interval_seconds=3600, now="2026-09-30T10:05:00+00:00", read=broken)
            self.assertEqual(first["failed"], 1)
            self.assertEqual(second["not_due"], 1)
            self.assertEqual(len(calls), 1)

    def test_report_deduplicates_x_posts_and_excludes_stale_failed_samples(self):
        import json
        with tempfile.TemporaryDirectory() as tmp, ObservationStore(Path(tmp) / "obs.db") as store:
            def response(url):
                return json.dumps({"posts": [{"id": "1", "url": "https://x.com/a/status/1", "text": "How do I run local AI offline?"},
                    {"id": "2", "url": "https://x.com/b/status/2", "text": "I need local AI offline for documents"}], "source": "xsearch"}).encode()
            sources = [Source("a", "x_search", "local AI"), Source("b", "x_profile", "test")]
            for source in sources:
                observe(source, store, read=response, observed_at="2026-09-30T10:00:00+00:00")
            report = build_report(sources, store, project={"id": "local-tools", "topics": ["local AI"], "problem": "Offline document workflows"}, now="2026-09-30T11:00:00+00:00")
            self.assertEqual(report["unique_posts"], 2)
            self.assertEqual(report["duplicate_observations"], 2)
            self.assertEqual(len(report["evidence"]), 2)
            self.assertIsNone(report["decision"])
            self.assertFalse(report["trend_claim"])
            self.assertEqual(report["evidence"][0]["content"], "How do I run local AI offline?")
            def broken(url):
                raise TimeoutError("offline")
            for source in sources:
                observe(source, store, read=broken, observed_at="2026-09-30T11:30:00+00:00")
            report = build_report(sources, store, project={"id": "local-tools", "topics": ["local AI"], "problem": "Offline documents"}, now="2026-09-30T12:00:00+00:00")
            self.assertIsNone(report["decision"])
            self.assertEqual(report["unavailable_sources"], ["a", "b"])


if __name__ == "__main__":
    unittest.main()
