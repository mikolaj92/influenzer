"""Declared watch: one project → one repo the interval tick may look at.

One job: persist an explicit watch, and let the always-on interval loop
compose existing hom_pass when scan-due would consider that watch due.
`--once` stays score-only unless `--pass-if-due`.

Does not invent a repo inventory. Does not copy scan_due or hom_pass.
Does not publish. Does not enable live social. Does not call gh
(github_survey owns gh). Does not know Heimdall. Does not know my-auth.
Does not run pass every interval. Does not open runtime.db.
Does not embed a Fala host. Watch set is host CLI only.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from github_survey import invalid_repo_reason

from influenzer.config import Config, open_workspace
from influenzer.domain import utc_now
from influenzer.envelope import fail, noop, ok
from influenzer.hom_pass import run_pass
from influenzer.scan_due import scan_due_reason
from influenzer.scheduler import tick
from influenzer.storage import StateRepository, StorageError


@dataclass(frozen=True)
class Watch:
    project_id: str
    repo_slug: str
    created_at: str


def get_watch(repo: StateRepository) -> Watch | None:
    row = repo.get_hom_watch()
    if row is None:
        return None
    return Watch(project_id=row["project_id"], repo_slug=row["repo"], created_at=row["created_at"])


def set_watch(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    now: str | None = None,
) -> dict[str, Any]:
    """Declare the singleton watch. Replaces any previous watch. No gh."""
    slug = repo_slug.strip()
    bad = invalid_repo_reason(slug)
    if bad:
        return fail(bad, published=False)
    if repo.get_project(project_id) is None:
        return fail("project not found", published=False)
    clock = now or utc_now()
    try:
        repo.set_hom_watch(project_id, slug, created_at=clock)
    except StorageError as exc:
        return fail(str(exc), published=False)
    return ok(project_id=project_id, repo=slug, published=False)


def show_watch(repo: StateRepository) -> dict[str, Any]:
    watch = get_watch(repo)
    if watch is None:
        return noop("no_watch", published=False)
    return ok(
        project_id=watch.project_id,
        repo=watch.repo_slug,
        created_at=watch.created_at,
        published=False,
    )


def interval_tick(
    repo: StateRepository,
    cfg: Config,
    *,
    allow_hom_pass: bool,
    cli_live: bool = False,
    gh: Any = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Score pending briefs. If allow_hom_pass and a due watch, run hom_pass once."""
    clock = now or utc_now()
    if allow_hom_pass:
        watch = get_watch(repo)
        if watch is not None:
            blocked = scan_due_reason(
                repo,
                project_id=watch.project_id,
                repo_slug=watch.repo_slug,
                now=clock,
            )
            if blocked is None:
                return run_pass(
                    repo,
                    cfg,
                    project_id=watch.project_id,
                    repo_slug=watch.repo_slug,
                    gh=gh,
                    now=clock,
                )
    return tick(repo, cfg, due=(), cli_live=cli_live, now=clock)


def run_watched_tick(
    *,
    config_path: str | None = None,
    cli_live: bool = False,
    allow_hom_pass: bool = False,
    gh: Any = None,
    now: str | None = None,
) -> dict[str, Any]:
    """One interval step against state.db. Does not open runtime.db."""
    cfg = open_workspace(config_path)
    with StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts") as repo:
        return interval_tick(
            repo,
            cfg,
            allow_hom_pass=allow_hom_pass,
            cli_live=cli_live,
            gh=gh,
            now=now,
        )


__all__ = [
    "Watch",
    "get_watch",
    "interval_tick",
    "run_watched_tick",
    "set_watch",
    "show_watch",
]
