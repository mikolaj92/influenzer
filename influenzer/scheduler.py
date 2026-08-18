"""Single scheduled mutator: due plans, policy gate, adapter dispatch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Sequence

from influenzer.adapters.base import AdapterRequest, AdapterResult, run_adapter
from influenzer.adapters.registry import get_adapter
from influenzer.config import Config
from influenzer.content import create_revision
from influenzer.domain import (
    AttemptStatus,
    ContentStatus,
    PlanStatus,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    PublicationAttempt,
    PublishPlan,
    transition_attempt,
    transition_plan,
    utc_now,
)
from influenzer.envelope import noop, planned, result
from influenzer.hom import (
    apply_brief,
    decision_to_dict,
    drop_repeat_angle,
    drop_repeat_release,
)
from influenzer.playbook import CANON_URL
from influenzer.policy import evaluate_policy
from influenzer.storage import StateRepository

Handler = Callable[[AdapterRequest], AdapterResult]


@dataclass(frozen=True)
class DueWork:
    plan: PublishPlan
    account: PlatformAccount
    policy: PolicyVersion
    grant: PolicyActivationGrant | None


def resolve_live_intent(*, scheduler: bool, cli_live: bool, config: Config) -> bool:
    """Tick-all ignores CLI --live; only durable scheduler.live_enabled authorizes."""
    if scheduler:
        return bool(config.scheduler_live_enabled)
    return bool(cli_live)


def run_operator_tick(repo: StateRepository, *, now: str) -> dict[str, Any]:
    """Ingested briefs → score → draft or explicit kill. Never publishes."""
    outcomes: list[dict[str, Any]] = []
    for brief in repo.list_pending_briefs():
        # Exclude the pending brief itself: only an earlier admitted story can
        # silence this release. History is machine-wide, like the story lock.
        decision = drop_repeat_release(
            drop_repeat_angle(
                apply_brief(
                    brief,
                    now=now,
                    stack_arena=repo.living_stack_arena(brief.project_id, now),
                ),
                repo.last_angle_body_hash(brief.project_id),
            ),
            repo.release_story_keys(exclude=(brief.project_id, brief.brief_id)),
        )
        revision = None
        if decision.draft is not None:
            revision = create_revision(
                project_id=brief.project_id,
                content_id=f"brief-{brief.brief_id}",
                revision_id=decision.draft.draft_id,
                body=decision.draft.body,
                kind="post",
                source="operator",
                status=ContentStatus.DRAFT,
                created_at=now,
            )
        repo.persist_operator_decision(
            brief,
            decision.score,
            decision.draft,
            revision=revision,
            now=now,
        )
        outcomes.append(decision_to_dict(decision))
    return {
        "processed": len(outcomes),
        "outcomes": outcomes,
        "published": False,
        "canon_url": CANON_URL,
    }


def tick(
    repo: StateRepository,
    config: Config,
    *,
    due: Sequence[DueWork] = (),
    cli_live: bool = False,
    posts_today: int = 0,
    now: str | None = None,
    handlers: dict[str, Handler] | None = None,
    score_only: bool = False,
) -> dict[str, Any]:
    """Process pending briefs, then due plans. Live mutation requires durable scheduler.live_enabled + grant.

    Look/pass/angle call this with ``score_only=True``: no adapters, even when
    ``scheduler.live_enabled`` and due plans exist. Live is a separate
    grant+intent path, not a Monday look side effect.
    """
    clock = now or utc_now()
    if score_only:
        live = False
        due = ()
    else:
        live = resolve_live_intent(scheduler=True, cli_live=cli_live, config=config)
    operator = run_operator_tick(repo, now=clock)
    if not due:
        extra = {
            "scheduler_live_enabled": config.scheduler_live_enabled,
            "cli_live_ignored": bool(cli_live),
            "processed": 0,
            "operator": operator,
        }
        if operator["processed"]:
            return result(status="ok", ok=True, mutated=False, **extra)
        return noop("no due work", **extra)

    processed = 0
    outcomes: list[dict[str, Any]] = []
    for item in due:
        plan = item.plan

        if not live:
            # Dry-run never claims plans or dispatches handlers. CLI --live is ignored.
            outcomes.append(
                planned(
                    plan_id=plan.plan_id,
                    platform=plan.platform,
                    operation_key=plan.operation_key,
                    reason="dry-run scheduler tick",
                )
            )
            processed += 1
            continue

        decision = evaluate_policy(
            item.policy,
            item.grant,
            project_id=plan.project_id,
            account_id=plan.platform_account_id,
            content_hash=plan.content_hash,
            content_kind="post",
            body=plan.body,
            action="publish",
            live_intent=True,
            scheduler=True,
            scheduler_live_enabled=config.scheduler_live_enabled,
            posts_today=posts_today,
            now=clock,
            account=item.account,
        )
        if not decision.allowed:
            outcomes.append(
                {
                    "plan_id": plan.plan_id,
                    "status": "denied",
                    "reason": decision.reason,
                    "mutated": False,
                }
            )
            processed += 1
            continue


        # Atomically claim plan + reserve PENDING attempt before any external call.
        executing = transition_plan(plan, PlanStatus.EXECUTING)
        attempt = PublicationAttempt(
            project_id=plan.project_id,
            attempt_id=f"att-{plan.plan_id}-{clock}",
            plan_id=plan.plan_id,
            operation_key=plan.operation_key,
            status=AttemptStatus.PENDING,
            created_at=clock,
        )
        repo.reserve_attempt(executing, attempt, expected_plan_status=PlanStatus.SCHEDULED)
        running = transition_attempt(attempt, AttemptStatus.RUNNING)
        repo.update_attempt_status(running, expected_status=AttemptStatus.PENDING)
        handler = (handlers or {}).get(plan.platform) or get_adapter(plan.platform)
        adapter_result: AdapterResult = run_adapter(
            handler,
            AdapterRequest(
                platform=plan.platform,
                project_id=plan.project_id,
                account_id=plan.platform_account_id,
                body=plan.body,
                operation_key=plan.operation_key,
                dry_run=False,
                host=item.account.host,
                credential_ref=item.account.credential_ref,
            ),
        )
        if adapter_result.get("ok") and adapter_result.get("mutated"):
            done = transition_attempt(
                running,
                AttemptStatus.SUCCEEDED,
                provider_id=adapter_result.get("provider_id"),
                provider_url=adapter_result.get("provider_url"),
            )
            repo.update_attempt_status(done, expected_status=AttemptStatus.RUNNING)
            repo.update_plan_status(
                transition_plan(executing, PlanStatus.SUCCEEDED),
                expected_status=PlanStatus.EXECUTING,
            )
        elif adapter_result.get("status") == "unknown":
            repo.update_attempt_status(
                transition_attempt(running, AttemptStatus.UNKNOWN),
                expected_status=AttemptStatus.RUNNING,
            )
            repo.update_plan_status(
                transition_plan(executing, PlanStatus.UNKNOWN),
                expected_status=PlanStatus.EXECUTING,
            )
        else:
            repo.update_attempt_status(
                transition_attempt(
                    running,
                    AttemptStatus.FAILED,
                    failure_class=str(adapter_result.get("failure_class") or "terminal"),
                    reason=str(adapter_result.get("reason") or "adapter failed"),
                ),
                expected_status=AttemptStatus.RUNNING,
            )
            repo.update_plan_status(
                transition_plan(executing, PlanStatus.FAILED),
                expected_status=PlanStatus.EXECUTING,
            )
        outcomes.append({"plan_id": plan.plan_id, "adapter": adapter_result})
        processed += 1

    return result(
        status="ok",
        ok=True,
        mutated=any(o.get("adapter", {}).get("mutated") for o in outcomes if isinstance(o, dict)),
        scheduler_live_enabled=config.scheduler_live_enabled,
        cli_live_ignored=bool(cli_live),
        processed=processed,
        outcomes=outcomes,
        operator=operator,
    )
