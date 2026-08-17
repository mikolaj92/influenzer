"""Coarse GitHub look: same as scan only when due, else silence.

One job: if it is Monday (Europe/Warsaw) and this Monday has no look yet,
compose existing scan_github (survey → pack → admit). Otherwise emit silence.
A rolling 168h window is not this rhythm. Wednesday because 168h elapsed
is silence. Tick may still score; social look does not.
`--project-id` and `--repo` are required; this block does not invent a
repo inventory.

Does not score. Does not dress. Does not publish. Does not enable live social.
Does not know Heimdall. Does not know my-auth. Does not implement github_pack
shape. Does not call gh (github_survey owns gh). Does not copy survey, pack,
or admit. Does not grow github_survey. Does not run every tick interval.
Does not open runtime.db. Does not embed a Fala host.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
A clock that goes backward is silence, not a second look. Look is monotonic.
Two watches on the same repo are one look. A second brief or angle from the
same git is silence, even with another project_id. That is the machine lock,
not a second survey.
Two ticks the same Monday are one look. The second run sees the done look
and stays silent: no second gh, no second brief. A race on scan/admit is
CAS silence.
Crash mid-look resumes; it does not start from zero. Look already done
and look in progress are two states. A second gh on a half-open look
is an error. Pending brief after a crash is score+angle only, no second
survey/gh.
Watch only on our repo. Owner must be the project maintainer (same
GitHub login). A foreign owner is silence, not a ship. Helping them is
cisza here or contribute, not our launch.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from github_survey import GhRunner, invalid_repo_reason

from influenzer.brief_admit import SOURCE, host_error, host_silence, open_story_reason
from influenzer.brief_scan import scan_github
from influenzer.config import load_config
from influenzer.domain import foreign_owner_reason, utc_now
from influenzer.fala_result import write_fala_result
from influenzer.hom import Brief
from influenzer.storage import StateRepository

DEFAULT_WINDOW_DAYS = 7
CMO_TZ = ZoneInfo("Europe/Warsaw")


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


def current_look_state(repo: StateRepository, repo_slug: str) -> str | None:
    """``in_progress`` or ``done`` for this git. Brief from this look is done.

    ``github.looking`` without a github-scan brief from this look is still
    in progress. An older brief from a previous Monday is not this look.
    A leftover looking event after admit is already done, not a new Monday.
    """
    state = repo.look_state(repo_slug)
    if state != "in_progress":
        return state
    started = parse_utc(repo.look_started_at(repo_slug))
    for brief in repo.list_briefs():
        if brief.source != SOURCE or not brief_mentions_repo(brief, repo_slug):
            continue
        created = parse_utc(brief.created_at)
        if created is None:
            continue
        if started is None or created >= started:
            return "done"
    return "in_progress"


def last_scan_at(repo: StateRepository, project_id: str, repo_slug: str) -> str | None:
    """Newest successful scan event or github-scan brief for this repo.

    Watermark is per git, not per project. ``project_id`` is the caller;
    another project on the same repo does not get a second look.
    """
    _ = project_id
    wanted = _norm_repo(repo_slug)
    found: list[str] = []
    for row in repo.events():
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
    for brief in repo.list_briefs():
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


def warsaw_monday(now: str) -> datetime | None:
    """Monday 00:00 Europe/Warsaw that owns this clock, as UTC. None if unparseable."""
    now_dt = parse_utc(now)
    if now_dt is None:
        return None
    local = now_dt.astimezone(CMO_TZ)
    if local.weekday() != 0:
        return None
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc)


def window_elapsed(last: str | None, now: str, *, window_days: int = DEFAULT_WINDOW_DAYS) -> bool:
    """True when a Monday look is due.

    Calendar is Monday Europe/Warsaw, not rolling 168h. A Wednesday clock
    is not due even if last was more than a week ago. Missing or
    unparseable last → due on Monday (first look). An unparseable now is
    not due. now < last is not due. A set-back clock (NTP, manual) is
    skew, not another Monday. Look is monotonic. ``window_days`` is
    accepted for the old CLI flag and ignored: the rhythm is the
    calendar, not an interval.
    """
    _ = window_days
    monday = warsaw_monday(now)
    if monday is None:
        return False
    now_dt = parse_utc(now)
    if now_dt is None:
        return False
    if last is None:
        return True
    last_dt = parse_utc(last)
    if last_dt is None:
        return True
    if now_dt < last_dt:
        return False
    return last_dt < monday


def scan_due_reason(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    now: str | None = None,
    window_days: int = DEFAULT_WINDOW_DAYS,
) -> str | None:
    """Silence reason if scan-due would not look. None means due. Does not call gh.

    Due is Monday Europe/Warsaw with no look yet this Monday. A rolling
    168h window is not this rhythm. ``window_days`` is ignored.
    """
    slug = repo_slug.strip()
    clock = now or utc_now()
    if invalid_repo_reason(slug):
        return "repo must be owner/name"
    project = repo.get_project(project_id)
    maintainer = project.brand.maintainer if project is not None else None
    foreign = foreign_owner_reason(slug, maintainer)
    if foreign:
        return foreign
    if current_look_state(repo, slug) == "in_progress":
        blocked = open_story_reason(repo, project_id, clock)
        if blocked:
            return blocked
        return None
    blocked = open_story_reason(repo, project_id, clock)
    if blocked:
        return blocked
    last = last_scan_at(repo, project_id, slug)
    if not window_elapsed(last, clock, window_days=window_days):
        return "not due"
    return None


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
    state = current_look_state(repo, slug)
    owner = repo.look_owner(slug)
    if state == "in_progress" and owner and owner != project_id:
        return host_error("half_open_look", project_id=project_id, repo_slug=slug)
    blocked = scan_due_reason(
        repo,
        project_id=project_id,
        repo_slug=slug,
        now=clock,
        window_days=window_days,
    )
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    if repo.look_state(slug) != "in_progress":
        raced = repo.claim_github_look(
            project_id,
            slug,
            started_at=clock,
            due=lambda: scan_due_reason(
                repo,
                project_id=project_id,
                repo_slug=slug,
                now=clock,
                window_days=window_days,
            ),
        )
        if raced:
            if raced == "half_open_look":
                return host_error(raced, project_id=project_id, repo_slug=slug)
            return host_silence(raced, project_id=project_id, repo_slug=slug)
    try:
        out = scan_github(
            repo,
            project_id=project_id,
            repo_slug=slug,
            gh=gh,
            now=clock,
            begun=True,
        )
    except Exception:
        out = host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    repo.record_github_scan(project_id, slug, scanned_at=clock)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer-scan-due")
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--repo", required=True, help="owner/name of a public GitHub repo")
    parser.add_argument("--config", help="path to config.json")
    parser.add_argument("--now", help="ISO-8601 clock for the Monday due check")
    parser.add_argument(
        "--window-days",
        type=int,
        default=DEFAULT_WINDOW_DAYS,
        help="ignored; rhythm is Monday Europe/Warsaw, not a day interval",
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
    "CMO_TZ",
    "DEFAULT_WINDOW_DAYS",
    "brief_mentions_repo",
    "current_look_state",
    "last_scan_at",
    "main",
    "scan_due_reason",
    "scan_github_if_due",
    "warsaw_monday",
    "window_elapsed",
]
