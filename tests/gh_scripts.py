"""Deterministic gh stand-in and survey scripts. Never talks to the network."""

from __future__ import annotations

import base64
import json
from typing import Sequence

from github_survey import GhCall, classify_gh_argv

NOW = "2026-08-13T06:00:00Z"
REPO = "mikolaj92/demo"
SHIP_PR = "https://github.com/mikolaj92/demo/pull/12"
SHIP_RELEASE = "https://github.com/mikolaj92/demo/releases/tag/v0.1.0"
ISSUE_COMMENT = "https://github.com/mikolaj92/demo/issues/7#issuecomment-101"
ISSUE_COMMENT_BUG = "https://github.com/mikolaj92/demo/issues/8#issuecomment-102"
PR_COMMENT = "https://github.com/mikolaj92/demo/pull/12#discussion_r202"


class ScriptedGh:
    def __init__(self, script: dict[str, GhCall]):
        self.script = script
        self.calls: list[tuple[str, ...]] = []

    def __call__(self, argv: Sequence[str]) -> GhCall:
        self.calls.append(tuple(argv))
        key = classify_gh_argv(argv)
        if key not in self.script:
            raise AssertionError(f"unexpected gh argv {list(argv)!r} classified as {key!r}")
        return self.script[key]


def b64_readme(text: str) -> str:
    return json.dumps(
        {
            "encoding": "base64",
            "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
            "html_url": f"https://github.com/{REPO}/blob/main/README.md",
        }
    )


def repo_json(*, private: bool = False, description: str = "Local operator with a working install") -> str:
    return json.dumps(
        {
            "nameWithOwner": REPO,
            "isPrivate": private,
            "url": f"https://github.com/{REPO}",
            "description": description,
            "homepageUrl": "",
        }
    )


def ship_script(**overrides: GhCall) -> dict[str, GhCall]:
    script = {
        "repo": GhCall(0, repo_json()),
        "prs": GhCall(
            0,
            json.dumps(
                [
                    {
                        "number": 12,
                        "title": "feat: local HoM operator scores briefs",
                        "url": SHIP_PR,
                        "mergedAt": "2026-08-12T12:00:00Z",
                        "body": "Stranger can clone and run.",
                    }
                ]
            ),
        ),
        "releases": GhCall(
            0,
            json.dumps(
                [
                    {
                        "tagName": "v0.1.0",
                        "name": "v0.1.0",
                        "isDraft": False,
                        "isPrerelease": False,
                        "publishedAt": "2026-08-12T18:00:00Z",
                    }
                ]
            ),
        ),
        "tags": GhCall(0, json.dumps([{"name": "v0.1.0"}])),
        "readme": GhCall(0, b64_readme("# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n")),
    }
    script.update(overrides)
    return script


def noise_script() -> dict[str, GhCall]:
    return {
        "repo": GhCall(0, repo_json()),
        "prs": GhCall(
            0,
            json.dumps(
                [
                    {
                        "number": 3,
                        "title": "chore: bump deps",
                        "url": "https://github.com/mikolaj92/demo/pull/3",
                        "mergedAt": "2026-08-12T12:00:00Z",
                        "body": "",
                    },
                    {
                        "number": 4,
                        "title": "typo in README",
                        "url": "https://github.com/mikolaj92/demo/pull/4",
                        "mergedAt": "2026-08-12T13:00:00Z",
                        "body": "",
                    },
                    {
                        "number": 5,
                        "title": "fix tests",
                        "url": "https://github.com/mikolaj92/demo/pull/5",
                        "mergedAt": "2026-08-12T14:00:00Z",
                        "body": "",
                    },
                ]
            ),
        ),
        "releases": GhCall(0, "[]"),
        "tags": GhCall(0, "[]"),
        "readme": GhCall(0, b64_readme("# Demo\nWIP\n")),
    }


def gh_comment(
    *,
    html_url: str,
    body: str,
    login: str = "alice",
    user_type: str = "User",
    created_at: str = "2026-08-12T12:00:00Z",
    comment_id: int = 101,
) -> dict:
    return {
        "id": comment_id,
        "html_url": html_url,
        "body": body,
        "user": {"login": login, "type": user_type},
        "created_at": created_at,
    }


def feedback_question_script(**overrides: GhCall) -> dict[str, GhCall]:
    script = {
        "repo": GhCall(0, repo_json()),
        "issue_comments": GhCall(
            0,
            json.dumps(
                [
                    gh_comment(
                        html_url=ISSUE_COMMENT,
                        body="How do I install this when uv is missing?",
                        comment_id=101,
                    ),
                    gh_comment(
                        html_url=ISSUE_COMMENT_BUG,
                        body="The Windows install fails with a traceback",
                        login="bob",
                        comment_id=102,
                        created_at="2026-08-12T13:00:00Z",
                    ),
                ]
            ),
        ),
        "pull_comments": GhCall(
            0,
            json.dumps(
                [
                    gh_comment(
                        html_url=PR_COMMENT,
                        body="Does this break the tick on Python 3.12?",
                        login="cara",
                        comment_id=202,
                        created_at="2026-08-12T14:00:00Z",
                    )
                ]
            ),
        ),
    }
    script.update(overrides)
    return script


def feedback_noise_script() -> dict[str, GhCall]:
    return {
        "repo": GhCall(0, repo_json()),
        "issue_comments": GhCall(
            0,
            json.dumps(
                [
                    gh_comment(
                        html_url="https://github.com/mikolaj92/demo/issues/1#issuecomment-1",
                        body="LGTM",
                        login="dependabot[bot]",
                        user_type="Bot",
                        comment_id=1,
                    ),
                    gh_comment(
                        html_url="https://github.com/mikolaj92/demo/issues/1#issuecomment-2",
                        body="thanks!",
                        login="bob",
                        comment_id=2,
                    ),
                ]
            ),
        ),
        "pull_comments": GhCall(
            0,
            json.dumps(
                [
                    gh_comment(
                        html_url="https://github.com/mikolaj92/demo/pull/3#discussion_r3",
                        body="Looks good to me",
                        login="carol",
                        comment_id=3,
                    )
                ]
            ),
        ),
    }
