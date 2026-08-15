"""Host compose: github_survey → github_pack → admit 0 or 1 brief.

CLI `influenzer brief scan` is this entry. Blocks are explicit extra imports,
not `import influenzer.scan`.

Does not score. Does not publish. Does not enable live social.
Does not implement `gh` — that is github_survey's job.
Does not comment, label, close, or push. Look is GitHub GET only.
Does not git clone. Does not make a worktree. Mini is not a checkout cache.
Does not run the project. Launching on watch is silence.
Tryable is a README+URL heuristic. Code in look is untrusted.
Survey/feedback only through gh api. Reply and code are not this path.
Look stops after N pages. Whole-repo history in one look is silence.
Inbound does not expand the watch. A foreign repo link in an issue stays
text, not a new survey. Look stays on the declared repo.
A fork is not a website. isFork is silence, even when the owner is ours.
Angle comes from the canonical source, not a copy. Helping upstream is
silence here, not our launch.
An empty repo is not a website. No tree or no README is silence. This is
not README-without-a-GIF: here there is not even a card.
A template repo is not a product. isTemplate, or generate-from-template
without an own ship, is silence. Show HN from boilerplate is silence.
A hung gh is silence, not a stuck loop. Timeout is harder and shorter
than the tick interval. After it: cisza, the child is gone, next tick
goes. This is not auth-fail.
"""

from __future__ import annotations

import json
import os
import signal
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from github_pack import pack_survey
from github_survey import GhCall, GhRunner, invalid_repo_reason, survey_public_repo
from github_survey.survey import look_declared_gh, look_short_gh
from influenzer.playbook import (
    looks_like_empty_repo,
    looks_like_failed_ci,
    looks_like_fork,
    looks_like_pending_ci,
    looks_like_template,
)

from influenzer.brief_admit import SOURCE, admit_pack, host_silence, open_story_reason
from influenzer.domain import utc_now
from influenzer.storage import StateRepository
from influenzer.tick import DEFAULT_INTERVAL_SECONDS

# Harder and shorter than the always-on tick interval. A hang is not auth.
GH_HANG_TIMEOUT_S = 20.0
assert GH_HANG_TIMEOUT_S < DEFAULT_INTERVAL_SECONDS


def _kill_lingering_gh() -> None:
    """Best-effort: a timed-out gh child must not stay. Next tick goes."""
    try:
        os.killpg(0, signal.SIGKILL)
    except (OSError, ProcessLookupError, PermissionError):
        return


def look_hard_gh(gh: GhRunner | None = None, *, timeout_s: float = GH_HANG_TIMEOUT_S) -> GhRunner:
    """One gh call may not hang the loop. After timeout: cisza, child gone."""
    from github_survey import run_gh

    inner = gh if gh is not None else run_gh
    deadline = max(0.1, float(timeout_s))

    def _hard(argv: Sequence[str]) -> GhCall:
        box: dict[str, Any] = {}

        def _run() -> None:
            try:
                box["call"] = inner(argv)
            except BaseException as exc:  # hang path must stay silent
                box["exc"] = exc

        worker = threading.Thread(target=_run, name="influenzer-gh", daemon=True)
        worker.start()
        worker.join(deadline)
        if worker.is_alive():
            _kill_lingering_gh()
            return GhCall(returncode=124, stdout="", stderr="gh timeout")
        exc = box.get("exc")
        if isinstance(exc, BaseException):
            return GhCall(returncode=124, stdout="", stderr="gh timeout")
        call = box.get("call")
        if isinstance(call, GhCall):
            return call
        return GhCall(returncode=124, stdout="", stderr="gh timeout")

    return _hard


def look_only_gh(gh: GhRunner | None, repo_slug: str | None = None) -> GhRunner:
    """Look may only GET the declared repo via gh api. Launching is silence."""
    runner = look_hard_gh(look_short_gh(gh))
    slug = (repo_slug or "").strip()
    if not slug:
        return runner
    return look_declared_gh(slug, runner)


def repo_is_fork(gh: GhRunner | None, repo_slug: str) -> bool:
    """True when gh says isFork. Owner does not matter. A copy is not a site."""
    slug = (repo_slug or "").strip()
    if not slug or invalid_repo_reason(slug):
        return False
    runner = look_only_gh(gh, slug)
    try:
        call = runner(["repo", "view", slug, "--json", "isFork"])
    except (OSError, TypeError, ValueError):
        return False
    raw = getattr(call, "stdout", "") or ""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and bool(data.get("isFork"))


def repo_is_empty(gh: GhRunner | None, repo_slug: str) -> bool:
    """True when gh says isEmpty. No tree is not a site."""
    slug = (repo_slug or "").strip()
    if not slug or invalid_repo_reason(slug):
        return False
    runner = look_only_gh(gh, slug)
    try:
        call = runner(["repo", "view", slug, "--json", "isEmpty"])
    except (OSError, TypeError, ValueError):
        return False
    raw = getattr(call, "stdout", "") or ""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and bool(data.get("isEmpty"))


def repo_is_template(gh: GhRunner | None, repo_slug: str) -> bool:
    """True when gh says isTemplate. A template is not a product."""
    slug = (repo_slug or "").strip()
    if not slug or invalid_repo_reason(slug):
        return False
    runner = look_only_gh(gh, slug)
    try:
        call = runner(["repo", "view", slug, "--json", "isTemplate"])
    except (OSError, TypeError, ValueError):
        return False
    raw = getattr(call, "stdout", "") or ""
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False
    return isinstance(data, dict) and bool(data.get("isTemplate"))


def _payload_is_fork(payload: dict[str, Any]) -> bool:
    if bool(payload.get("isFork")):
        return True
    survey = payload.get("survey")
    if not isinstance(survey, dict):
        return False
    meta = survey.get("meta")
    bits: list[str] = []
    if isinstance(meta, dict):
        if bool(meta.get("isFork")):
            return True
        bits.append(str(meta.get("description") or ""))
    bits.append(str(survey.get("readme_text") or ""))
    return looks_like_fork("\n".join(bits))


def _payload_is_empty_repo(payload: dict[str, Any]) -> bool:
    if bool(payload.get("isEmpty")):
        return True
    survey = payload.get("survey")
    if not isinstance(survey, dict):
        return False
    meta = survey.get("meta")
    bits: list[str] = []
    if isinstance(meta, dict):
        if bool(meta.get("isEmpty")):
            return True
        bits.append(str(meta.get("description") or ""))
    readme_text = str(survey.get("readme_text") or "").strip()
    readme_url = str(survey.get("readme_url") or "").strip()
    if not readme_text and not readme_url:
        return True
    bits.append(readme_text)
    return looks_like_empty_repo("\n".join(bits))


def _payload_ci_bits(payload: dict[str, Any]) -> str:
    bits: list[str] = [str(payload.get("reason") or "")]
    survey = payload.get("survey")
    if isinstance(survey, dict):
        bits.append(str(survey.get("readme_text") or ""))
        meta = survey.get("meta")
        if isinstance(meta, dict):
            bits.append(str(meta.get("description") or ""))
        for key in ("prs", "releases", "tags"):
            items = survey.get(key) or []
            if not isinstance(items, list):
                continue
            for item in items:
                if not isinstance(item, dict):
                    continue
                bits.append(str(item.get("title") or ""))
                bits.append(str(item.get("body") or ""))
                bits.append(str(item.get("name") or ""))
                bits.append(str(item.get("tagName") or ""))
    facts = payload.get("facts")
    if isinstance(facts, list):
        for item in facts:
            if isinstance(item, dict):
                bits.append(str(item.get("text") or ""))
    return "\n".join(bits)


def _payload_has_pending_ci(payload: dict[str, Any]) -> bool:
    """Pending / yellow CI is unknown. Not a ship, not a fail, not a stored brief."""
    return looks_like_pending_ci(_payload_ci_bits(payload))


def _payload_has_failed_ci(payload: dict[str, Any]) -> bool:
    """Failed / red CI on the default branch is a false launch. Not tryable."""
    return looks_like_failed_ci(_payload_ci_bits(payload))


def _payload_is_template(payload: dict[str, Any]) -> bool:
    if bool(payload.get("isTemplate")):
        return True
    if payload.get("reason") == "template_not_a_product":
        return True
    survey = payload.get("survey")
    if not isinstance(survey, dict):
        return False
    meta = survey.get("meta")
    bits: list[str] = []
    if isinstance(meta, dict):
        if bool(meta.get("isTemplate")) or bool(meta.get("is_template")):
            return True
        if meta.get("templateRepository") or meta.get("template_repository"):
            return True
        bits.append(str(meta.get("description") or ""))
    bits.append(str(survey.get("readme_text") or ""))
    return looks_like_template("\n".join(bits))


def scan_github(
    repo: StateRepository,
    *,
    project_id: str,
    repo_slug: str,
    gh: GhRunner | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Compose survey → pack → admit. At most one pending brief, or silence."""
    slug = repo_slug.strip()
    if invalid_repo_reason(slug):
        return host_silence("repo must be owner/name", project_id=project_id, repo_slug=slug)
    blocked = open_story_reason(repo, project_id)
    if blocked:
        return host_silence(blocked, project_id=project_id, repo_slug=slug)
    runner = look_only_gh(gh, slug)
    if repo_is_fork(runner, slug):
        return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
    if repo_is_empty(runner, slug):
        return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
    if repo_is_template(runner, slug):
        return host_silence("template_not_a_product", project_id=project_id, repo_slug=slug)
    try:
        surveyed = survey_public_repo(slug, gh=runner, now=now)
        if _payload_is_fork(surveyed):
            return host_silence("fork_not_a_site", project_id=project_id, repo_slug=slug)
        if _payload_is_empty_repo(surveyed):
            return host_silence("empty_repo_not_a_site", project_id=project_id, repo_slug=slug)
        if _payload_is_template(surveyed):
            return host_silence("template_not_a_product", project_id=project_id, repo_slug=slug)
        if _payload_has_pending_ci(surveyed):
            return host_silence("pending_ci_unknown", project_id=project_id, repo_slug=slug)
        if _payload_has_failed_ci(surveyed):
            return host_silence("failed_ci_not_tryable", project_id=project_id, repo_slug=slug)
        packed = pack_survey(surveyed)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return host_silence("empty_survey", project_id=project_id, repo_slug=slug)
    return admit_pack(repo, packed, project_id=project_id, now=now or utc_now())


__all__ = ["SOURCE", "look_only_gh", "repo_is_empty", "repo_is_fork", "repo_is_template", "scan_github"]
