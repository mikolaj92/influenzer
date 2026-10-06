"""Read-only source observations through datasource-kit's opt-in ingest.

Snapshots are append-only per run; source outages never erase prior evidence.
A successful read describes a bounded feed, not full platform coverage.
"""
from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

import feedparser
from datasource_kit import SourceProfile, builtin_registry, run_ingest

from influenzer.storage import ArtifactStore


@dataclass(frozen=True, slots=True)
class Source:
    source_id: str
    provider: str
    target: str
    limit: int = 100

    def __post_init__(self):
        if not self.source_id.strip() or self.provider not in {"rss", "hn", "x_profile", "x_search"}:
            raise ValueError("non-empty source_id and supported provider required")
        if not 1 <= self.limit <= 500:
            raise ValueError("limit must be between 1 and 500")
        if self.provider == "rss" and urlparse(self.target).scheme not in {"http", "https"}:
            raise ValueError("RSS target must be HTTP(S)")
        if self.provider == "hn" and self.target not in {"topstories", "newstories", "beststories"}:
            raise ValueError("unsupported Hacker News feed")
        if self.provider in {"x_profile", "x_search"} and (not self.target.strip() or self.limit > 100):
            raise ValueError("x-md requires a target and limit at most 100")
        if self.provider == "x_profile" and (
            not self.target or len(self.target) > 15
            or not all(c.isascii() and (c.isalnum() or c == "_") for c in self.target)
        ):
            raise ValueError("X target must be a public handle without @")


def read_url(url: str) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": "influenzer/0.1"}), timeout=20) as response:
        data = response.read(2_000_001)
    if len(data) > 2_000_000:
        raise ValueError("source response exceeds 2MB")
    return data


class ObservationStore:
    """Separate observation database; never changes the operator state schema."""

    def __init__(self, path: str | Path):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.artifacts = ArtifactStore(path.parent / "source-artifacts")
        self.conn.executescript('''
            CREATE TABLE IF NOT EXISTS source_observations (
                run_id TEXT NOT NULL, source_id TEXT NOT NULL, id TEXT NOT NULL,
                payload TEXT NOT NULL, PRIMARY KEY(run_id, source_id, id));
            CREATE TABLE IF NOT EXISTS source_reads (
                run_id TEXT PRIMARY KEY, source_id TEXT NOT NULL, payload TEXT NOT NULL);
        ''')

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.conn.close()

    def history(self, source_id: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.conn.execute(
            "SELECT payload FROM source_observations WHERE source_id=? ORDER BY rowid", (source_id,))]

    def reports(self, source_id: str) -> list[dict]:
        return [json.loads(row[0]) for row in self.conn.execute(
            "SELECT payload FROM source_reads WHERE source_id=? ORDER BY rowid", (source_id,))]


def observe(source: Source, store: ObservationStore, *, read: Callable[[str], bytes] = read_url,
            observed_at: str | None = None) -> dict:
    """One bounded read. Kit owns execution/reporting; consumer owns records."""
    run_id = uuid.uuid4().hex
    at = observed_at or datetime.now(UTC).isoformat()
    coverage: dict[str, object] = {"available": None, "truncated": None}

    def fetch(window, config):
        if source.provider in {"x_profile", "x_search"}:
            params = {"format": "json", "limit": source.limit}
            route = f"profiles/{source.target}"
            if source.provider == "x_search":
                route = "search"
                params.update(q=source.target, feed="latest")
            query = urlencode(params)
            raw = read(f"https://x.pcstyle.dev/api/v1/{route}?{query}")
            data = json.loads(raw)
            if not isinstance(data, dict) or not isinstance(data.get("posts"), list):
                raise ValueError("invalid x-md posts response")
            posts = data["posts"]
            coverage.update(available=len(posts), truncated=bool(data.get("nextCursor")) or len(posts) > source.limit,
                            next_cursor=data.get("nextCursor"), upstream_source=data.get("source"),
                            upstream_cache=data.get("cache"))
            if data.get("source") == "firecrawl" or data.get("warnings"):
                raise ValueError(f"x-md incomplete response: {data.get('warnings', 'web-index fallback')}")
            ref = store.artifacts.put(raw)["digest"]
            records = []
            for post in posts[:source.limit]:
                if not isinstance(post, dict) or not post.get("id") or not isinstance(post.get("text"), str):
                    raise ValueError("invalid x-md post identity or text")
                timestamp = post.get("created_timestamp")
                records.append({
                    "id": str(post["id"]), "source_id": source.source_id,
                    "external_id": str(post["id"]), "observed_at": at,
                    "published_at": datetime.fromtimestamp(timestamp, UTC).isoformat() if timestamp is not None else None,
                    "url": post.get("url") or f"https://x.com/{source.target}/status/{post['id']}",
                    "content": post["text"],
                    "metrics": {k: post[k] for k in ("likes", "replies", "reposts", "quotes", "views", "bookmarks")
                                if post.get(k) is not None},
                    "raw_ref": ref,
                })
            return records
        if source.provider == "hn":
            base = "https://hacker-news.firebaseio.com/v0"
            ids = json.loads(read(f"{base}/{source.target}.json"))
            if not isinstance(ids, list) or any(type(i) is not int or i <= 0 for i in ids):
                raise ValueError("invalid Hacker News feed IDs")
            coverage.update(available=len(ids), truncated=len(ids) > source.limit)
            records = []
            for item_id in ids[:source.limit]:
                raw = read(f"{base}/item/{item_id}.json")
                item = json.loads(raw)
                if not isinstance(item, dict) or item.get("id") != item_id:
                    raise ValueError("invalid Hacker News item")
                if item.get("deleted") or item.get("dead"):
                    continue
                ref = store.artifacts.put(raw)["digest"]
                records.append({
                    "id": str(item_id), "source_id": source.source_id,
                    "external_id": str(item_id), "observed_at": at,
                    "published_at": datetime.fromtimestamp(item["time"], UTC).isoformat() if "time" in item else None,
                    "url": f"https://news.ycombinator.com/item?id={item_id}",
                    "content": item.get("title", "") + "\n" + item.get("text", ""),
                    "metrics": {k: item[k] for k in ("score", "descendants") if k in item},
                    "raw_ref": ref,
                })
            return records
        raw = read(source.target)
        ref = store.artifacts.put(raw)["digest"]
        feed = feedparser.parse(raw)
        if feed.bozo or not feed.version:
            raise ValueError("invalid feed")
        coverage.update(available=len(feed.entries), truncated=len(feed.entries) > source.limit)
        records = []
        for entry in feed.entries[:source.limit]:
            url = entry.get("link", "")
            external_id = entry.get("id") or url
            if not external_id:
                raise ValueError("feed entry has no stable identity")
            published = entry.get("published_parsed")
            records.append({
                "id": str(external_id), "source_id": source.source_id,
                "external_id": str(external_id), "observed_at": at,
                "published_at": datetime(*published[:6], tzinfo=UTC).isoformat() if published else None,
                "url": url, "content": entry.get("title", "") + "\n" + entry.get("summary", ""),
                "metrics": {}, "raw_ref": ref,
            })
        return records

    class Driver:
        def load(self):
            return store.history(source.source_id)

        def upsert(self, records):
            for record in records:
                store.conn.execute("INSERT INTO source_observations VALUES(?,?,?,?)",
                                   (run_id, source.source_id, record["id"], json.dumps(record)))

    registry = builtin_registry()
    registry.register("window.source", lambda config: [{"observed_at": at}], category="enumerator")
    registry.register("fetch.source", fetch, category="fetcher")
    registry.register("store.observations", Driver, category="store")
    registry.register("diff.observations", lambda fetched, stored, config: {
        "observed": len(fetched),
        "first_seen": sorted({r["id"] for r in fetched} - {r["id"] for r in stored}),
    }, category="diff")
    # Do not use assess.passthrough: it can label failed reads 'ok'.
    registry.register("assess.source", lambda records, window, config: {"count": len(records)}, category="assess")
    profile = SourceProfile(name=source.source_id, source_type=source.provider, providers={
        "enumerator": "window.source", "fetcher": "fetch.source", "mapper": "records.passthrough",
        "store": "store.observations", "diff": "diff.observations", "assess": "assess.source",
    }, policies={"retry": {"attempts": 1}, "source": {"target": source.target, "limit": source.limit}})
    with store.conn:
        report = run_ingest(profile, registry=registry).as_dict()
        report.update(run_id=run_id, observed_at=at, target=source.target,
                      scope="bounded_feed", limit=source.limit, **coverage)
        store.conn.execute("INSERT INTO source_reads VALUES(?,?,?)", (run_id, source.source_id, json.dumps(report)))
    return report
