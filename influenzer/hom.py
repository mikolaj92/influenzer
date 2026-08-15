"""Head of Marketing operator: Brief in, Score, Draft or explicit kill.

Pure rules. No provider calls. Live publish stays on the existing policy/adapter path.
Influenzer does not need Heimdall internals; briefs arrive, drafts leave.

Scoring lives here. Costume-native copy is influenzer.hom_draft (thin call).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from influenzer.domain import DomainError, content_hash, require_slug, utc_now
from influenzer.playbook import (
    ANGLES,
    ARENAS,
    ArenaGate,
    ArenaId,
    CANON_URL,
    MIN_FACT_CHARS,
    MIN_SOCIAL_FACTS,
    StoryKind,
    Verdict,
    arena_gate,
    arena_play,
    has_cinema_package,
    has_fair_hook,
    has_named_subreddit,
    is_blog_host_url,
    is_launch_host_url,
    is_merge_log_texts,
    is_news_host_url,
    is_ranking_host_url,
    is_ship_artifact_url,
    is_social_arena,
    is_store_host_url,
    is_video_host_url,
    looks_like_commit_noise,
    looks_like_contest,
    looks_like_dunk,
    looks_like_foreign_wave,
    looks_like_engagement_bait,
    looks_like_ranking_dump,
    looks_like_thread,
    looks_like_emoji_title,
    looks_like_hashtag_wall,
    looks_like_listicle_title,
    looks_like_hire_fundraise,
    looks_like_private_conversation,
    looks_like_source_available_as_oss,
    looks_like_press_release,
    looks_like_world_commentary,
    news_urls_only,
    looks_like_shouty_title,
    looks_like_store_pitch,
    looks_like_launch_pitch,
    looks_like_superlative,
    looks_like_dead_link,
    looks_like_dead_release_asset,
    looks_like_issues_disabled,
    looks_like_fork,
    looks_like_empty_repo,
    looks_like_login_gate,
    looks_like_server_splash,
    looks_like_roadmap,
    looks_like_waitlist,
    ranking_urls_only,
    unquotable_reason,
)

_SECRET_KEYS = frozenset(
    {
        "token",
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "authorization",
        "credential",
        "access_token",
        "refresh_token",
        "client_secret",
    }
)


class HomError(DomainError):
    pass


@dataclass(frozen=True)
class Fact:
    """One signal in a brief. Many facts; the operator picks one angle."""

    text: str
    kind: str = "signal"
    artifact_url: str | None = None

    def __post_init__(self) -> None:
        if not self.text.strip():
            raise HomError("fact text must not be empty")
        if self.kind.strip() != self.kind or not self.kind:
            raise HomError("fact kind must be a non-empty string")


@dataclass(frozen=True)
class Brief:
    """Many facts at once. Not a single commit/event."""

    project_id: str
    brief_id: str
    facts: tuple[Fact, ...]
    story_kind: StoryKind
    claims_ship: bool = False
    tryable: bool = False
    preferred_arena: ArenaId | None = None
    source: str = "manual"
    status: str = "pending"
    created_at: str = ""

    @staticmethod
    def create(
        *,
        project_id: str,
        brief_id: str,
        facts: tuple[Fact, ...] | list[Fact],
        story_kind: StoryKind | str,
        claims_ship: bool = False,
        tryable: bool = False,
        preferred_arena: ArenaId | str | None = None,
        source: str = "manual",
        created_at: str | None = None,
        status: str = "pending",
    ) -> "Brief":
        require_slug(brief_id, "brief_id")
        kind = story_kind if isinstance(story_kind, StoryKind) else StoryKind(story_kind)
        arena: ArenaId | None
        if preferred_arena is None or preferred_arena == "":
            arena = None
        elif isinstance(preferred_arena, ArenaId):
            arena = preferred_arena
        else:
            try:
                arena = ArenaId(preferred_arena)
            except ValueError as exc:
                raise HomError(f"unknown arena: {preferred_arena}") from exc
        packed = tuple(facts)
        if status not in {"pending", "processed"}:
            raise HomError("brief status must be pending|processed")
        return Brief(
            project_id=project_id,
            brief_id=brief_id,
            facts=packed,
            story_kind=kind,
            claims_ship=bool(claims_ship),
            tryable=bool(tryable),
            preferred_arena=arena,
            source=source,
            status=status,
            created_at=created_at or utc_now(),
        )


@dataclass(frozen=True)
class Score:
    brief_id: str
    verdict: Verdict
    reason: str
    arena: ArenaId | None
    angle: str | None
    wave_checklist: tuple[str, ...]
    canon_url: str
    score_hash: str = ""

    def with_hash(self) -> "Score":
        payload = {
            "brief_id": self.brief_id,
            "verdict": self.verdict.value,
            "reason": self.reason,
            "arena": None if self.arena is None else self.arena.value,
            "angle": self.angle,
            "wave_checklist": list(self.wave_checklist),
            "canon_url": self.canon_url,
        }
        return Score(
            brief_id=self.brief_id,
            verdict=self.verdict,
            reason=self.reason,
            arena=self.arena,
            angle=self.angle,
            wave_checklist=self.wave_checklist,
            canon_url=self.canon_url,
            score_hash=content_hash(payload),
        )


@dataclass(frozen=True)
class Draft:
    """Costume-native copy for one arena. Never an auto-publish."""

    project_id: str
    brief_id: str
    draft_id: str
    arena: ArenaId
    costume: str
    angle: str
    body: str
    wave_checklist: tuple[str, ...]
    canon_url: str
    created_at: str
    content_hash: str = ""

    def with_hash(self) -> "Draft":
        payload = {
            "project_id": self.project_id,
            "brief_id": self.brief_id,
            "draft_id": self.draft_id,
            "arena": self.arena.value,
            "costume": self.costume,
            "angle": self.angle,
            "body": self.body,
            "wave_checklist": list(self.wave_checklist),
            "canon_url": self.canon_url,
            "created_at": self.created_at,
        }
        return Draft(
            project_id=self.project_id,
            brief_id=self.brief_id,
            draft_id=self.draft_id,
            arena=self.arena,
            costume=self.costume,
            angle=self.angle,
            body=self.body,
            wave_checklist=self.wave_checklist,
            canon_url=self.canon_url,
            created_at=self.created_at,
            content_hash=content_hash(payload),
        )


@dataclass(frozen=True)
class OperatorDecision:
    brief: Brief
    score: Score
    draft: Draft | None


def is_ship_artifact(url: str | None) -> bool:
    return is_ship_artifact_url(url)


def brief_artifacts(brief: Brief) -> tuple[str, ...]:
    found: list[str] = []
    for fact in brief.facts:
        url = fact.artifact_url
        if url and url not in found:
            found.append(url)
    return tuple(found)


def _kill(brief: Brief, reason: str) -> Score:
    return Score(
        brief_id=brief.brief_id,
        verdict=Verdict.KILL,
        reason=reason,
        arena=None,
        angle=None,
        wave_checklist=(),
        canon_url=CANON_URL,
    ).with_hash()


def _changelog(brief: Brief, reason: str) -> Score:
    play = arena_play(ArenaId.GITHUB)
    return Score(
        brief_id=brief.brief_id,
        verdict=Verdict.CHANGELOG_ONLY,
        reason=reason,
        arena=None,
        angle=ANGLES[StoryKind.PATCH],
        wave_checklist=play.wave,
        canon_url=play.canon_url,
    ).with_hash()


def _facts_blob(brief: Brief) -> str:
    parts: list[str] = []
    for fact in brief.facts:
        parts.append(fact.text)
        if fact.kind:
            parts.append(fact.kind)
        if fact.artifact_url:
            parts.append(fact.artifact_url)
    return "\n".join(parts)


def _has_clickable_url(brief: Brief) -> bool:
    """A tryable demo URL. A film, store, blog, or launch board is not click-and-run."""
    for fact in brief.facts:
        url = (fact.artifact_url or "").strip()
        if is_ship_artifact(url):
            return True
        if (
            url.startswith("https://")
            and not is_video_host_url(url)
            and not is_store_host_url(url)
            and not is_blog_host_url(url)
            and not is_launch_host_url(url)
            and not is_ranking_host_url(url)
            and not is_news_host_url(url)
        ):
            return True
    return False


def _film_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is YouTube/Vimeo/Loom and none is a repo."""
    urls = [url.strip() for url in brief_artifacts(brief) if url and url.strip()]
    if not urls:
        return False
    if any(is_ship_artifact(url) for url in urls):
        return False
    return all(is_video_host_url(url) for url in urls)


def _store_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is App Store / Play / TestFlight and none is a repo."""
    urls = [url.strip() for url in brief_artifacts(brief) if url and url.strip()]
    if not urls:
        return False
    if any(is_ship_artifact(url) for url in urls):
        return False
    return all(is_store_host_url(url) for url in urls)


def _blog_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is Medium / Substack / dev.to / hashnode and none is a repo."""
    urls = [url.strip() for url in brief_artifacts(brief) if url and url.strip()]
    if not urls:
        return False
    if any(is_ship_artifact(url) for url in urls):
        return False
    return all(is_blog_host_url(url) for url in urls)


def _launch_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is Product Hunt / BetaList and none is a repo."""
    urls = [url.strip() for url in brief_artifacts(brief) if url and url.strip()]
    if not urls:
        return False
    if any(is_ship_artifact(url) for url in urls):
        return False
    return all(is_launch_host_url(url) for url in urls)


def _ranking_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is HN / star-history / shields and none is a repo."""
    return ranking_urls_only(brief_artifacts(brief))


def _news_only_urls(brief: Brief) -> bool:
    """True when every artifact URL is a newspaper / wire and none is a repo."""
    return news_urls_only(brief_artifacts(brief))


def _enough_social_substance(brief: Brief) -> bool:
    if any(is_ship_artifact(url) for url in brief_artifacts(brief)):
        return True
    meaty = [fact for fact in brief.facts if len(fact.text.strip()) >= MIN_FACT_CHARS]
    return len(meaty) >= MIN_SOCIAL_FACTS


def _wearable_fact_texts(brief: Brief) -> tuple[str, ...]:
    found: list[str] = []
    for fact in brief.facts:
        text = fact.text.strip()
        if not text:
            continue
        if fact.kind.strip().lower() == "artifact" or text.casefold() == "ship artifact":
            continue
        found.append(text)
    return tuple(found)


def _is_merge_log_brief(brief: Brief) -> bool:
    return is_merge_log_texts(_wearable_fact_texts(brief))


def _fact_triples(brief: Brief) -> tuple[tuple[str, str, str | None], ...]:
    return tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)


def _choose_arena(brief: Brief) -> ArenaId:
    """One primary arena. GitHub is the website; HN only when there is a clickable demo."""
    if brief.preferred_arena is not None:
        return brief.preferred_arena
    if (
        brief.tryable
        and brief.story_kind in {StoryKind.MAJOR, StoryKind.HARD_ISSUE}
        and _has_clickable_url(brief)
        and not looks_like_issues_disabled(_facts_blob(brief))
        and not looks_like_fork(_facts_blob(brief))
        and not looks_like_empty_repo(_facts_blob(brief))
        and not looks_like_server_splash(_facts_blob(brief))
    ):
        return ArenaId.HN
    return ArenaId.GITHUB


def _gate_violation(brief: Brief, arena: ArenaId, blob: str) -> tuple[Verdict, str] | None:
    gate: ArenaGate = arena_gate(arena)
    if gate.always_kill:
        return Verdict.KILL, gate.reason
    if gate.allowed_story_kinds is not None and brief.story_kind not in gate.allowed_story_kinds:
        return gate.mismatch_verdict, gate.reason
    if gate.require_tryable and not brief.tryable:
        return Verdict.KILL, gate.reason
    if arena is ArenaId.HN and _film_only_urls(brief):
        return Verdict.KILL, "hn_not_an_episode"
    store_blob = "\n".join(fact.text for fact in brief.facts)
    if arena is ArenaId.HN and (_store_only_urls(brief) or looks_like_store_pitch(store_blob)):
        return Verdict.KILL, "hn_not_a_store"
    if arena is ArenaId.HN and _blog_only_urls(brief):
        return Verdict.KILL, "hn_not_a_blog"
    if arena is ArenaId.HN and (_launch_only_urls(brief) or looks_like_launch_pitch(store_blob)):
        return Verdict.KILL, "hn_not_an_aggregator"
    if arena is ArenaId.HN and _ranking_only_urls(brief):
        return Verdict.KILL, "ranking_not_an_artifact"
    if arena is ArenaId.HN and _news_only_urls(brief):
        return Verdict.KILL, "world_commentary"
    title = next(iter(_wearable_fact_texts(brief)), "")
    if is_social_arena(arena) and looks_like_issues_disabled(blob):
        return Verdict.KILL, "issues_disabled_no_camp"
    if looks_like_fork(blob):
        return Verdict.KILL, "fork_not_a_site"
    if looks_like_empty_repo(blob):
        return Verdict.KILL, "empty_repo_not_a_site"
    if looks_like_server_splash(blob):
        return Verdict.KILL, "server_splash_not_a_product"
    if arena is ArenaId.HN and looks_like_listicle_title(title):
        return Verdict.KILL, "hn_not_a_listicle"
    if arena in {ArenaId.HN, ArenaId.GITHUB} and looks_like_shouty_title(title):
        return Verdict.KILL, "shouty_title"
    if arena in {ArenaId.HN, ArenaId.GITHUB} and looks_like_emoji_title(title):
        return Verdict.KILL, "emoji_title"
    if gate.require_clickable_url and not _has_clickable_url(brief):
        return Verdict.KILL, gate.reason
    if gate.require_ship_artifact and not any(is_ship_artifact(url) for url in brief_artifacts(brief)):
        return Verdict.KILL, gate.reason
    if gate.forbid_ship_claim and brief.claims_ship:
        return Verdict.KILL, gate.reason
    if gate.min_facts and len(brief.facts) < gate.min_facts:
        return Verdict.KILL, gate.reason
    kinds = {fact.kind.strip().lower() for fact in brief.facts}
    if gate.require_subreddit and "subreddit" not in kinds and not has_named_subreddit(blob):
        return Verdict.KILL, gate.reason
    if gate.require_package and "package" not in kinds and not has_cinema_package(blob):
        return Verdict.KILL, gate.reason
    if gate.require_hook and "hook" not in kinds and not has_fair_hook(blob):
        return Verdict.KILL, gate.reason
    return None


def score_brief(brief: Brief) -> Score:
    """Fail-closed speak / silence decision. Borderline briefs do not leak a social draft."""
    if not brief.facts:
        return _kill(brief, "empty_brief")
    blob = _facts_blob(brief)
    unsourced = unquotable_reason(_fact_triples(brief))
    if unsourced:
        return _kill(brief, unsourced)
    if brief.story_kind is StoryKind.PATCH:
        return _changelog(brief, "patch_changelog_only")
    if brief.facts and all(looks_like_commit_noise(fact.text) for fact in brief.facts):
        return _changelog(brief, "commit_noise_changelog")
    if _is_merge_log_brief(brief):
        return _changelog(brief, "merge_log_changelog")
    if brief.claims_ship:
        if not any(is_ship_artifact(url) for url in brief_artifacts(brief)):
            return _kill(brief, "ship_claim_missing_artifact")
        if not brief.tryable:
            return _kill(brief, "hype_without_demo")
    if looks_like_waitlist(blob):
        if brief.claims_ship or is_social_arena(brief.preferred_arena):
            return _kill(brief, "waitlist_not_tryable")
        return _changelog(brief, "waitlist_not_tryable")
    if looks_like_login_gate(blob):
        if brief.claims_ship or is_social_arena(brief.preferred_arena):
            return _kill(brief, "login_gate_not_tryable")
        return _changelog(brief, "login_gate_not_tryable")
    if looks_like_dead_link(blob):
        if brief.claims_ship or is_social_arena(brief.preferred_arena):
            return _kill(brief, "dead_link_not_tryable")
        return _changelog(brief, "dead_link_not_tryable")
    if looks_like_issues_disabled(blob):
        if is_social_arena(brief.preferred_arena):
            return _kill(brief, "issues_disabled_no_camp")
    if looks_like_fork(blob):
        return _kill(brief, "fork_not_a_site")
    if looks_like_empty_repo(blob):
        return _kill(brief, "empty_repo_not_a_site")
    if looks_like_server_splash(blob):
        return _kill(brief, "server_splash_not_a_product")
    if looks_like_dead_release_asset(blob):
        if brief.claims_ship or is_social_arena(brief.preferred_arena):
            return _kill(brief, "dead_release_asset")
        return _changelog(brief, "dead_release_asset")
    if looks_like_roadmap(blob):
        if brief.claims_ship or is_social_arena(brief.preferred_arena):
            return _kill(brief, "roadmap_not_a_ship")
        return _changelog(brief, "roadmap_not_a_ship")
    if looks_like_superlative(blob) and not (
        brief.tryable and any(is_ship_artifact(url) for url in brief_artifacts(brief))
    ):
        return _kill(brief, "superlative_without_proof")
    if looks_like_dunk(blob):
        return _kill(brief, "dunking")
    if looks_like_foreign_wave(_fact_triples(brief)):
        return _kill(brief, "foreign_wave")
    if looks_like_engagement_bait(blob):
        return _kill(brief, "engagement_bait")
    if looks_like_contest(blob):
        return _kill(brief, "contest")
    if looks_like_thread(blob):
        return _kill(brief, "thread")
    if looks_like_ranking_dump(blob):
        return _kill(brief, "ranking_not_an_artifact")
    if looks_like_hashtag_wall(blob):
        return _kill(brief, "hashtag_wall")
    if looks_like_private_conversation(blob):
        return _kill(brief, "private_conversation")
    if looks_like_world_commentary(blob) or _news_only_urls(brief):
        return _kill(brief, "world_commentary")
    if looks_like_hire_fundraise(blob):
        return _kill(brief, "hire_fundraise")
    if looks_like_source_available_as_oss(blob):
        return _kill(brief, "source_available_not_oss")
    if brief.story_kind is StoryKind.EXPLORATION:
        if is_social_arena(brief.preferred_arena):
            return _kill(brief, "exploration_not_a_post")
        return _changelog(brief, "exploration_not_a_post")
    if brief.story_kind is StoryKind.DECISION and not (brief.tryable or brief.claims_ship):
        if is_social_arena(brief.preferred_arena):
            return _kill(brief, "decision_not_user_facing")
        return _changelog(brief, "decision_not_user_facing")

    chosen = _choose_arena(brief)
    blocked = _gate_violation(brief, chosen, blob)
    if blocked is not None:
        verdict, reason = blocked
        if verdict is Verdict.CHANGELOG_ONLY:
            return _changelog(brief, reason)
        return _kill(brief, reason)
    if is_social_arena(chosen):
        if not _enough_social_substance(brief):
            return _changelog(brief, "thin_brief")
        if looks_like_press_release(blob):
            return _kill(brief, "press_release_tone")
    play = arena_play(chosen)
    return Score(
        brief_id=brief.brief_id,
        verdict=Verdict.DRAFT,
        reason="one_angle",
        arena=chosen,
        angle=ANGLES[brief.story_kind],
        wave_checklist=play.wave,
        canon_url=play.canon_url,
    ).with_hash()


def compose_draft(brief: Brief, score: Score, *, now: str | None = None) -> Draft | None:
    """Costume-native body for the single chosen arena. Kill/changelog emit nothing.

    Scoring stays here. Dressing is influenzer.hom_draft — this is a thin call.
    """
    from influenzer.hom_draft import dress_brief

    return dress_brief(brief, score, now=now)


def apply_brief(brief: Brief, *, now: str | None = None) -> OperatorDecision:
    score = score_brief(brief)
    draft = compose_draft(brief, score, now=now)
    return OperatorDecision(brief=brief, score=score, draft=draft)


def decision_to_dict(decision: OperatorDecision) -> dict[str, Any]:
    score = decision.score
    draft = decision.draft
    out: dict[str, Any] = {
        "brief_id": decision.brief.brief_id,
        "project_id": decision.brief.project_id,
        "verdict": score.verdict.value,
        "reason": score.reason,
        "arena": None if score.arena is None else score.arena.value,
        "angle": score.angle,
        "canon_url": score.canon_url,
        "published": False,
        "draft_id": None if draft is None else draft.draft_id,
    }
    if draft is not None:
        out["costume"] = draft.costume
        out["content_hash"] = draft.content_hash
        out["wave_checklist"] = list(draft.wave_checklist)
        out["body"] = draft.body
    else:
        out["wave_checklist"] = list(score.wave_checklist)
    return out


def _reject_secret_keys(data: Mapping[str, Any], *, path: str = "") -> None:
    for key, value in data.items():
        lowered = str(key).lower().replace("-", "_")
        here = f"{path}.{key}" if path else str(key)
        if lowered in _SECRET_KEYS:
            raise HomError(f"brief must not contain secret field: {here}")
        if isinstance(value, Mapping):
            _reject_secret_keys(value, path=here)
        elif isinstance(value, list):
            for idx, item in enumerate(value):
                if isinstance(item, Mapping):
                    _reject_secret_keys(item, path=f"{here}[{idx}]")


def fact_from_mapping(raw: Mapping[str, Any] | str) -> Fact:
    if isinstance(raw, str):
        return Fact(text=raw)
    text = str(raw.get("text") or "").strip()
    kind = str(raw.get("kind") or "signal")
    artifact = raw.get("artifact_url")
    artifact_url = None if artifact in (None, "") else str(artifact)
    return Fact(text=text, kind=kind, artifact_url=artifact_url)


def brief_from_mapping(data: Mapping[str, Any], *, project_id: str | None = None) -> Brief:
    if not isinstance(data, Mapping):
        raise HomError("brief JSON must be an object")
    _reject_secret_keys(data)
    pid = str(data.get("project_id") or project_id or "")
    if not pid:
        raise HomError("project_id is required")
    facts_raw = data.get("facts") or []
    if not isinstance(facts_raw, list):
        raise HomError("facts must be a list")
    facts = tuple(fact_from_mapping(item) for item in facts_raw)
    return Brief.create(
        project_id=pid,
        brief_id=str(data.get("brief_id") or ""),
        facts=facts,
        story_kind=str(data.get("story_kind") or ""),
        claims_ship=bool(data.get("claims_ship", False)),
        tryable=bool(data.get("tryable", False)),
        preferred_arena=data.get("preferred_arena") or data.get("arena"),
        source=str(data.get("source") or "json"),
        created_at=data.get("created_at"),
    )


def brief_to_mapping(brief: Brief) -> dict[str, Any]:
    return {
        "project_id": brief.project_id,
        "brief_id": brief.brief_id,
        "facts": [
            {"kind": f.kind, "text": f.text, "artifact_url": f.artifact_url}
            for f in brief.facts
        ],
        "story_kind": brief.story_kind.value,
        "claims_ship": brief.claims_ship,
        "tryable": brief.tryable,
        "preferred_arena": None if brief.preferred_arena is None else brief.preferred_arena.value,
        "source": brief.source,
        "status": brief.status,
        "created_at": brief.created_at,
    }


def parse_facts_json(blob: str) -> tuple[Fact, ...]:
    data = json.loads(blob)
    if not isinstance(data, list):
        raise HomError("facts_json must be a list")
    return tuple(fact_from_mapping(item) for item in data)


# Every listed arena has a costume and a non-empty wave so tests can lock the copy.
assert all(play.costume and play.wave for play in ARENAS.values())

__all__ = [
    "Brief",
    "Draft",
    "Fact",
    "HomError",
    "OperatorDecision",
    "Score",
    "apply_brief",
    "brief_artifacts",
    "brief_from_mapping",
    "brief_to_mapping",
    "compose_draft",
    "decision_to_dict",
    "fact_from_mapping",
    "is_ship_artifact",
    "parse_facts_json",
    "score_brief",
]
