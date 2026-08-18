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
from github_pack.pack import (
    README_WITHOUT_DEMO_REASON,
    README_WITHOUT_QUICKSTART_REASON,
    REVERTED_NOT_A_SHIP_REASON,
    SOLICIT_GESTURE_REASON,
    looks_like_same_window_revert,
    looks_like_solicit_gesture,
    readme_has_copyable_start,
    readme_has_visible_demo,
)
from github_survey import GhCall, survey_public_repo

from tests.gh_scripts import NOW, REPO, SHIP_PR, SHIP_RELEASE, b64_readme, merge_log_script, noise_script, repo_json, ship_script, ScriptedGh

INSTALLABLE = "# Demo\n\n```bash\nuv run influenzer-tick --once\n```\n"
VISIBLE_DEMO = INSTALLABLE + "\n![demo](docs/demo.gif)\n"
PROSE_ONLY = (
    "# Demo\n\nInstall with pip install influenzer, then uv run the tick.\n"
    "\n![demo](docs/demo.gif)\n"
)


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
        ship = {
            "number": 12,
            "title": "feat: local HoM operator scores briefs",
            "url": "https://github.com/mikolaj92/demo/pull/12",
        }
        self.assertTrue(
            looks_like_same_window_revert(
                [ship, {"number": 13, "title": 'Revert "feat: local HoM operator scores briefs"'}]
            )
        )
        self.assertTrue(
            looks_like_same_window_revert([ship, {"number": 13, "title": "Revert #12"}])
        )
        self.assertTrue(
            looks_like_same_window_revert(
                [ship, {"number": 13, "title": "Revert the launch", "body": "This reverts #12."}]
            )
        )
        self.assertFalse(looks_like_same_window_revert([ship]))
        self.assertFalse(
            looks_like_same_window_revert([ship, {"number": 13, "title": "Revert #99"}])
        )
        asks = (
            "star the repo after you try it",
            "please star us",
            "give us a star",
            "please upvote this",
            "follow us",
            "RT this",
            "daj nam gwiazdkę",
        )
        for text in asks:
            with self.subTest(text=text):
                self.assertTrue(looks_like_solicit_gesture(text))
        self.assertFalse(looks_like_solicit_gesture("follow the README to run the demo"))
        self.assertFalse(looks_like_solicit_gesture("Local tick scores briefs and emits a draft"))


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

    def test_prose_install_is_not_a_copyable_start(self) -> None:
        self.assertFalse(readme_has_copyable_start(PROSE_ONLY))
        self.assertFalse(readme_has_copyable_start("# Demo\n\nSee the docs to install.\n\n![demo](docs/demo.gif)\n"))
        self.assertTrue(readme_has_copyable_start(VISIBLE_DEMO))
        self.assertTrue(readme_has_copyable_start("# Demo\n\nRun `brew install influenzer` and go.\n"))
        self.assertTrue(readme_has_copyable_start("# Demo\n\n```\n$ pip install influenzer\n```\n"))
        out = self._pack(ship_script(readme=GhCall(0, b64_readme(PROSE_ONLY))))
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], README_WITHOUT_QUICKSTART_REASON)
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertNotIn("facts", out)
        self.assertNotIn("claims_ship", out)

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

    def test_same_window_revert_is_not_a_ship(self) -> None:
        out = self._pack(
            ship_script(
                prs=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "number": 12,
                                "title": "feat: local HoM operator scores briefs",
                                "url": SHIP_PR,
                                "mergedAt": "2026-08-12T12:00:00Z",
                                "body": "Stranger can clone and run.",
                            },
                            {
                                "number": 13,
                                "title": 'Revert "feat: local HoM operator scores briefs"',
                                "url": "https://github.com/mikolaj92/demo/pull/13",
                                "mergedAt": "2026-08-12T16:00:00Z",
                                "body": "This reverts #12.",
                            },
                        ]
                    ),
                )
            )
        )
        self.assertEqual(out["status"], "noop")
        self.assertEqual(out["reason"], REVERTED_NOT_A_SHIP_REASON)
        self.assertTrue(out["ok"])
        self.assertIsNone(out["brief_id"])
        self.assertNotIn("claims_ship", out)
        self.assertNotIn("facts", out)

        other = self._pack(
            ship_script(
                prs=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "number": 12,
                                "title": "feat: local HoM operator scores briefs",
                                "url": SHIP_PR,
                                "mergedAt": "2026-08-12T12:00:00Z",
                                "body": "Stranger can clone and run.",
                            },
                            {
                                "number": 13,
                                "title": "Revert #99",
                                "url": "https://github.com/mikolaj92/demo/pull/13",
                                "mergedAt": "2026-08-12T16:00:00Z",
                                "body": "",
                            },
                        ]
                    ),
                )
            )
        )
        self.assertEqual(other["status"], "ok")
        self.assertTrue(other["claims_ship"])

    def test_star_upvote_follow_or_rt_ask_is_silence(self) -> None:
        asks = (
            "please star us if this local tick helped",
            "give us a star after you try it",
            "please upvote this Show HN",
            "follow us for more local-first tools",
            "RT this if the install works",
        )
        for text in asks:
            with self.subTest(text=text):
                out = self._pack(ship_script(repo=GhCall(0, repo_json(description=text))))
                self.assertEqual(out["status"], "noop")
                self.assertEqual(out["reason"], SOLICIT_GESTURE_REASON)
                self.assertTrue(out["ok"])
                self.assertIsNone(out["brief_id"])
                self.assertNotIn("facts", out)
                dumped = json.dumps(out)
                self.assertNotIn("star the repo", dumped)
                self.assertNotIn("upvote", dumped.lower())
                self.assertNotIn("follow us", dumped.lower())
        readme_ask = self._pack(
            ship_script(
                readme=GhCall(
                    0,
                    b64_readme(VISIBLE_DEMO + "\nPlease star the repo after you try it.\n"),
                )
            )
        )
        self.assertEqual(readme_ask["status"], "noop")
        self.assertEqual(readme_ask["reason"], SOLICIT_GESTURE_REASON)
        self.assertNotIn("facts", readme_ask)

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

    def test_webinar_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-event",
                                "name": "Join us Thursday for the webinar",
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
        self.assertEqual(out["reason"], "event_not_a_ship")

    def test_happy_friday_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-friday",
                                "name": "Happy Friday",
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
        self.assertEqual(out["reason"], "calendar_filler")

    def test_thanks_for_stars_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-stars",
                                "name": "Thanks for 1000 stars",
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
        self.assertEqual(out["reason"], "counter_thanks")

    def test_you_know_who_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-fog",
                                "name": "You know who still scores remotely",
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
        self.assertEqual(out["reason"], "fog")

    def test_desk_setup_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-desk",
                                "name": "Desk setup for the local tick",
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
        self.assertEqual(out["reason"], "founder_journal")

    def test_ebook_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-ebook",
                                "name": "Ebook for the local tick",
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
        self.assertEqual(out["reason"], "lead_magnet")

    def test_last_chance_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-last-chance",
                                "name": "Last chance for the local tick",
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
        self.assertEqual(out["reason"], "fomo")

    def test_drake_meme_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-drake",
                                "name": "Drake meme for the local tick",
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
        self.assertEqual(out["reason"], "meme")

    def test_pitch_deck_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-deck",
                                "name": "Pitch deck for the local tick",
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
        self.assertEqual(out["reason"], "deck_not_an_artifact")

    def test_linktree_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-linktree",
                                "name": "Linktree for the local tick",
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
        self.assertEqual(out["reason"], "linktree_not_an_artifact")

    def test_rebrand_release_is_silence(self) -> None:
        out = self._pack(
            ship_script(
                releases=GhCall(
                    0,
                    json.dumps(
                        [
                            {
                                "tagName": "v0.0.0-rebrand",
                                "name": "Rebrand of the local tick",
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
        self.assertEqual(out["reason"], "logo_reveal_not_a_ship")

    def test_prior_silence_passes_through(self) -> None:
        out = pack_survey({"status": "noop", "ok": True, "reason": "gh_missing", "repo": REPO})
        self.assertEqual(out["reason"], "gh_missing")
        self.assertEqual(out["status"], "noop")
