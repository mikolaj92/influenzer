"""Hermes CLI entry for Influenzer."""

from __future__ import annotations

import argparse
import json
import sys
import re
import webbrowser
from pathlib import Path
from urllib.parse import urlencode, urlparse

from influenzer import __version__
from influenzer.config import Config, load_config, write_config
from influenzer.domain import (
    AccountStatus,
    Campaign,
    CampaignKind,
    CampaignStatus,
    ContentRevision,
    ContentStatus,
    DomainError,
    PLATFORMS,
    PlatformAccount,
    PolicyActivationGrant,
    PolicyVersion,
    Project,
    PlanStatus,
    transition_plan,
    content_hash,
    utc_now,
)
from influenzer.storage import CrossProjectError, StateRepository, StorageError


def setup_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--version", action="store_true", help="print package version")
    parser.add_argument("--config", help="path to config.json")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="create local workspace home")
    init.add_argument("--home", help="workspace directory")

    project = sub.add_parser("project", help="project operations")
    project_sub = project.add_subparsers(dest="project_command")
    create = project_sub.add_parser("create", help="create an app or builder project")
    create.add_argument("--id", required=True)
    create.add_argument("--slug", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--display-name", required=True)
    create.add_argument("--voice", required=True)
    create.add_argument("--audience", required=True)
    create.add_argument("--maintainer", required=True)
    create.add_argument("--kind", choices=("app", "personal", "builder"), default="app")
    create.add_argument("--tone", default="builder")
    show = project_sub.add_parser("show", help="show a project and brand profile")
    show.add_argument("--id", required=True)

    content = sub.add_parser("content", help="content operations")
    content_sub = content.add_subparsers(dest="content_command")
    add = content_sub.add_parser("add", help="create an immutable content revision")
    add.add_argument("--project-id", required=True)
    add.add_argument("--content-id", required=True)
    add.add_argument("--revision-id", required=True)
    add.add_argument("--body", required=True)
    add.add_argument("--kind", default="post")
    add.add_argument("--source", default="manual")
    add.add_argument("--status", choices=[s.value for s in ContentStatus], default=ContentStatus.DRAFT.value)

    campaign = sub.add_parser("campaign", help="campaign planning (no spend)")
    campaign_sub = campaign.add_subparsers(dest="campaign_command")
    ccreate = campaign_sub.add_parser("create", help="create organic or paid plan-only campaign")
    ccreate.add_argument("--project-id", required=True)
    ccreate.add_argument("--campaign-id", required=True)
    ccreate.add_argument("--name", required=True)
    ccreate.add_argument("--kind", choices=("organic", "paid"), default="organic")
    ccreate.add_argument("--budget-amount", type=float)
    ccreate.add_argument("--budget-currency")
    ccreate.add_argument("--disclosure", action="append", default=[])

    account = sub.add_parser("account", help="register platform accounts (credential refs only)")
    account_sub = account.add_subparsers(dest="account_command")
    aadd = account_sub.add_parser("add", help="add an existing platform account to a project")
    aadd.add_argument("--project-id", required=True)
    aadd.add_argument("--account-id", required=True)
    aadd.add_argument("--platform", required=True, choices=sorted(PLATFORMS))
    aadd.add_argument("--handle", required=True)
    aadd.add_argument("--host", help="required for mastodon instance host")
    aadd.add_argument(
        "--credential-ref",
        required=True,
        help="env:NAME or keychain:SERVICE/ACCOUNT — never a raw token",
    )
    aadd.add_argument(
        "--status",
        choices=[s.value for s in AccountStatus],
        default=AccountStatus.DISCONNECTED.value,
        help="use connected only when the credential_ref resolves",
    )
    aadd.add_argument("--capability", action="append", default=None, help="optional capability tag")
    alist = account_sub.add_parser("list", help="list accounts (never prints secrets)")
    alist.add_argument("--project-id")

    policy = sub.add_parser("policy", help="versioned autopublish policy")
    policy_sub = policy.add_subparsers(dest="policy_command")
    pcreate = policy_sub.add_parser("create", help="create an immutable policy version")
    pcreate.add_argument("--project-id", required=True)
    pcreate.add_argument("--policy-version-id", required=True)
    pcreate.add_argument("--action", action="append", default=None)
    pcreate.add_argument("--content-kind", action="append", default=None)
    pcreate.add_argument("--account-id", action="append", default=None, help="empty = all project accounts")
    pcreate.add_argument("--max-posts-per-day", type=int, default=5)
    pcreate.add_argument("--require-disclosures", action="store_true")

    grant = sub.add_parser("grant", help="hash-bound policy activation grants")
    grant_sub = grant.add_subparsers(dest="grant_command")
    gact = grant_sub.add_parser("activate", help="activate a grant for an account/action")
    gact.add_argument("--project-id", required=True)
    gact.add_argument("--grant-id", required=True)
    gact.add_argument("--policy-version-id", required=True)
    gact.add_argument("--account-id", help="optional account binding")
    gact.add_argument("--action", action="append", default=None)
    gact.add_argument("--actor", required=True)
    gact.add_argument("--expires-at", help="optional ISO-8601 expiry")

    publish = sub.add_parser("publish", help="safe publishing handoffs")
    publish_sub = publish.add_subparsers(dest="publish_command")
    handoff = publish_sub.add_parser("handoff", help="open an approved X plan for manual posting")
    handoff.add_argument("--project-id", required=True)
    handoff.add_argument("--plan-id", required=True)
    confirm = publish_sub.add_parser("confirm", help="confirm a manually published X status URL")
    confirm.add_argument("--project-id", required=True)
    confirm.add_argument("--plan-id", required=True)
    confirm.add_argument("--url", required=True)


def _repo(args: argparse.Namespace) -> StateRepository:
    cfg = load_config(args.config)
    cfg.home.mkdir(parents=True, exist_ok=True)
    (cfg.home / "artifacts" / "sha256").mkdir(parents=True, exist_ok=True)
    return StateRepository(cfg.state_db, artifact_root=cfg.home / "artifacts")


def _fail(reason: str, code: int = 1) -> int:
    print(json.dumps({"status": "failed", "reason": reason}, sort_keys=True), file=sys.stderr)
    return code


def handle_cli(args: argparse.Namespace) -> int:
    if getattr(args, "version", False):
        print(__version__)
        return 0

    if args.command == "init":
        cfg = load_config(args.config)
        home = Path(args.home) if getattr(args, "home", None) else cfg.home
        config_file = Path(args.config) if args.config else home / "config.json"
        write_config(config_file, Config(home=home))
        home.mkdir(parents=True, exist_ok=True)
        (home / "artifacts" / "sha256").mkdir(parents=True, exist_ok=True)
        # Open once so schema migrates.
        with StateRepository(home / "state.db", artifact_root=home / "artifacts"):
            pass
        print(json.dumps({"status": "ok", "home": str(home)}, sort_keys=True))
        return 0

    if args.command == "project" and args.project_command == "create":
        project = Project.create(
            project_id=args.id,
            slug=args.slug,
            name=args.name,
            display_name=args.display_name,
            voice=args.voice,
            audience=args.audience,
            maintainer=args.maintainer,
            kind=args.kind,
            tone=args.tone,
        )
        with _repo(args) as repo:
            repo.save_project(project)
            stored = repo.get_project(project.project_id)
        assert stored is not None
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": stored.project_id,
                    "slug": stored.slug,
                    "kind": stored.kind,
                    "brand_hash": stored.brand.profile_hash,
                    "persisted": True,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "project" and args.project_command == "show":
        with _repo(args) as repo:
            stored = repo.get_project(args.id)
        if stored is None:
            print(json.dumps({"status": "failed", "reason": "project not found"}, sort_keys=True), file=sys.stderr)
            return 1
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": stored.project_id,
                    "slug": stored.slug,
                    "kind": stored.kind,
                    "brand": {
                        "display_name": stored.brand.display_name,
                        "voice": stored.brand.voice,
                        "audience": stored.brand.audience,
                        "profile_hash": stored.brand.profile_hash,
                    },
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "content" and args.content_command == "add":
        source_digest = content_hash({"source": args.source, "body": args.body})
        revision = ContentRevision(
            project_id=args.project_id,
            content_id=args.content_id,
            revision_id=args.revision_id,
            body=args.body,
            kind=args.kind,
            status=ContentStatus(args.status),
            source=args.source,
            source_digest=source_digest,
            created_at=utc_now(),
        ).with_hash()
        with _repo(args) as repo:
            if repo.get_project(args.project_id) is None:
                print(json.dumps({"status": "failed", "reason": "project not found"}, sort_keys=True), file=sys.stderr)
                return 1
            repo.save_content_revision(revision)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": revision.project_id,
                    "content_id": revision.content_id,
                    "revision_id": revision.revision_id,
                    "content_hash": revision.content_hash,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "campaign" and args.campaign_command == "create":
        campaign = Campaign(
            project_id=args.project_id,
            campaign_id=args.campaign_id,
            kind=CampaignKind(args.kind),
            name=args.name,
            status=CampaignStatus.DRAFT,
            budget_amount=args.budget_amount,
            budget_currency=args.budget_currency,
            disclosures=tuple(args.disclosure or ()),
        )
        try:
            campaign.validate()
        except ValueError as exc:
            print(json.dumps({"status": "failed", "reason": str(exc)}, sort_keys=True), file=sys.stderr)
            return 1
        with _repo(args) as repo:
            if repo.get_project(args.project_id) is None:
                print(json.dumps({"status": "failed", "reason": "project not found"}, sort_keys=True), file=sys.stderr)
                return 1
            repo.save_campaign(campaign)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": campaign.project_id,
                    "campaign_id": campaign.campaign_id,
                    "kind": campaign.kind.value,
                    "spend_path": False,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "account" and args.account_command == "add":
        if args.platform == "mastodon" and not args.host:
            return _fail("mastodon requires --host (instance hostname, no scheme)")
        if args.credential_ref.startswith(("http://", "https://", "/")) or " " in args.credential_ref:
            return _fail("credential_ref must be env:NAME or keychain:SERVICE/ACCOUNT")
        try:
            account = PlatformAccount(
                project_id=args.project_id,
                account_id=args.account_id,
                platform=args.platform,
                handle=args.handle,
                host=args.host,
                credential_ref=args.credential_ref,
                status=AccountStatus(args.status),
                capabilities=tuple(args.capability or ()),
            )
        except DomainError as exc:
            return _fail(str(exc))
        with _repo(args) as repo:
            if repo.get_project(args.project_id) is None:
                return _fail("project not found")
            try:
                repo.save_account(account)
            except StorageError as exc:
                return _fail(str(exc))
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": account.project_id,
                    "account_id": account.account_id,
                    "platform": account.platform,
                    "handle": account.handle,
                    "host": account.host,
                    "credential_ref": account.credential_ref,
                    "account_status": account.status.value,
                    "secret_stored": False,
                    "live_ready": False,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "account" and args.account_command == "list":
        with _repo(args) as repo:
            accounts = repo.list_accounts(args.project_id)
        print(
            json.dumps(
                {
                    "status": "ok",
                    "accounts": [
                        {
                            "project_id": a.project_id,
                            "account_id": a.account_id,
                            "platform": a.platform,
                            "handle": a.handle,
                            "host": a.host,
                            "credential_ref": a.credential_ref,
                            "account_status": a.status.value,
                        }
                        for a in accounts
                    ],
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "policy" and args.policy_command == "create":
        policy = PolicyVersion(
            project_id=args.project_id,
            policy_version_id=args.policy_version_id,
            account_ids=tuple(args.account_id or ()),
            actions=tuple(args.action or ("publish",)),
            content_kinds=tuple(args.content_kind or ("post",)),
            max_posts_per_day=args.max_posts_per_day,
            require_disclosures=bool(args.require_disclosures),
        ).with_hash()
        with _repo(args) as repo:
            if repo.get_project(args.project_id) is None:
                return _fail("project not found")
            # Fail closed via repository: every account_id must belong to this project.
            for account_id in policy.account_ids:
                if repo.get_account(policy.project_id, account_id) is None:
                    # Distinguish missing vs foreign via list scan for clearer CLI errors.
                    foreign = any(a.account_id == account_id for a in repo.list_accounts())
                    if foreign:
                        return _fail("policy account belongs to another project")
                    return _fail(f"unknown policy account: {account_id}")
            try:
                repo.save_policy(policy)
            except CrossProjectError as exc:
                return _fail(str(exc))
            except StorageError as exc:
                return _fail(str(exc))
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": policy.project_id,
                    "policy_version_id": policy.policy_version_id,
                    "policy_hash": policy.policy_hash,
                    "max_posts_per_day": policy.max_posts_per_day,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "grant" and args.grant_command == "activate":
        with _repo(args) as repo:
            if repo.get_project(args.project_id) is None:
                return _fail("project not found")
            policy = repo.get_policy(args.project_id, args.policy_version_id)
            if policy is None:
                return _fail("policy version not found")
            if args.account_id is not None:
                if repo.get_account(args.project_id, args.account_id) is None:
                    foreign = any(a.account_id == args.account_id for a in repo.list_accounts())
                    if foreign:
                        return _fail("grant account belongs to another project")
                    return _fail("account not found")
            grant = PolicyActivationGrant(
                project_id=args.project_id,
                grant_id=args.grant_id,
                policy_version_id=policy.policy_version_id,
                policy_hash=policy.policy_hash,
                platform_account_id=args.account_id,
                actions=tuple(args.action or ("publish",)),
                actor=args.actor,
                created_at=utc_now(),
                expires_at=args.expires_at,
            )
            try:
                repo.save_grant(grant)
            except CrossProjectError as exc:
                return _fail(str(exc))
            except StorageError as exc:
                return _fail(str(exc))
        print(
            json.dumps(
                {
                    "status": "ok",
                    "project_id": grant.project_id,
                    "grant_id": grant.grant_id,
                    "policy_version_id": grant.policy_version_id,
                    "policy_hash": grant.policy_hash,
                    "account_id": grant.platform_account_id,
                    "actions": list(grant.actions),
                    "live_enabled_still_required": True,
                },
                sort_keys=True,
            )
        )
        return 0

    if args.command == "publish" and args.publish_command in {"handoff", "confirm"}:
        with _repo(args) as repo:
            plan = repo.get_plan(args.project_id, args.plan_id)
            if plan is None:
                return _fail("plan not found")
            if plan.platform != "x":
                return _fail("manual handoff currently supports X plans only")

            if args.publish_command == "handoff":
                intent_url = "https://twitter.com/intent/tweet?" + urlencode({"text": plan.body})
                if plan.status is PlanStatus.APPROVED:
                    ready = transition_plan(plan, PlanStatus.HANDOFF_READY)
                    try:
                        repo.update_plan_status_with_receipt(
                            ready,
                            expected_status=PlanStatus.APPROVED,
                            receipt_id=f"handoff-ready:{plan.plan_id}",
                            receipt_status="handoff_ready",
                            receipt_payload={"intent_url": intent_url, "published": False},
                            created_at=utc_now(),
                            event_type="plan.handoff_ready",
                        )
                    except StorageError as exc:
                        return _fail(str(exc))
                    plan = ready
                elif plan.status is not PlanStatus.HANDOFF_READY:
                    return _fail("handoff requires an approved or handoff-ready plan")
                if not webbrowser.open(intent_url, new=2):
                    return _fail("could not open X handoff; retry is safe")
                opened = transition_plan(plan, PlanStatus.HANDOFF_OPENED)
                try:
                    repo.update_plan_status_with_receipt(
                        opened,
                        expected_status=PlanStatus.HANDOFF_READY,
                        receipt_id=f"handoff-opened:{plan.plan_id}",
                        receipt_status="handoff_opened",
                        receipt_payload={"intent_url": intent_url, "published": False},
                        created_at=utc_now(),
                        event_type="plan.handoff_opened",
                    )
                except StorageError as exc:
                    return _fail(f"handoff opened but audit finalization failed; confirm the status URL or retry: {exc}")
                print(json.dumps({"status": "ok", "plan_id": plan.plan_id, "plan_status": opened.status.value, "intent_url": intent_url, "published": False}, sort_keys=True))
                return 0

            parsed = urlparse(args.url)
            match = re.fullmatch(r"/[^/]+/status/(\d+)", parsed.path.rstrip("/"))
            if parsed.scheme != "https" or parsed.hostname not in {"x.com", "www.x.com", "twitter.com", "www.twitter.com"} or match is None:
                return _fail("confirmation URL must be an HTTPS X status URL")
            if plan.status not in {PlanStatus.HANDOFF_READY, PlanStatus.HANDOFF_OPENED}:
                return _fail("confirmation requires a prepared handoff")
            updated = transition_plan(plan, PlanStatus.PUBLISHED_CONFIRMED)
            try:
                repo.update_plan_status_with_receipt(
                    updated,
                    expected_status=plan.status,
                    receipt_id=f"confirmation:{plan.plan_id}",
                    receipt_status="published_confirmed",
                    receipt_payload={"provider_id": match.group(1), "provider_url": args.url},
                    created_at=utc_now(),
                    event_type="plan.publication_confirmed",
                )
            except StorageError as exc:
                return _fail(str(exc))
            print(json.dumps({"status": "ok", "plan_id": plan.plan_id, "plan_status": updated.status.value, "provider_id": match.group(1), "provider_url": args.url}, sort_keys=True))
            return 0

    print(
        "usage: influenzer [--version] {init,project,content,campaign,account,policy,grant,publish}",
        file=sys.stderr,
    )
    return 2


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="influenzer")
    setup_parser(parser)
    args = parser.parse_args(argv)
    return handle_cli(args)


if __name__ == "__main__":
    raise SystemExit(main())
