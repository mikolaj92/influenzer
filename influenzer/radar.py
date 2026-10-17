"""Collect bounded evidence only; interpretation and decisions belong to review."""
from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

from influenzer.sources import ObservationStore, Source, observe, read_url


def clock(value: str) -> datetime:
    at = datetime.fromisoformat(value)
    if at.tzinfo is None:
        raise ValueError("timezone required")
    return at


def collect_due(sources: list[Source], store: ObservationStore, *, interval_seconds: int,
                now: str, read: Callable[[str], bytes] = read_url) -> dict:
    if interval_seconds < 900:
        raise ValueError("radar interval must be at least 900 seconds")
    result = {"ok": 0, "failed": 0, "not_due": 0, "reads": []}
    for source in sources:
        reports = store.reports(source.source_id)
        if reports and (clock(now) - clock(reports[-1]["observed_at"])).total_seconds() < interval_seconds:
            result["not_due"] += 1
            continue
        report = observe(source, store, observed_at=now, read=read)
        result["ok" if report["status"] == "ok" else "failed"] += 1
        result["reads"].append(report)
    return result


def build_report(sources: list[Source], store: ObservationStore, *, project: dict,
                 now: str, max_age_seconds: int = 86400) -> dict:
    topics = project.get("topics", [])
    if not project.get("id") or not topics or not all(isinstance(t, str) and t.strip() for t in topics):
        raise ValueError("project id and non-empty topics required")
    unique = {}
    duplicate_count = 0
    unavailable = []
    coverage = []
    for source in sources:
        reads = store.reports(source.source_id)
        latest = reads[-1] if reads else None
        age = (clock(now) - clock(latest["observed_at"])).total_seconds() if latest else None
        usable = latest is not None and latest["status"] == "ok" and age is not None and 0 <= age <= max_age_seconds
        coverage.append({"source_id": source.source_id, "usable": usable, "read": latest})
        if not usable or latest is None:
            unavailable.append(source.source_id)
            continue
        for row in store.history(source.source_id):
            if row["observed_at"] != latest["observed_at"]:
                continue
            url = row["url"]
            parsed = urlparse(url)
            # X handle variations must not multiply evidence for the same post.
            key = "x:" + row["external_id"] if parsed.hostname in {"x.com", "twitter.com", "www.x.com"} else url or source.source_id + ":" + row["external_id"]
            if key in unique:
                duplicate_count += 1
                continue
            unique[key] = row
    return {"generated_at": now, "project_id": project["id"], "method": "bounded_evidence_v2",
            "trend_claim": False, "unique_posts": len(unique), "duplicate_observations": duplicate_count,
            "unavailable_sources": unavailable, "coverage": coverage,
            "evidence": [{"evidence_id": key, **row} for key, row in unique.items()],
            "decision": None, "decision_status": "not_evaluated"}


def run_radar(home: Path, *, read: Callable[[str], bytes] = read_url) -> dict:
    path = home / "radar.json"
    if not path.exists():
        return {"status": "disabled"}
    config = json.loads(path.read_text())
    sources = [Source(**item) for item in config["sources"]]
    if len({s.source_id for s in sources}) != len(sources):
        raise ValueError("radar source IDs must be unique")
    if sum(s.provider == "x_search" for s in sources) > 5:
        raise ValueError("at most 5 X searches per radar cycle")
    now = datetime.now(UTC).isoformat()
    with ObservationStore(home / "observations.db") as store:
        collected = collect_due(sources, store, interval_seconds=config.get("interval_seconds", 21600), now=now, read=read)
        report = build_report(sources, store, project=config["project"], now=now)
    report["collection"] = collected
    report["status"] = "partial" if report["unavailable_sources"] else "ok"
    destination = home / "radar-latest.json"
    temporary = destination.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(destination)
    return report
