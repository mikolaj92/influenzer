from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from influenzer.cli import main
from influenzer.domain import AccountStatus, PlatformAccount, PolicyActivationGrant, PolicyVersion, Project
from influenzer.storage import CrossProjectError, StateRepository, StorageError


class AccountPolicyGrantCLITests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "ws"
        self.config = self.home / "config.json"
        self.assertEqual(main(["--config", str(self.config), "init", "--home", str(self.home)]), 0)
        for project_id, slug, name in (
            ("app-1", "app", "App"),
            ("app-2", "other", "Other"),
        ):
            self.assertEqual(
                main(
                    [
                        "--config",
                        str(self.config),
                        "project",
                        "create",
                        "--id",
                        project_id,
                        "--slug",
                        slug,
                        "--name",
                        name,
                        "--display-name",
                        name,
                        "--voice",
                        "v",
                        "--audience",
                        "a",
                        "--maintainer",
                        "m",
                        "--kind",
                        "app",
                    ]
                ),
                0,
            )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_account_add_list_and_grant_flow(self) -> None:
        code = main(
            [
                "--config",
                str(self.config),
                "account",
                "add",
                "--project-id",
                "app-1",
                "--account-id",
                "masto-1",
                "--platform",
                "mastodon",
                "--handle",
                "@me",
                "--host",
                "mastodon.social",
                "--credential-ref",
                "env:MASTODON_TOKEN",
                "--status",
                "connected",
            ]
        )
        self.assertEqual(code, 0)
        with StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts") as repo:
            accounts = repo.list_accounts("app-1")
            self.assertEqual(len(accounts), 1)
            self.assertEqual(accounts[0].credential_ref, "env:MASTODON_TOKEN")
            self.assertEqual(accounts[0].host, "mastodon.social")
            self.assertIsNotNone(repo.get_account("app-1", "masto-1"))
            self.assertIsNone(repo.get_account("app-2", "masto-1"))

        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "policy",
                    "create",
                    "--project-id",
                    "app-1",
                    "--policy-version-id",
                    "pol-1",
                    "--account-id",
                    "masto-1",
                    "--max-posts-per-day",
                    "3",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "grant",
                    "activate",
                    "--project-id",
                    "app-1",
                    "--grant-id",
                    "g-1",
                    "--policy-version-id",
                    "pol-1",
                    "--account-id",
                    "masto-1",
                    "--actor",
                    "tester",
                ]
            ),
            0,
        )
        self.assertEqual(main(["--config", str(self.config), "account", "list", "--project-id", "app-1"]), 0)

    def test_mastodon_requires_host_and_rejects_raw_secret_ref(self) -> None:
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "account",
                    "add",
                    "--project-id",
                    "app-1",
                    "--account-id",
                    "m1",
                    "--platform",
                    "mastodon",
                    "--handle",
                    "@x",
                    "--credential-ref",
                    "env:T",
                ]
            ),
            1,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "account",
                    "add",
                    "--project-id",
                    "app-1",
                    "--account-id",
                    "x1",
                    "--platform",
                    "x",
                    "--handle",
                    "@x",
                    "--credential-ref",
                    "/tmp/token.txt",
                ]
            ),
            1,
        )

    def test_policy_and_grant_reject_foreign_project_account(self) -> None:
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "account",
                    "add",
                    "--project-id",
                    "app-2",
                    "--account-id",
                    "foreign-acct",
                    "--platform",
                    "bluesky",
                    "--handle",
                    "other.bsky.social",
                    "--credential-ref",
                    "env:BSKY_APP_PASSWORD",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "policy",
                    "create",
                    "--project-id",
                    "app-1",
                    "--policy-version-id",
                    "pol-x",
                    "--account-id",
                    "foreign-acct",
                ]
            ),
            1,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "account",
                    "add",
                    "--project-id",
                    "app-1",
                    "--account-id",
                    "local-acct",
                    "--platform",
                    "bluesky",
                    "--handle",
                    "me.bsky.social",
                    "--credential-ref",
                    "env:LOCAL_BSKY",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "policy",
                    "create",
                    "--project-id",
                    "app-1",
                    "--policy-version-id",
                    "pol-local",
                    "--account-id",
                    "local-acct",
                ]
            ),
            0,
        )
        self.assertEqual(
            main(
                [
                    "--config",
                    str(self.config),
                    "grant",
                    "activate",
                    "--project-id",
                    "app-1",
                    "--grant-id",
                    "g-foreign",
                    "--policy-version-id",
                    "pol-local",
                    "--account-id",
                    "foreign-acct",
                    "--actor",
                    "tester",
                ]
            ),
            1,
        )


class AccountPolicyGrantRepoIsolationTests(unittest.TestCase):
    def test_save_policy_and_grant_reject_cross_project_accounts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, StateRepository(Path(tmp) / "state.db") as repo:
            for pid, slug in (("p1", "one"), ("p2", "two")):
                repo.save_project(
                    Project.create(
                        project_id=pid,
                        slug=slug,
                        name=slug,
                        display_name=slug,
                        voice="v",
                        audience="a",
                        maintainer="m",
                        kind="app",
                    )
                )
            repo.save_account(
                PlatformAccount(
                    "p2",
                    "acct-p2",
                    "x",
                    "@other",
                    None,
                    "env:X_TOKEN",
                    AccountStatus.CONNECTED,
                )
            )
            foreign_policy = PolicyVersion(
                project_id="p1",
                policy_version_id="pol-1",
                account_ids=("acct-p2",),
                actions=("publish",),
                content_kinds=("post",),
                max_posts_per_day=1,
                require_disclosures=False,
            ).with_hash()
            with self.assertRaises(CrossProjectError):
                repo.save_policy(foreign_policy)

            repo.save_account(
                PlatformAccount(
                    "p1",
                    "acct-p1",
                    "x",
                    "@me",
                    None,
                    "env:X_LOCAL",
                    AccountStatus.CONNECTED,
                )
            )
            local_policy = PolicyVersion(
                project_id="p1",
                policy_version_id="pol-local",
                account_ids=("acct-p1",),
                actions=("publish",),
                content_kinds=("post",),
                max_posts_per_day=2,
                require_disclosures=False,
            ).with_hash()
            repo.save_policy(local_policy)

            with self.assertRaises(CrossProjectError):
                repo.save_grant(
                    PolicyActivationGrant(
                        project_id="p1",
                        grant_id="g1",
                        policy_version_id="pol-local",
                        policy_hash=local_policy.policy_hash,
                        platform_account_id="acct-p2",
                        actions=("publish",),
                        actor="tester",
                        created_at="2026-01-01T00:00:00Z",
                        expires_at=None,
                    )
                )
            with self.assertRaises(StorageError):
                repo.save_grant(
                    PolicyActivationGrant(
                        project_id="p1",
                        grant_id="g2",
                        policy_version_id="pol-local",
                        policy_hash=local_policy.policy_hash,
                        platform_account_id="acct-missing",
                        actions=("publish",),
                        actor="tester",
                        created_at="2026-01-01T00:00:00Z",
                        expires_at=None,
                    )
                )
            with self.assertRaises(StorageError):
                repo.save_grant(
                    PolicyActivationGrant(
                        project_id="p1",
                        grant_id="g3",
                        policy_version_id="pol-local",
                        policy_hash=local_policy.policy_hash,
                        platform_account_id="acct-p1",
                        actions=("delete",),
                        actor="tester",
                        created_at="2026-01-01T00:00:00Z",
                        expires_at=None,
                    )
                )


if __name__ == "__main__":
    unittest.main()
