import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from influenzer.sources import ObservationStore, Source, observe

RSS = b'''<rss version="2.0"><channel><title>Blog</title><link>https://example.org</link><description>Blog</description><item><guid>one</guid><title>Local tools</title><description>First text</description><link>https://example.org/one</link></item></channel></rss>'''


class SourceTests(unittest.TestCase):
    def test_rss_history_survives_repeat_reads_and_restart(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.db"
            source = Source("blog", "rss", "https://example.org/feed")
            with ObservationStore(path) as store:
                first = observe(source, store, read=lambda url: RSS, observed_at="2026-09-30T10:00:00Z")
                second = observe(source, store, read=lambda url: RSS.replace(b"First text", b"Updated text"), observed_at="2026-09-30T11:00:00Z")
                self.assertEqual(first["records_fetched"], 1)
                self.assertEqual(second["records_fetched"], 1)
                self.assertIsNone(first["completeness"])
            with ObservationStore(path) as store:
                history = store.history("blog")
                self.assertEqual(len(history), 2)
                self.assertEqual(history[0]["external_id"], history[1]["external_id"])
                self.assertNotEqual(history[0]["content"], history[1]["content"])
                self.assertNotEqual(history[0]["raw_ref"], history[1]["raw_ref"])
                self.assertEqual(history[0]["metrics"], {})
                self.assertEqual(len(store.reports("blog")), 2)

    def test_hn_metrics_change_without_overwriting_history(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                score = [3]
                calls = []
                def read(url):
                    calls.append(url)
                    if url.endswith("topstories.json"):
                        return b"[42, 43]"
                    return json.dumps({"id": 42, "title": "Tools", "time": 100,
                                       "score": score[0], "descendants": 2}).encode()
                source = Source("hn-top", "hn", "topstories", limit=1)
                first = observe(source, store, read=read)
                score[0] = 9
                observe(source, store, read=read)
                history = store.history("hn-top")
                self.assertEqual([r["metrics"]["score"] for r in history], [3, 9])
                self.assertEqual(history[0]["url"], "https://news.ycombinator.com/item?id=42")
                self.assertEqual(first["scope"], "bounded_feed")
                self.assertTrue(first["truncated"])
                self.assertEqual(first["available"], 2)
                self.assertEqual(len(calls), 4)
                self.assertFalse(any("43.json" in url for url in calls))

    def test_x_profile_records_posts_metrics_and_pagination(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                calls = []
                def read(url):
                    calls.append(url)
                    return json.dumps({"posts": [{"id": "123", "url": "https://x.com/test/status/123",
                        "text": "Need local tools", "created_timestamp": 100,
                        "likes": 7, "views": None}], "nextCursor": "opaque", "source": "fxtwitter",
                        "cache": "hit"}).encode()
                report = observe(Source("x-test", "x_profile", "test", 2), store, read=read)
                self.assertEqual(report["status"], "ok")
                self.assertEqual(len(calls), 1)
                self.assertIn("/api/v1/profiles/test?", calls[0])
                self.assertIn("format=json", calls[0])
                self.assertEqual(report["next_cursor"], "opaque")
                self.assertEqual(report["upstream_source"], "fxtwitter")
                self.assertEqual(report["upstream_cache"], "hit")
                self.assertTrue(report["truncated"])
                record = store.history("x-test")[0]
                self.assertEqual(record["content"], "Need local tools")
                self.assertEqual(record["metrics"], {"likes": 7})
                self.assertEqual(record["published_at"], "1970-01-01T00:01:40+00:00")

    def test_x_search_encodes_query_and_rejects_degraded_results(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                calls = []
                def read(url):
                    calls.append(url)
                    return json.dumps({"posts": [], "source": "firecrawl", "warnings": ["degraded"]}).encode()
                report = observe(Source("x-needs", "x_search", '"local AI"', 10), store, read=read)
                self.assertEqual(report["status"], "partial")
                self.assertEqual(len(calls), 1)
                self.assertIn("/api/v1/search?", calls[0])
                self.assertIn("q=%22local+AI%22", calls[0])
                self.assertEqual(store.history("x-needs"), [])

    def test_x_invalid_response_is_not_an_empty_feed(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                report = observe(Source("x-test", "x_profile", "test", 2), store,
                                 read=lambda url: b'{"code":"rate_limited"}')
                self.assertEqual(report["status"], "partial")
                self.assertTrue(report["warnings"])
                self.assertIsNone(report["available"])

    def test_empty_feed_is_distinct_from_invalid_feed(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                source = Source("blog", "rss", "https://example.org/feed")
                empty = RSS[:RSS.index(b"<item>")] + b"</channel></rss>"
                good = observe(source, store, read=lambda url: empty)
                bad = observe(source, store, read=lambda url: b"not a feed")
                self.assertEqual(good["status"], "ok")
                self.assertEqual(good["available"], 0)
                self.assertEqual(bad["status"], "partial")
                self.assertIsNone(bad["available"])

    def test_source_cli_reads_profile_and_prints_history(self):
        from influenzer.cli import main
        with tempfile.TemporaryDirectory() as tmp:
            profile = Path(tmp) / "source.json"
            profile.write_text(json.dumps({"source_id": "blog", "provider": "rss", "target": "https://example.org/feed"}))
            config = str(Path(tmp) / "config.json")
            main(["--config", config, "init", "--home", tmp])
            with patch("influenzer.sources.read_url", return_value=RSS), redirect_stdout(io.StringIO()) as output:
                result = main(["--config", config, "source", "read", "--profile", str(profile)])
            self.assertEqual(result, 0)
            self.assertEqual(json.loads(output.getvalue())["records_fetched"], 1)
            with redirect_stdout(io.StringIO()) as output:
                result = main(["--config", config, "source", "history", "--id", "blog"])
            self.assertEqual(result, 0)
            self.assertEqual(len(json.loads(output.getvalue())), 1)

    def test_failed_read_is_reported_without_erasing_history(self):
        with tempfile.TemporaryDirectory() as tmp:  # noqa: SIM117 -- store depends on tmp
            with ObservationStore(Path(tmp) / "observations.db") as store:
                source = Source("blog", "rss", "https://example.org/feed")
                observe(source, store, read=lambda url: RSS)
                calls = []
                def broken(url):
                    calls.append(url)
                    raise TimeoutError("upstream timeout")
                report = observe(source, store, read=broken)
                self.assertEqual(report["status"], "partial")
                self.assertTrue(report["warnings"])
                self.assertEqual(len(store.history("blog")), 1)
                self.assertEqual(len(store.reports("blog")), 2)
                self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
