"""Coarse GitHub look: same as scan only when due, else silence.

One job: if a weekly-ish window has elapsed for this project+repo, compose
existing scan_github (survey → pack → admit). Otherwise emit silence.
`--project-id` and `--repo` are required; this block does not invent a
repo inventory.

Does not score. Does not dress. Does not publish. Does not enable live social.
Does not know Heimdall. Does not know my-auth. Does not implement github_pack
shape. Does not call gh (github_survey owns gh). Does not copy survey, pack,
or admit. Does not grow github_survey. Does not run every tick interval.
Does not open runtime.db. Does not embed a Fala host.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from typing import Any

from github_survey import GhRunner, invalid_repo_reason

from influenzer.brief_admit import SOURCE, host_silence, open_story_reason
from influenzer.brief_scan import scan_github
from influenzer.config import load_config
from influenzer.domain import utc_now
from influenzer.fala_result import write_fala_result
from influenzer.hom import Brief
from influenzer.storage import StateRepository

DEFAULT_WINDOW_DAYS = 7


def parse_utc(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _norm_repo(slug: str) -> str:
    return slug.strip().lower()


def _url_repo(url: str) -> str | None:
    parts = url.lower().split("github.com/", 1)
    if len(parts) != 2:
        return None
    bits = [bit for bit in parts[1].split("/") if bit]
    if len(bits) < 2:
        return None
    return f"{bits[0]}/{bits[1]}"


def brief_mentions_repo(brief: Brief, repo_slug: str) -> bool:
    wanted = _norm_repo(repo_slug)
    for fact in brief.facts:
        url = fact.artifact_url or ""
        if _url_repo(url) == wanted:
            return True
    return False


def last_scan_at(repo: StateRepository, project_id: str, repo_slug: str) -> str | None:
    """Newest successful scan event or github-scan brief for this project+repo."""
    wanted = _norm_repo(repo_slug)
    found: list[str] = []
    for row in repo.events(project_id):
        if row["event_type"] != "github.scanned":
            continue
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        if _norm_repo(str(payload.get("repo") or "")) != wanted:
            continue
        ts = payload.get("scanned_at") or row["created_at"]
        if isinstance(ts, str) and ts.strip():
            found.append(ts)
    for brief in repo.list_briefs(project_id):
        if brief.source != SOURCE:
            continue
        if not brief_mentions_repo(brief, repo_slug):
            continue
        if brief.created_at:
            found.append(brief.created_at)
    if not found:
        return None
    dated = [(parse_utc(ts), ts) for ts in found]
    known = [(stamp, raw) for stamp, raw in dated if stamp is not None]
    if not known:
        return None
    return max(known, key=lambda item: item[0])[1]


def window_elapsed(last: str | None, now: str, *, window_days: int) -> bool:
    """True when a look is due. Missing or unparseable last → due (fail closed)."""
    if last is None or window_days < 1:
        return True
    last_dt = parse_utc(last)
    now_dt = parse_utc(now)
    if last_dt is None or now_dt is None:
        return True
    return now_dt - last_dt >= timedelta(days=window_days)


def scan_github_if_due(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    gh: GhRunner | None = None,
    now: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> dict[str, Any]:
    """Compose existing scan only when due. Does not call gh itself."""
    slug = repo_slug.strip()
    clock = now or utc_now()
    if invalid_repo_reason(slug):
        return host_silence("repo must be owner/name", project_id=project_id, repo_slug=slug)
    blocked = open_story_reason(repo, project_id)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    last = last_scan_at(repo, project_id, slug)
    if not window_elapsed(last, clock, window_days=window_days):
        return host_silence("not due", project_id=project_id, repo_slug=slug)
    out = scan_github(repo, project_id=project_id, repo_slug=slug, gh=gh, now=clock)
    repo.record_github_scan(project_id, slug, scanned_at=clock)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-scan-due")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo", required=True, help="owner/name of a public GitHub repo")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--now", help="ISO-8601 clock for the due window")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="coarse cadence in days (default 7)",
    )
    args = parser.parse_args(argv)
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        out = scan_github_if_due(
            repo,
            project_id=args.project_id,
            repo_slug=args.repo,
            now=args.now,
            window_days=args.window_days,
        )
    print(json.dumps(out, sort_keys=True))
    write_fala_result(out, reaction_kind="hom.brief")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DEFAULT_WINDOW_DAYS",
    "brief_mentions_repo",
    "last_scan_at",
    "main",
    "scan_github_if_due",
    "window_elapsed",
]
