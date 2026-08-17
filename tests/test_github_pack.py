from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from github_pack import looks_like_patch_only, looks_like_ship_title, pack_survey
from github_pack.classify import (
    facts_are_merge_log,
    is_trusted_artifact_url,
    is_tryable,
    looks_like_merged_pr_fact,
    readme_tryable_url,
)
from github_pack.pack import README_WITHOUT_DEMO_REASON, readme_has_visible_demo
from github_survey import GhCall, survey_public_repo

from tests.gh_scripts import NOW, REPO, SHIP_RELEASE, b64_readme, merge_log_script, noise_script, ship_script, ScriptedGh

INSTALLABLE = "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n"
VISIBLE_DEMO = INSTALLABLE + "\n![demo](docs/demo.gif)\n"


class HeuristicTests(unittest.TestCase):
    def test_noise_vs_ship_titles(self) -> None:
        self.assertTrue(looks_like_patch_only("chore: bump deps"))
        self.assertTrue(looks_like_patch_only("typo in README"))
        self.assertTrue(looks_like_patch_only("docs: fix badge"))
        self.assertTrue(looks_like_patch_only("fix tests"))
        self.assertFalse(looks_like_ship_title("chore: bump deps"))
        self.assertTrue(looks_like_ship_title("feat: local HoM operator scores briefs"))
        self.assertTrue(looks_like_ship_title("Shipped the operator tick"))
        self.assertTrue(looks_like_ship_title("Treat GitHub repo root as a ship artifact"))
        self.assertFalse(looks_like_ship_title("Refactor storage helpers"))
        self.assertTrue(looks_like_merged_pr_fact("Merged PR #190: Treat GitHub repo root as a ship artifact"))
        self.assertFalse(looks_like_merged_pr_fact("Released v0.1.0"))
        self.assertTrue(
            facts_are_merge_log(
                [
                    {"text": "Merged PR #190: Treat GitHub repo root as a ship artifact"},
                    {"text": "Merged PR #187: feat: prior look"},
                    {"text": "README has an install/quickstart a stranger can run"},
                ]
            )
        )
        self.assertFalse(
            facts_are_merge_log(
                [
                    {"text": "Released v0.1.0"},
                    {"text": "Merged PR #12: feat: local HoM operator scores briefs"},
                ]
            )
        )


class PackSilenceTests(unittest.TestCase):
    def _pack(self, script: dict[str, GhCall]) -> dict:
        fake = ScriptedGh(script)
        with patch("subprocess.run", side_effect=AssertionError("pack must not call subprocess")):
            surveyed = survey_public_repo(REPO, gh=fake, now=NOW)
        return pack_survey(surveyed)

    def test_silence_on_commit_noise(self) -> None:
        out = self._pack(noise_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "commit_noise")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])

    def test_ship_and_tryable_packs_facts(self) -> None:
        out = self._pack(ship_script())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["brief_id"], "scan-v0-1-0")
        self.assertTrue(out["claims_ship"])
        self.assertTrue(out["tryable"])
        self.assertGreaterEqual(len(out["facts"]), 2)
        urls = {item["artifact_url"] for item in out["facts"] if item.get("artifact_url")}
        self.assertIn("https://github.com/mikolaj92/demo/pull/12", urls)
        self.assertIn("https://github.com/mikolaj92/demo/releases/tag/v0.1.0", urls)

    def test_merge_window_without_release_is_not_a_tryable_ship(self) -> None:
        out = self._pack(merge_log_script())
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not_tryable")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertNotIn("facts", out)

    def test_release_without_readme_url_is_not_tryable(self) -> None:
        out = self._pack(ship_script(readme=GhCall(0, b64_readme("# Demo\nWIP\n"))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "not_tryable")
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertFalse(
            is_tryable(
                {
                    "releases": [{"tagName": "v0.1.0"}],
                    "readme_text": "# Demo\nWIP\n",
                    "readme_url": "https://github.com/mikolaj92/demo/blob/main/README.md",
                },
                [{"text": "Released v0.1.0", "artifact_url": "https://github.com/mikolaj92/demo/releases/tag/v0.1.0"}],
            )
        )

    def test_text_only_readme_is_changelog_not_a_launch(self) -> None:
        self.assertFalse(readme_has_visible_demo(INSTALLABLE))
        self.assertFalse(readme_has_visible_demo("# Demo\n\n![ci](https://img.shields.io/github/stars/mikolaj92/demo)\n"))
        self.assertFalse(readme_has_visible_demo("# Demo\n\n![logo](docs/logo.png)\n"))
        self.assertTrue(readme_has_visible_demo(VISIBLE_DEMO))
        self.assertTrue(readme_has_visible_demo("# Demo\n\n<img src=\"docs/screen.png\" alt=\"screenshot\">\n"))
        self.assertTrue(
            readme_has_visible_demo(
                "# Demo\n\n![demo](https://github.com/user-attachments/assets/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee)\n"
            )
        )
        out = self._pack(ship_script(readme=GhCall(0, b64_readme(INSTALLABLE))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], README_WITHOUT_DEMO_REASON)
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertNotIn("facts", out)
        badge = self._pack(
            ship_script(
                readme=GhCall(
                    0,
                    b64_readme(INSTALLABLE + "\n![ci](https://img.shields.io/github/stars/mikolaj92/demo)\n"),
                )
            )
        )
        self.assertEqual(badge["status"], "noop")
        self.assertEqual(badge["reason"], README_WITHOUT_DEMO_REASON)

    def test_readme_url_outside_trusted_host_is_not_tryable(self) -> None:
        installable = INSTALLABLE
        untrusted = (
            "https://example.com/demo",
            "https://bit.ly/try-this",
            "https://github.com/mikolaj92/demo?utm_source=hn",
            "https://github.com/mikolaj92/demo/click-here",
        )
        for url in untrusted:
            with self.subTest(url=url):
                self.assertFalse(is_trusted_artifact_url(url))
                self.assertIsNone(
                    readme_tryable_url(
                        {"readme_text": installable, "readme_url": url, "meta": {"homepageUrl": url}}
                    )
                )
                self.assertFalse(
                    is_tryable(
                        {
                            "releases": [{"tagName": "v0.1.0"}],
                            "readme_text": installable,
                            "readme_url": url,
                            "meta": {"homepageUrl": url},
                        },
                        [{"text": "Released v0.1.0", "artifact_url": SHIP_RELEASE}],
                    )
                )
                out = pack_survey(
                    {
                        "status": "ok",
                        "ok": True,
                        "repo": REPO,
                        "now": NOW,
                        "survey": {
                            "meta": {"description": "Local operator with a working install", "homepageUrl": url},
                            "prs": [
                                {
                                    "number": 12,
                                    "title": "feat: local HoM operator scores briefs",
                                    "url": "https://github.com/mikolaj92/demo/pull/12",
                                }
                            ],
                            "releases": [{"tagName": "v0.1.0", "name": "v0.1.0"}],
                            "tags": [{"name": "v0.1.0"}],
                            "readme_text": installable,
                            "readme_url": url,
                        },
                    }
                )
                self.assertEqual(out["status"], "noop")
                self.assertEqual(out["reason"], "not_tryable")
                self.assertTrue(out["ok"])
                self.assertIsNone(out["brief_id"])
                self.assertNotIn("facts", out)

    def test_github_readme_url_stays_tryable(self) -> None:
        url = "https://github.com/mikolaj92/demo/blob/main/README.md"
        self.assertTrue(is_trusted_artifact_url(url))
        self.assertTrue(is_trusted_artifact_url("https://www.github.com/mikolaj92/demo"))
        self.assertEqual(
            readme_tryable_url(
                {
                    "readme_text": "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n",
                    "readme_url": url,
                    "meta": {"homepageUrl": "https://bit.ly/ignore-me"},
                }
            ),
            url,
        )

    def test_waitlist_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-wait",
                                "name": "Join the waitlist",
                                "isDraft": False,
                                "isPrerelease": False,
                                "publishedAt": "2026-08-12T18:00:00Z",
                            }
                        ]
                    ),
                )
            )
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], "waitlist_not_tryable")

    def test_prior_silence_passes_through(self) -> None:
        out = pack_survey({"status": "noop", "ok": True, "reason": "gh_missing", "repo": REPO})
        self.assertEqual(out["reason"], "gh_missing")
        self.assertEqual(out["status"], "noop")
