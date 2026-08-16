from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from influenzer.cli import main
from influenzer.config import Config, write_config
from influenzer.hom import (
    Brief,
    Fact,
    HomError,
    angle_body_hash,
    apply_brief,
    brief_from_mapping,
    compose_draft,
    drop_repeat_angle,
    is_ship_artifact,
    score_brief,
)
from influenzer.playbook import (
    ARENAS,
    CANON_URL,
    LIVING_STACK_REASON,
    SOCIAL_ARENAS,
    STACK_ARENAS,
    STACK_HOURS,
    ArenaId,
    StoryKind,
    Verdict,
    choose_arena,
    living_stack_arena,
    stack_costume_reason,
    is_blog_host_url,
    is_launch_host_url,
    is_news_host_url,
    is_ranking_host_url,
    is_store_host_url,
    is_tryable_artifact_url,
    is_shortener_url,
    is_video_host_url,
    invented_metric_reason,
    is_model_host_url,
    looks_like_bot_author,
    looks_like_bot_bump_week,
    looks_like_contest,
    looks_like_model_in_frame,
    looks_like_dunk,
    looks_like_foreign_wave,
    looks_like_reply,
    is_parent_post_url,
    looks_like_engagement_bait,
    looks_like_ranking_dump,
    looks_like_thread,
    looks_like_emoji_title,
    looks_like_hashtag_wall,
    looks_like_hire_fundraise,
    looks_like_invented_opinion,
    looks_like_listicle_title,
    looks_like_person_mention,
    looks_like_private_conversation,
    looks_like_dead_link,
    looks_like_dead_release_asset,
    looks_like_issues_disabled,
    looks_like_fork,
    looks_like_empty_repo,
    looks_like_private_repo,
    looks_like_archived_repo,
    looks_like_login_gate,
    looks_like_shortener,
    looks_like_utm_farm,
    looks_like_click_here,
    looks_like_server_splash,
    looks_like_roadmap,
    looks_like_pending_ci,
    looks_like_failed_ci,
    looks_like_prerelease,
    looks_like_source_available_as_oss,
    looks_like_source_available_license,
    looks_like_world_commentary,
    looks_like_shouty_title,
    looks_like_store_pitch,
    looks_like_launch_pitch,
    looks_like_superlative,
    looks_like_version_diff,
    looks_like_monday_without_history,
    looks_like_weekly_update,
    has_monday_history,
    has_real_feedback,
    metric_tokens,
    quote_without_sourced_excerpt,
    strip_person_mentions,
    unquotable_reason,
)
from influenzer.scheduler import tick
from influenzer.storage import StateRepository
from influenzer.tick_all import main as tick_all_main


SHIP_PR = "https://github.com/mikolaj92/influenzer/pull/12"
SHIP_ISSUE = "https://github.com/mikolaj92/influenzer/issues/4"
SHIP_RELEASE = "https://github.com/mikolaj92/influenzer/releases/tag/v0.1.0"
SHIP_REPO = "https://github.com/mikolaj92/influenzer"
FEEDBACK_COMMENT = "https://github.com/mikolaj92/influenzer/issues/4#issuecomment-101"


def _project(repo: StateRepository, project_id: str = "app-1") -> None:
    from influenzer.domain import Project

    repo.save_project(
        Project.create(
            project_id=project_id,
            slug=project_id.replace("-", ""),
            name="App",
            display_name="App",
            voice="product",
            audience="builders",
            maintainer="mikolaj92",
            kind="app",
        )
    )


class PlaybookCopyTests(unittest.TestCase):
    def test_every_arena_has_costume_and_wave_checklist(self) -> None:
        self.assertGreaterEqual(len(ARENAS), 10)
        for arena, play in ARENAS.items():
            with self.subTest(arena=arena.value):
                self.assertTrue(play.costume)
                self.assertGreaterEqual(len(play.wave), 3)
                self.assertTrue(play.canon_url.startswith(CANON_URL))
                self.assertNotIn("champion", play.game.lower())

    def test_stack_is_github_and_hn_for_forty_eight_hours(self) -> None:
        self.assertEqual(STACK_HOURS, 48)
        self.assertEqual(STACK_ARENAS, frozenset({ArenaId.GITHUB, ArenaId.HN}))
        self.assertEqual(LIVING_STACK_REASON, "living_stack")

    def test_choose_arena_keeps_living_github_or_hn_costume(self) -> None:
        self.assertEqual(
            choose_arena(stack_arena=ArenaId.GITHUB, tryable=True, story_kind=StoryKind.MAJOR, clickable=True),
            ArenaId.GITHUB,
        )
        self.assertEqual(
            choose_arena(
                preferred_arena=ArenaId.HN,
                stack_arena=ArenaId.GITHUB,
                tryable=True,
                story_kind=StoryKind.MAJOR,
                clickable=True,
            ),
            ArenaId.GITHUB,
        )
        self.assertEqual(
            choose_arena(tryable=True, story_kind=StoryKind.MAJOR, clickable=True),
            ArenaId.HN,
        )
        self.assertEqual(choose_arena(tryable=False, story_kind=StoryKind.MAJOR), ArenaId.GITHUB)
        self.assertEqual(
            living_stack_arena(((ArenaId.HN, "2026-08-13T05:00:00Z"),), "2026-08-14T04:59:59Z"),
            ArenaId.HN,
        )
        self.assertIsNone(
            living_stack_arena(((ArenaId.HN, "2026-08-13T05:00:00Z"),), "2026-08-15T05:00:00Z")
        )
        self.assertIsNone(
            living_stack_arena(
                (
                    (ArenaId.GITHUB, "2026-08-13T05:00:00Z"),
                    (ArenaId.GITHUB, "2026-08-14T04:00:00Z"),
                ),
                "2026-08-15T05:00:00Z",
            )
        )
        self.assertEqual(
            living_stack_arena(((ArenaId.HN, "not-a-clock"),), "2026-08-20T05:00:00Z"),
            ArenaId.HN,
        )
        self.assertEqual(
            living_stack_arena(
                (
                    (ArenaId.GITHUB, "not-a-clock"),
                    (ArenaId.GITHUB, "2026-08-13T05:00:00Z"),
                ),
                "2026-08-20T05:00:00Z",
            ),
            ArenaId.GITHUB,
        )
        self.assertEqual(
            stack_costume_reason(ArenaId.X, ArenaId.HN),
            LIVING_STACK_REASON,
        )
        self.assertIsNone(stack_costume_reason(ArenaId.HN, ArenaId.HN))
        self.assertIsNone(stack_costume_reason(None, ArenaId.HN))

    def test_ship_artifact_accepts_repo_pr_issue_release(self) -> None:
        self.assertTrue(is_ship_artifact(SHIP_PR))
        self.assertTrue(is_ship_artifact(SHIP_ISSUE))
        self.assertTrue(is_ship_artifact(SHIP_RELEASE))
        self.assertTrue(is_ship_artifact(SHIP_REPO))
        self.assertTrue(is_ship_artifact(SHIP_REPO + "/"))
        self.assertFalse(is_ship_artifact("https://example.com/ship"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/commit/abc"))
        self.assertFalse(is_ship_artifact("https://gist.github.com/mikolaj92/abc"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/wiki"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/compare/main...dev"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/tree/main"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/blob/main/README.md"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/actions"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92/influenzer/settings"))
        self.assertFalse(is_ship_artifact("https://github.com/mikolaj92"))
        self.assertFalse(is_ship_artifact("https://github.com/orgs/github"))
        self.assertFalse(is_ship_artifact("https://github.com/settings/profile"))

    def test_tryable_url_is_https_on_allowlisted_host_only(self) -> None:
        self.assertTrue(is_tryable_artifact_url(SHIP_REPO))
        self.assertTrue(is_tryable_artifact_url(SHIP_PR))
        self.assertTrue(is_tryable_artifact_url("https://www.github.com/mikolaj92/influenzer"))
        almost = (
            "http://github.com/mikolaj92/influenzer",
            "http://github.com/mikolaj92/influenzer/pull/12",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "file:///etc/passwd",
            "https://example.com/demo",
            "https://bit.ly/try-this",
            "https://github.com/mikolaj92/influenzer?utm_source=hn",
            "https://github.com/mikolaj92/influenzer/click-here",
            "HTTPS://github.com.evil.com/mikolaj92/influenzer",
            "https://user:pass@github.com/mikolaj92/influenzer",
        )
        for url in almost:
            with self.subTest(url=url):
                self.assertFalse(is_tryable_artifact_url(url))
                self.assertFalse(is_ship_artifact(url))
        self.assertTrue(is_shortener_url("https://bit.ly/try-this"))
        self.assertTrue(looks_like_shortener("skracacz: https://t.co/abc"))
        self.assertTrue(looks_like_utm_farm("https://github.com/mikolaj92/influenzer?utm_source=hn"))
        self.assertTrue(looks_like_click_here("kliknij tu"))
        self.assertFalse(looks_like_shortener("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_utm_farm("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_click_here("Local tick scores briefs and emits a draft"))

    def test_video_host_is_youtube_vimeo_loom_not_a_repo(self) -> None:
        films = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://youtube-nocookie.com/embed/dQw4w9WgXcQ",
            "http://vimeo.com/123456789",
            "https://player.vimeo.com/video/123456789",
            "https://www.loom.com/share/abc123",
        )
        for url in films:
            with self.subTest(url=url):
                self.assertTrue(is_video_host_url(url))
                self.assertFalse(is_ship_artifact(url))
        self.assertFalse(is_video_host_url(SHIP_REPO))
        self.assertFalse(is_video_host_url("https://example.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_video_host_url("https://notyoutube.com/watch?v=dQw4w9WgXcQ"))
        self.assertFalse(is_video_host_url("https://youtube.com.evil.com/watch"))

    def test_store_host_is_app_store_play_testflight_not_a_repo(self) -> None:
        stores = (
            "https://apps.apple.com/app/id123456789",
            "https://itunes.apple.com/us/app/id123456789",
            "https://play.google.com/store/apps/details?id=com.example.app",
            "https://testflight.apple.com/join/abc123",
        )
        for url in stores:
            with self.subTest(url=url):
                self.assertTrue(is_store_host_url(url))
                self.assertFalse(is_ship_artifact(url))
                self.assertFalse(is_video_host_url(url))
        self.assertFalse(is_store_host_url(SHIP_REPO))
        self.assertFalse(is_store_host_url("https://example.com/app-store"))
        self.assertFalse(is_store_host_url("https://notplay.google.com/store"))
        self.assertFalse(is_store_host_url("https://apps.apple.com.evil.com/app"))
        self.assertTrue(looks_like_store_pitch("download the app on TestFlight"))
        self.assertTrue(looks_like_store_pitch("Get it on the App Store"))
        self.assertFalse(looks_like_store_pitch("a stranger can click and run the demo"))

    def test_listicle_title_is_n_ways_you_wont_believe_or_trailing_bang(self) -> None:
        bait = (
            "7 ways to score briefs",
            "N ways a stranger can try it",
            "you won't believe this local tick",
            "you will not believe this local tick",
            "Show HN: you wont believe this local tick",
            "Local tick scores briefs!",
        )
        for title in bait:
            with self.subTest(title=title):
                self.assertTrue(looks_like_listicle_title(title))
        self.assertFalse(looks_like_listicle_title("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_listicle_title("this is a great way to run ticks"))
        self.assertFalse(looks_like_listicle_title("Wow! Local tick scores briefs"))

    def test_shouty_title_is_whole_title_caps_not_one_or_two_acronyms(self) -> None:
        bait = (
            "LOCAL TICK SCORES BRIEFS AND EMITS A DRAFT",
            "Show HN: LOCAL TICK SCORES BRIEFS AND EMITS A DRAFT",
            "STRANGERS CAN CLICK AND RUN THE DEMO TODAY",
        )
        for title in bait:
            with self.subTest(title=title):
                self.assertTrue(looks_like_shouty_title(title))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "CLI scores briefs and emits a draft",
            "Show HN: CLI scores briefs",
            "API",
            "HN CLI",
            "README GIF",
        )
        for title in allowed:
            with self.subTest(title=title):
                self.assertFalse(looks_like_shouty_title(title))

    def test_emoji_title_is_pictograph_not_ascii_or_arrow(self) -> None:
        bait = (
            "Local tick scores briefs 🚀",
            "Show HN: Local tick scores briefs ✨",
            "\U0001f389 Local tick scores briefs",
            "Local tick \U0001f600 scores briefs",
            "Local tick scores briefs ⭐",
        )
        for title in bait:
            with self.subTest(title=title):
                self.assertTrue(looks_like_emoji_title(title))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Show HN: CLI scores briefs",
            "README one-liner \u2192 GIF \u2192 working quickstart",
            "C++ scores briefs",
        )
        for title in allowed:
            with self.subTest(title=title):
                self.assertFalse(looks_like_emoji_title(title))

    def test_blog_host_is_medium_substack_devto_hashnode_not_a_repo(self) -> None:
        blogs = (
            "https://medium.com/@someone/we-shipped-a-thing-abc123",
            "https://someone.medium.com/we-shipped-a-thing-abc123",
            "https://someone.substack.com/p/we-shipped-a-thing",
            "https://dev.to/someone/we-shipped-a-thing",
            "https://someone.hashnode.dev/we-shipped-a-thing",
            "https://hashnode.com/@someone/we-shipped-a-thing",
        )
        for url in blogs:
            with self.subTest(url=url):
                self.assertTrue(is_blog_host_url(url))
                self.assertFalse(is_ship_artifact(url))
                self.assertFalse(is_video_host_url(url))
                self.assertFalse(is_store_host_url(url))
        self.assertFalse(is_blog_host_url(SHIP_REPO))
        self.assertFalse(is_blog_host_url("https://example.com/medium"))
        self.assertFalse(is_blog_host_url("https://notmedium.com/we-shipped"))
        self.assertFalse(is_blog_host_url("https://medium.com.evil.com/we-shipped"))

    def test_launch_host_is_product_hunt_or_betalist_not_a_repo(self) -> None:
        boards = (
            "https://www.producthunt.com/posts/local-tick",
            "https://producthunt.com/posts/local-tick",
            "https://www.betalist.com/startups/local-tick",
            "https://betalist.com/startups/local-tick",
        )
        for url in boards:
            with self.subTest(url=url):
                self.assertTrue(is_launch_host_url(url))
                self.assertFalse(is_ship_artifact(url))
                self.assertFalse(is_video_host_url(url))
                self.assertFalse(is_store_host_url(url))
                self.assertFalse(is_blog_host_url(url))
        self.assertFalse(is_launch_host_url(SHIP_REPO))
        self.assertFalse(is_launch_host_url("https://example.com/producthunt"))
        self.assertFalse(is_launch_host_url("https://notproducthunt.com/posts/local-tick"))
        self.assertFalse(is_launch_host_url("https://producthunt.com.evil.com/posts/local-tick"))
        self.assertTrue(looks_like_launch_pitch("launch on PH today"))
        self.assertTrue(looks_like_launch_pitch("we launched on Product Hunt"))
        self.assertTrue(looks_like_launch_pitch("see us on BetaList"))
        self.assertFalse(looks_like_launch_pitch("a stranger can click and run the demo"))

    def test_ranking_host_is_hn_star_chart_or_badge_not_a_repo(self) -> None:
        charts = (
            "https://news.ycombinator.com/item?id=123",
            "https://news.ycombinator.com/",
            "https://hn.algolia.com/?q=influenzer",
            "https://star-history.com/#mikolaj92/influenzer",
            "https://star-history.t9t.io/#mikolaj92/influenzer",
            "https://img.shields.io/github/stars/mikolaj92/influenzer",
            "https://shields.io/github/stars/mikolaj92/influenzer",
            "https://gitstar-ranking.com/mikolaj92/influenzer",
            "https://github.com/mikolaj92/influenzer/stargazers",
            "https://github.com/mikolaj92/influenzer/watchers",
            "https://github.com/trending",
        )
        for url in charts:
            with self.subTest(url=url):
                self.assertTrue(is_ranking_host_url(url))
                self.assertFalse(is_ship_artifact(url))
                self.assertFalse(is_video_host_url(url))
                self.assertFalse(is_store_host_url(url))
                self.assertFalse(is_blog_host_url(url))
                self.assertFalse(is_launch_host_url(url))
        self.assertFalse(is_ranking_host_url(SHIP_REPO))
        self.assertFalse(is_ranking_host_url(SHIP_PR))
        self.assertFalse(is_ranking_host_url("https://example.com/hn-front"))
        self.assertFalse(is_ranking_host_url("https://notnews.ycombinator.com/item?id=1"))
        self.assertFalse(is_ranking_host_url("https://news.ycombinator.com.evil.com/item?id=1"))

    def test_superlative_is_revolutionary_worlds_first_or_ai_powered(self) -> None:
        slogans = (
            "revolutionary local tick",
            "the world's first local tick",
            "the worlds first local tick",
            "a world-first operator tick",
            "an AI-powered local tick",
            "an AI powered local tick",
        )
        for text in slogans:
            with self.subTest(text=text):
                self.assertTrue(looks_like_superlative(text))
        self.assertFalse(looks_like_superlative("Local tick scores briefs and emits a draft"))
        self.assertFalse(looks_like_superlative("first local tick on this machine"))

    def test_dunk_is_mockery_not_naming_a_predecessor(self) -> None:
        dunks = (
            "Loki sucks, use this local tick instead",
            "their project is trash",
            "that clone is a joke",
            "dunking on Loki with a local tick",
            "laughing at their project",
            "roast their repo",
            "that trash of a project",
        )
        for text in dunks:
            with self.subTest(text=text):
                self.assertTrue(looks_like_dunk(text))
        allowed = (
            "Unlike Loki, this scores briefs locally",
            "Loki is the predecessor; the difference is a local tick",
            "Loki is worth helping with a local tick",
            "Compared to Loki we keep the draft local",
            "Local tick scores briefs and emits a draft",
            "the project is dead until the install works",
            "HN is dead until the first hour",
            "the install is dead until the demo works",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_dunk(text))

    def test_foreign_wave_is_reply_under_someone_elses_post(self) -> None:
        parent = "https://x.com/other/status/123456789"
        self.assertTrue(is_parent_post_url(parent))
        self.assertFalse(is_parent_post_url(SHIP_PR))
        self.assertFalse(is_parent_post_url("https://x.com/other"))
        self.assertTrue(looks_like_reply("reply under a rising thread"))
        self.assertTrue(looks_like_reply("in-reply-to a mid-KOL post"))
        self.assertTrue(looks_like_reply("pod postem o launchu"))
        self.assertFalse(looks_like_reply("thinking about posting a launch reply"))
        self.assertFalse(looks_like_reply("Local tick scores briefs and emits a draft"))
        self.assertTrue(
            looks_like_foreign_wave(
                (
                    ("parent", "rising mid-KOL post", parent),
                    ("signal", "Local tick scores briefs and emits a draft", SHIP_PR),
                )
            )
        )
        self.assertTrue(
            looks_like_foreign_wave(
                (
                    ("signal", "reply under a rising thread", parent),
                    ("signal", "strangers can click and run the demo today", SHIP_PR),
                )
            )
        )
        self.assertFalse(
            looks_like_foreign_wave(
                (
                    ("parent", "Show HN about mikolaj92/influenzer", "https://news.ycombinator.com/item?id=1"),
                    ("signal", "Local tick scores briefs and emits a draft", SHIP_PR),
                )
            )
        )
        self.assertFalse(
            looks_like_foreign_wave(
                (
                    ("parent", "our ship thread", SHIP_PR),
                    ("signal", "strangers can click and run the demo today", SHIP_PR),
                )
            )
        )
        self.assertTrue(
            looks_like_foreign_wave(
                (("parent", "a parent URL alone", "https://x.com/other/status/1"),)
            )
        )
        self.assertTrue(
            looks_like_foreign_wave((("parent", "a GitHub parent URL alone", SHIP_ISSUE),))
        )
        self.assertTrue(
            looks_like_foreign_wave(
                (
                    ("parent", "someone else's repo", "https://github.com/other/tool"),
                    ("signal", "Local tick scores briefs and emits a draft", SHIP_PR),
                )
            )
        )
        self.assertFalse(
            looks_like_foreign_wave(
                (("signal", "Local tick scores briefs and emits a draft", SHIP_PR),)
            )
        )

    def test_quote_needs_feedback_excerpt_with_url_not_users_love(self) -> None:
        self.assertTrue(looks_like_invented_opinion("users love the local tick"))
        self.assertTrue(looks_like_invented_opinion("Customers love this operator"))
        self.assertTrue(looks_like_invented_opinion("loved by users on day one"))
        self.assertFalse(looks_like_invented_opinion("Local tick scores briefs and emits a draft"))
        self.assertTrue(quote_without_sourced_excerpt('A stranger said "this is great"', ()))
        self.assertTrue(
            quote_without_sourced_excerpt(
                'A stranger said "this is great"',
                ("something else entirely",),
            )
        )
        self.assertFalse(
            quote_without_sourced_excerpt(
                'A stranger said "the Windows install fails"',
                ("@bob: the Windows install fails with a traceback",),
            )
        )
        self.assertEqual(
            unquotable_reason((("signal", 'users said "this is great"', SHIP_PR),)),
            "quote_without_excerpt",
        )
        self.assertEqual(
            unquotable_reason((("excerpt", '"great tool"', None),)),
            "quote_without_excerpt",
        )
        self.assertEqual(
            unquotable_reason((("signal", "users love the local tick", SHIP_PR),)),
            "invented_opinion",
        )
        self.assertIsNone(
            unquotable_reason(
                (
                    ("issue_comment", "@bob: the Windows install fails", FEEDBACK_COMMENT),
                    ("signal", 'A stranger said "the Windows install fails"', None),
                )
            )
        )

    def test_number_in_costume_must_already_be_in_brief(self) -> None:
        self.assertIn("10x", metric_tokens("we are 10x faster"))
        self.assertIn("10x", metric_tokens("we are 10× faster"))
        self.assertIn("1m users", metric_tokens("1M users on day one"))
        self.assertIn("1m", metric_tokens("1M users on day one"))
        self.assertIn("benchmark", metric_tokens("our benchmark beats the queue"))
        self.assertFalse(metric_tokens("Local tick scores briefs and emits a draft"))
        facts = (("signal", "Local tick scores briefs and emits a draft", SHIP_PR),)
        self.assertEqual(
            invented_metric_reason(facts, extra="Show HN: 10x faster local tick"),
            "invented_metric",
        )
        self.assertEqual(
            unquotable_reason(facts, extra="Show HN: 10x faster local tick"),
            "invented_metric",
        )
        self.assertEqual(
            unquotable_reason(facts, extra="1M users already use the local tick"),
            "invented_metric",
        )
        self.assertEqual(
            unquotable_reason(facts, extra="benchmark: local tick beats the queue"),
            "invented_metric",
        )
        self.assertIsNone(
            unquotable_reason(
                (("signal", "Local tick is 10x faster than the queue", SHIP_PR),),
                extra="Show HN: Local tick is 10x faster than the queue",
            )
        )
        self.assertFalse(metric_tokens(SHIP_PR))
        self.assertIsNone(
            invented_metric_reason(
                facts,
                extra=f"Show HN: Local tick scores briefs\n\n{SHIP_PR}",
            )
        )
        self.assertIsNone(invented_metric_reason(facts))
        self.assertIsNone(unquotable_reason(facts))

    def test_engagement_bait_is_a_gesture_ask_not_a_feedback_question(self) -> None:
        bait = (
            "Agree?",
            "agree ?",
            "like if this helped",
            "Like if you want Windows support",
            "upvote if you found this useful",
            "rt if this saved you an hour",
            "comment one word",
            "comment just one word",
            "comment a word below",
            "Local tick scores briefs \u2193",
            "tap the arrow \u2b07",
            "more below \U0001F447",
        )
        for text in bait:
            with self.subTest(text=text):
                self.assertTrue(looks_like_engagement_bait(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "engagement_bait",
                )
        questions = (
            "How do I install this when uv is missing?",
            "The Windows install fails with a traceback",
            "Does the local tick score a thin brief?",
            "Do you agree this is a bug?",
            "I like this local tick",
            "Leave a comment if the install fails",
            "Local tick scores briefs and emits a draft",
        )
        for text in questions:
            with self.subTest(text=text):
                self.assertFalse(looks_like_engagement_bait(text))
        excerpt = "How do I install this when uv is missing?"
        self.assertIsNone(
            unquotable_reason(
                (
                    ("issue_comment", f"@bob: {excerpt}", FEEDBACK_COMMENT),
                    ("signal", f'A stranger said "{excerpt}"', SHIP_PR),
                )
            )
        )

    def test_contest_is_giveaway_raffle_or_prize_for_follow(self) -> None:
        contests = (
            "giveaway of the local tick",
            "Give-away: one license",
            "raffle for a seat",
            "sweepstake next week",
            "contest: follow to win",
            "konkurs na follow",
            "losowanie licencji",
            "RT to win a license",
            "retweet to win",
            "follow to win a seat",
            "win if you follow",
            "prize for a follow",
            "nagroda za follow",
            "enter to win",
            "wygraj licencję",
            "do wygrania: licencja",
        )
        for text in contests:
            with self.subTest(text=text):
                self.assertTrue(looks_like_contest(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "contest",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "follow the README to run the demo",
            "star the repo after you try it",
            "Unlike Loki, this scores briefs locally",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_contest(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_model_in_frame_is_prompt_dump_or_i_asked_chatgpt(self) -> None:
        dumps = (
            "I asked ChatGPT how to score a brief",
            "I asked the model how to score a brief",
            "I asked an LLM for a Show HN",
            "we asked ChatGPT for a launch angle",
            "asked ChatGPT to write the Show HN",
            "I prompted Claude for a one-liner",
            "I used Gemini to draft the post",
            "as ChatGPT I would ship the local tick",
            "as an AI I would ship the local tick",
            "as an AI language model I scored the brief",
            "as a language model I cannot click the demo",
            "I'm an AI writing the launch post",
            "I am a large language model scoring briefs",
            "ChatGPT said the local tick is ready",
            "according to ChatGPT the install works",
            "here's the prompt I used for the launch",
            "Prompt: write a Show HN for the local tick",
            "my ChatGPT prompt for the launch",
            "prompt dump of the local tick",
            "ChatGPT conversation about the local tick",
            "conversation with the model about the local tick",
            "dump of the model scoring the brief",
            "You are a helpful assistant. Score this brief.",
            "System: You are Influenzer. Write a Show HN.",
            "zapytałem ChatGPT o lokalny tick",
            "rozmowa z ChatGPT o lokalnym ticku",
            "zrzut rozmowy z modelem",
            "jako AI napisałem kąt",
            "jako model językowy oceniam brief",
            "wkleiłem prompt do ChatGPT",
            "oto mój prompt",
            "generated by ChatGPT",
            "written by an AI",
            "https://chat.openai.com/c/abc a launch angle",
            "https://chatgpt.com/share/xyz I asked for a title",
            "User: write a Show HN\nAssistant: Show HN: local tick",
        )
        for text in dumps:
            with self.subTest(text=text):
                self.assertTrue(looks_like_model_in_frame(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "model_in_frame",
                )
        self.assertTrue(is_model_host_url("https://chat.openai.com/c/abc"))
        self.assertTrue(is_model_host_url("https://chatgpt.com/share/xyz"))
        self.assertTrue(is_model_host_url("https://claude.ai/chat/1"))
        self.assertTrue(is_model_host_url("https://gemini.google.com/app"))
        self.assertFalse(is_model_host_url(SHIP_PR))
        self.assertFalse(is_model_host_url("https://example.com/chatgpt"))
        self.assertFalse(is_model_host_url("https://chatgpt.com.evil.com/share/1"))
        self.assertEqual(
            unquotable_reason(
                (("signal", "read the transcript", "https://chat.openai.com/c/abc"),)
            ),
            "model_in_frame",
        )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "follow the README to run the demo",
            "star the repo after you try it",
            "Unlike Loki, this scores briefs locally",
            "prompt the operator with a brief, not a chat",
            "an AI-powered local tick",
            "GPT tokenizer stays local",
            "Claude Shannon entropy on the payload",
            "Gemini protocol on the local host",
            "copilot of the local tick is the operator",
            "bard of the local launch is the README",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_model_in_frame(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_thread_is_numbering_thread_or_storm_not_a_serial(self) -> None:
        serials = (
            "1/7 local tick scores briefs",
            "1/n local tick scores briefs",
            "2 / n: local tick",
            "thread: local tick scores briefs",
            "a launch thread for the local tick",
            "tweetstorm about the local tick",
            "tweet-storm of the local tick",
            "storm of posts about the local tick",
            "wątek 1 o lokalnym ticku",
            "watek o lokalnym ticku",
            "🧵 local tick scores briefs",
        )
        for text in serials:
            with self.subTest(text=text):
                self.assertTrue(looks_like_thread(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "thread",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "thread-safe local tick",
            "pthread pool for the local tick",
            "multithreaded local tick",
            "main thread stays free",
            "24/7 local tick",
            "hook in 1-3s: brief in, draft out",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_thread(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_ranking_dump_is_hn_front_star_counter_or_vanity_chart(self) -> None:
        dumps = (
            "HN front for the local tick",
            "hacker news front page",
            "front page of HN",
            "on the HN front",
            "top on Hacker News",
            "#1 on HN",
            "star count in the README",
            "star-counter in the corner",
            "stars in the corner",
            "licznik gwiazdek",
            "gwiazdki w kącie",
            "zrzut rankingu",
            "ranking dump of the local tick",
            "wykres próżności",
            "vanity chart",
            "stargazers this week",
        )
        for text in dumps:
            with self.subTest(text=text):
                self.assertTrue(looks_like_ranking_dump(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "ranking_not_an_artifact",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "star the repo after you try it",
            "product dashboard for the local tick",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_ranking_dump(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_hashtag_wall_is_a_tag_dump_not_one_inline_tag(self) -> None:
        walls = (
            "#buildinpublic #saas #ai",
            "Local tick scores briefs #buildinpublic #saas #indiehackers",
            "Local tick scores briefs\n#buildinpublic #saas",
            "#buildinpublic",
        )
        for text in walls:
            with self.subTest(text=text):
                self.assertTrue(looks_like_hashtag_wall(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "hashtag_wall",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Local tick scores briefs #buildinpublic",
            "Unlike Loki, this scores briefs locally #buildinpublic",
            "Merged PR #190: Treat GitHub repo root as a ship artifact",
            f"A stranger asked on {FEEDBACK_COMMENT}",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_hashtag_wall(text))

    def test_person_mention_is_a_summon_not_a_url_or_email(self) -> None:
        summons = (
            "@alice try this local tick",
            "cc @bob on the Windows install",
            "thanks @pg",
            "(@cara) the timeout looks like success",
        )
        for text in summons:
            with self.subTest(text=text):
                self.assertTrue(looks_like_person_mention(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "person_mention",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "hello@example.com is the support inbox",
            f"read the writeup at https://medium.com/@someone/we-shipped-a-thing-abc123",
            "Merged PR #190: Treat GitHub repo root as a ship artifact",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_person_mention(text))
        self.assertEqual(
            strip_person_mentions("@bob: the Windows install fails"),
            "the Windows install fails",
        )
        self.assertEqual(
            strip_person_mentions("cc @alice on this"),
            "cc on this",
        )
        self.assertIn(
            "https://medium.com/@someone/we-shipped-a-thing-abc123",
            strip_person_mentions(
                "read https://medium.com/@someone/we-shipped-a-thing-abc123"
            ),
        )
        self.assertIsNone(
            unquotable_reason(
                (
                    ("issue_comment", "@bob: the Windows install fails", FEEDBACK_COMMENT),
                    ("signal", 'A stranger said "the Windows install fails"', SHIP_PR),
                )
            )
        )

    def test_world_commentary_is_headlines_not_a_product(self) -> None:
        takes = (
            "hot take on today's headlines",
            "my take on the election",
            "thoughts on the news of the day",
            "breaking news: markets opened red",
            "political brief without a ship",
            "cultural brief: awards night",
            "news of the day, no repo",
            "komentarz świata: wybory",
            "brief polityczny bez artefaktu",
            "brief kulturalny: festiwal",
            "news dnia bez repo",
            "felieton o polityce dnia",
            "https://www.nytimes.com/2026/08/14/world/europe.html",
            "https://tvn24.pl/polska/wybory a take",
        )
        for text in takes:
            with self.subTest(text=text):
                self.assertTrue(looks_like_world_commentary(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "world_commentary",
                )
        self.assertTrue(is_news_host_url("https://www.bbc.com/news/world-123"))
        self.assertTrue(is_news_host_url("https://www.nytimes.com/2026/08/14/world.html"))
        self.assertTrue(is_news_host_url("https://tvn24.pl/polska/wybory"))
        self.assertFalse(is_news_host_url(SHIP_PR))
        self.assertFalse(is_news_host_url("https://example.com/nytimes"))
        self.assertFalse(is_news_host_url("https://nytimes.com.evil.com/world"))
        self.assertEqual(
            unquotable_reason(
                (("signal", "read the clipping", "https://www.reuters.com/world/"),)
            ),
            "world_commentary",
        )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "newsletter cadence stays weekly",
            "Show HN: local tick scores briefs",
            "star the repo after you try it",
            "Unlike Loki, this scores briefs locally",
            "my take on the timeout bug",
            "hot take: dry-run stays default",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_world_commentary(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_hire_fundraise_is_not_a_product(self) -> None:
        notices = (
            "we're hiring a CMO",
            "we are hiring engineers",
            "hiring for a founding engineer",
            "join our team",
            "open roles on the product team",
            "job board is live",
            "now hiring",
            "we are raising a seed round",
            "fundraise: series A",
            "closed our seed round",
            "announcing our series A",
            "team offsite next week",
            "rekrutacja na CMO",
            "szukamy osoby do produktu",
            "otwarte stanowisko: engineer",
            "tablica ogłoszeń",
            "runda seed zamknięta",
            "wyjazd zespołu w góry",
        )
        for text in notices:
            with self.subTest(text=text):
                self.assertTrue(looks_like_hire_fundraise(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "hire_fundraise",
                )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "star the repo after you try it",
            "Unlike Loki, this scores briefs locally",
            "job application form validates a resume",
            "funding README explains how the grant is spent",
            "hire the local tick to score briefs",
            "round-trip the draft through dress",
            "seed the ICP graph with two-line adds",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_hire_fundraise(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_login_gate_is_not_tryable(self) -> None:
        gated = (
            "behind a login",
            "behind an authentication wall",
            "login required",
            "sign in to continue",
            "log in to try",
            "create an account to access",
            "HEAD 401",
            "GET 403",
            "401/403",
            "401 unauthorized",
            "403 forbidden",
            "za logowaniem",
            "wymaga logowania",
            "bramka logowania",
        )
        for text in gated:
            with self.subTest(text=text):
                self.assertTrue(looks_like_login_gate(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "login form validates a password",
            "sign-in page is a product feature",
            "auth token refresh stays local",
            "must account for the timeout",
            "HTTP 200 on the demo",
            "404 is a dead link, not this gate",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_login_gate(text))

    def test_issues_disabled_is_not_a_camp(self) -> None:
        closed = (
            "hasIssuesEnabled: false",
            "has_issues: false",
            "issues: disabled",
            "issues disabled",
            "issues are disabled",
            "issue tracker is off",
            "disabled issues",
            "turned off the issues",
            "no issue tracker",
            "without an issue tracker",
            "repo z wylaczonymi issues",
            "repo z wyłączonymi issues",
            "wylaczone issues",
            "wyłączone issues",
            "issues wylaczone",
            "issues wyłączone",
        )
        for text in closed:
            with self.subTest(text=text):
                self.assertTrue(looks_like_issues_disabled(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "open issues on the tracker",
            "fixes three issues in the README",
            "no issues with the install",
            "without issues in the install",
            "issues are open",
            "hasIssuesEnabled: true",
            "has_issues: true",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_issues_disabled(text))

    def test_fork_is_not_a_website(self) -> None:
        copies = (
            "isFork: true",
            "is_fork: true",
            "fork: true",
            "this repo is a fork",
            "this repository is a fork",
            "forked from other/tool",
            "forked this repo",
            "a fork of github.com/other/tool",
            "upstream is github.com/other/tool",
            "parentRepository: other/tool",
            "parent: other/tool",
            "to jest fork",
            "fork nie jest witryna",
            "kopia repo",
        )
        for text in copies:
            with self.subTest(text=text):
                self.assertTrue(looks_like_fork(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "isFork: false",
            "is_fork: false",
            "fork the process on each tick",
            "we do not fork the worker",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_fork(text))

    def test_archived_repo_is_dead_not_a_museum(self) -> None:
        tombs = (
            "isArchived: true",
            "is_archived: true",
            "isDisabled: true",
            "is_disabled: true",
            "this repo is archived",
            "this repository is disabled",
            "archived github repo",
            "disabled repo",
            "repo is archived",
            "zarchiwizowane repo",
            "martwe repo",
            "nie launchujemy muzeum",
        )
        for text in tombs:
            with self.subTest(text=text):
                self.assertTrue(looks_like_archived_repo(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "isArchived: false",
            "is_archived: false",
            "isDisabled: false",
            "we archive old logs each night",
            "disabled feature flag stays off",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_archived_repo(text))

    def test_private_repo_is_not_a_website(self) -> None:
        locks = (
            "isPrivate: true",
            "is_private: true",
            "visibility: private",
            "this repo is private",
            "this repository is private",
            "private github repo",
            "private repo",
            "repo is private",
            "prywatne repo",
        )
        for text in locks:
            with self.subTest(text=text):
                self.assertTrue(looks_like_private_repo(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "isPrivate: false",
            "is_private: false",
            "visibility: public",
            "privacy-first local operator",
            "private keys stay on the machine",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_private_repo(text))

    def test_empty_repo_is_not_a_website(self) -> None:
        blanks = (
            "isEmpty: true",
            "is_empty: true",
            "this repo is empty",
            "this repository is empty",
            "empty git tree",
            "empty tree",
            "no default branch",
            "without a default branch",
            "no README",
            "no README file",
            "without a README",
            "missing README",
            "brak drzewa",
            "brak README",
            "bez README",
            "puste repo",
            "nie ma witryny",
            "nie ma nawet kartki",
            "diskUsage: 0",
            "disk_usage: 0",
        )
        for text in blanks:
            with self.subTest(text=text):
                self.assertTrue(looks_like_empty_repo(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "isEmpty: false",
            "is_empty: false",
            "README without a GIF",
            "README one-liner \u2192 GIF \u2192 working quickstart",
            "typo in README",
            "no GIF in the README",
            "empty feed is not this gate",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_empty_repo(text))

    def test_server_splash_is_not_a_product(self) -> None:
        splashes = (
            "Welcome to nginx",
            "nginx default page",
            "nginx welcome page",
            "It works! This is the default web page for this server",
            "Apache2 Debian Default Page",
            "Apache2 Ubuntu Default Page",
            "Apache default page",
            "Apache HTTP Server Test Page",
            "Test Page for the Apache HTTP Server",
            "This page is used to test the proper operation of the Apache",
            "If you see this page, the nginx web server is successfully installed",
            "Caddy default page",
            "Caddy placeholder page",
            "Caddy works!",
            "Congratulations, Caddy is working",
            "server splash",
            "splash serwera",
            "domyslna strona serwera",
            "domyślna strona serwera",
            "strona domyslna serwera",
        )
        for text in splashes:
            with self.subTest(text=text):
                self.assertTrue(looks_like_server_splash(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "nginx reverse proxy fronts the demo",
            "Apache config for the product site",
            "Caddyfile serves the working demo",
            "welcome to the operator",
            "default branch is main",
            "parked domain is a different gate",
            "HTTP 200 on the demo",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_server_splash(text))

    def test_bot_bump_week_is_not_a_story(self) -> None:
        bots = (
            "Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
            "Merged PR #4: chore(deps): update dependency by renovate[bot]",
            "Merged PR #5: bump actions/checkout from 4 to 5 by github-actions[bot]",
            "dependabot",
            "renovate[bot]",
            "github-actions[bot]",
            "author dependabot",
        )
        for text in bots:
            with self.subTest(text=text):
                self.assertTrue(looks_like_bot_author(text))
        diffs = (
            "bump lodash from 4.17.20 to 4.17.21",
            "chore(deps): bump requests from 2.31.0 to 2.32.0",
            "Released v1.2.3",
            "Tag v0.4.0",
            "version diff",
            "diffy wersji",
            "tydzień samych bump",
        )
        for text in diffs:
            with self.subTest(text=text):
                self.assertTrue(looks_like_version_diff(text))
        self.assertTrue(
            looks_like_bot_bump_week(
                (
                    "Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
                    "Merged PR #4: chore(deps): update lockfile by renovate[bot]",
                    "README has an install/quickstart a stranger can run",
                )
            )
        )
        self.assertTrue(
            looks_like_bot_bump_week(
                (
                    "Released v1.2.3",
                    "Merged PR #9: bump actions/checkout from 4 to 5 by github-actions[bot]",
                )
            )
        )
        self.assertTrue(looks_like_bot_bump_week(("Released v1.2.3", "Tag v1.2.3")))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "a stranger can bump the local score",
            "from 1 to 3 facts in the brief",
            "Released the operator that scores briefs",
            "Tag the draft after a human pass",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_bot_author(text))
                self.assertFalse(looks_like_version_diff(text))
        self.assertFalse(
            looks_like_bot_bump_week(
                (
                    "Merged PR #12: feat: local HoM operator scores briefs",
                    "Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
                )
            )
        )
        self.assertFalse(looks_like_bot_bump_week(("dependabot",)))

    def test_weekly_update_without_history_is_not_a_story(self) -> None:
        recaps = (
            "weekly update",
            "Weekly recap",
            "week in review",
            "this week's update",
            "aktualizacja tygodniowa",
            "podsumowanie tygodnia",
            "tygodniowy recap",
        )
        for text in recaps:
            with self.subTest(text=text):
                self.assertTrue(looks_like_weekly_update(text))
        self.assertFalse(looks_like_weekly_update("newsletter cadence stays weekly"))
        self.assertFalse(
            has_monday_history(
                tryable=False,
                artifact_urls=(),
                facts=(("signal", "weekly update", None),),
            )
        )
        self.assertTrue(
            looks_like_monday_without_history(
                story_kind=StoryKind.MAJOR,
                tryable=False,
                facts=(("signal", "weekly update", None),),
                blob="weekly update",
            )
        )
        self.assertFalse(
            looks_like_monday_without_history(
                story_kind=StoryKind.MAJOR,
                tryable=True,
                artifact_urls=(SHIP_PR,),
                facts=(("signal", "Local tick scores briefs", SHIP_PR),),
            )
        )
        self.assertTrue(
            looks_like_monday_without_history(
                preferred_arena=ArenaId.NEWSLETTER,
                tryable=False,
                facts=(("signal", "nothing shipped this week", None),),
            )
        )
        excerpt = ("issue_comment", "@bob: the Windows install fails", FEEDBACK_COMMENT)
        self.assertTrue(has_real_feedback((excerpt,)))
        self.assertFalse(
            looks_like_monday_without_history(
                story_kind=StoryKind.MAJOR,
                tryable=False,
                facts=(excerpt,),
            )
        )

    def test_dead_link_is_not_tryable(self) -> None:
        corpses = (
            "HEAD 404",
            "GET 410",
            "HEAD/GET 404",
            "404/410",
            "404 not found",
            "410 gone",
            "dead link",
            "martwy link",
            "HEAD timeout",
            "GET timeout",
        )
        for text in corpses:
            with self.subTest(text=text):
                self.assertTrue(looks_like_dead_link(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "HTTP 200 on the demo",
            "HEAD 401",
            "GET 403",
            "401/403",
            "behind a login",
            "asset on the list 404",
            "release asset is 404",
            "martwy plik",
            "the timeout fires too soon",
            "download the tarball from the release",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_dead_link(text))

    def test_dead_release_asset_is_not_a_ship(self) -> None:
        corpses = (
            "asset on the list 404",
            "asset on the release list 410",
            "file on the list gone",
            "plik na liscie 404",
            "plik na liście 410",
            "release asset is 404",
            "release asset returned 410",
            "404 on the release asset",
            "410 for the download",
            "browser_download_url 404",
            "dead release asset",
            "dead asset",
            "martwy plik",
            "pobranie 404",
            "pobranie 410",
        )
        for text in corpses:
            with self.subTest(text=text):
                self.assertTrue(looks_like_dead_release_asset(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "404 is a dead link, not this gate",
            "HEAD 404",
            "GET 410",
            "404/410",
            "HEAD 401",
            "GET 403",
            "401/403",
            "behind a login",
            "HTTP 200 on the demo",
            "release notes list the binary",
            "asset list is complete",
            "download the tarball from the release",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_dead_release_asset(text))

    def test_roadmap_is_a_calendar_not_a_ship(self) -> None:
        vapor = (
            "coming Q3",
            "Coming in Q4",
            "coming this quarter",
            "coming next year",
            "coming 2027",
            "soon",
            "shipping soon",
            "on the roadmap",
            "planned for Q2",
            "na roadmapie",
            "w roadmapie",
            "na mapie drogowej",
            "wkrotce",
            "wkrótce",
            "planowane na Q3",
        )
        for text in vapor:
            with self.subTest(text=text):
                self.assertTrue(looks_like_roadmap(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "as soon as you install, the local tick scores",
            "the timeout fires too soon",
            "soon after install the local tick scores",
            "roadmap.md lists shipped gates",
            "the product roadmap page is a changelog",
            "soon-to-be-deleted cache is gone after install",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_roadmap(text))

    def test_draft_and_prerelease_are_not_a_ship(self) -> None:
        vapor = (
            "isDraft: true",
            "is_draft: true",
            "isPrerelease: true",
            "is_prerelease: true",
            "draft release",
            "release is a draft",
            "unpublished github release",
            "github draft",
            "prerelease",
            "pre-release",
            "pre release",
            "release candidate",
            "public beta",
            "closed beta",
            "open beta",
            "rc release",
            "beta release",
            "alpha release",
            "v1.2.3-rc.1",
            "v0.1.0-beta",
            "1.0.0-rc1",
            "v2.0.0-alpha.2",
            "v1.0.0-pre",
            "rc-1",
            "beta-2",
            "https://github.com/mikolaj92/influenzer/releases/tag/v1.0.0-rc.1",
            "wydanie robocze",
            "wydanie szkic",
            "wydanie wstępne",
            "przedpremiera",
            "szkic wydania",
        )
        for text in vapor:
            with self.subTest(text=text):
                self.assertTrue(looks_like_prerelease(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "as soon as you install, the local tick scores",
            "the product draft is the wearable copy",
            "Tag the draft after a human pass",
            "Released v1.2.3",
            "Released v0.1.0",
            "HTTP 200 on the demo",
            "see us on BetaList",
            "operator emits drafts",
            "join the waitlist",
            "coming Q3",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_prerelease(text))

    def test_pending_or_yellow_ci_is_not_green(self) -> None:
        vapor = (
            "CI is pending",
            "checks are pending",
            "pending CI",
            "yellow CI",
            "pending or yellow CI",
            "workflow is in progress",
            "checks queued",
            "statusCheckRollup: PENDING",
            "check-run: in_progress",
            "CI jeszcze wisi",
            "CI w toku",
            "żółte CI",
            "oczekujące checki",
        )
        for text in vapor:
            with self.subTest(text=text):
                self.assertTrue(looks_like_pending_ci(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "pending brief",
            "status: pending",
            "Released v1.2.3",
            "CI passed",
            "checks succeeded",
            "CI failed",
            "red CI",
            "checks failed",
            "join the waitlist",
            "coming Q3",
            "github-actions bumps is not a story",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_pending_ci(text))

    def test_failed_or_red_ci_is_not_tryable(self) -> None:
        broken = (
            "CI failed",
            "checks failed",
            "failed CI",
            "red CI",
            "red or failed CI",
            "workflow is failing",
            "statusCheckRollup: FAILURE",
            "check-run: failure",
            "default branch is red",
            "main is failed",
            "czerwone CI",
            "padnięte checki",
            "CI padło",
        )
        for text in broken:
            with self.subTest(text=text):
                self.assertTrue(looks_like_failed_ci(text))
                self.assertFalse(looks_like_pending_ci(text))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "failed brief",
            "status: failed",
            "Released v1.2.3",
            "CI passed",
            "checks succeeded",
            "CI is pending",
            "yellow CI",
            "join the waitlist",
            "coming Q3",
            "github-actions bumps is not a story",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_failed_ci(text))

    def test_source_available_plus_open_source_is_a_license_lie(self) -> None:
        lies = (
            "BUSL open source",
            "Business Source License, open-source release",
            "Commons Clause FOSS",
            "fair code OSS",
            "fair-code open source",
            "SSPL open source",
            "Server Side Public License is open source",
            "source-available open source",
            "source available license, otwarte oprogramowanie",
        )
        for text in lies:
            with self.subTest(text=text):
                self.assertTrue(looks_like_source_available_license(text))
                self.assertTrue(looks_like_source_available_as_oss(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "source_available_not_oss",
                )
        honest = (
            "source-available",
            "BUSL",
            "Business Source License",
            "Commons Clause",
            "fair code",
            "SSPL",
            "Server Side Public License",
            "source available license",
            "not open source, BUSL",
            "to nie OSS, source-available",
        )
        for text in honest:
            with self.subTest(text=text):
                self.assertTrue(looks_like_source_available_license(text))
                self.assertFalse(looks_like_source_available_as_oss(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Show HN: local tick scores briefs",
            "open source",
            "MIT License — open source",
            "source available on GitHub",
            "not BUSL, this is open source",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_source_available_as_oss(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))

    def test_private_conversation_is_slack_mail_or_dm_not_a_public_issue(self) -> None:
        dumps = (
            "Slack dump: a stranger said the Windows install fails",
            "from Slack: the timeout looks like success",
            "in an anonymized Slack thread a user said the install fails",
            "zrzut Slacka: timeout wygląda jak sukces",
            "from an email: the Windows install fails",
            "email dump of a user saying the install fails",
            "zrzut maila: Windows install fails",
            "From: anon@example.com\nThe Windows install fails",
            "in a DM a user said the Windows install fails",
            "direct message: the timeout looks like success",
            "zrzut DMa: timeout wygląda jak sukces",
            "prywatna rozmowa: timeout wygląda jak sukces",
            "in an anonymized DM a user said the install fails",
            "https://acme.slack.com/archives/C123/p123 a user said the install fails",
            "https://mail.google.com/mail/u/0/#inbox/FMfc a user said the install fails",
        )
        for text in dumps:
            with self.subTest(text=text):
                self.assertTrue(looks_like_private_conversation(text))
                self.assertEqual(
                    unquotable_reason((("signal", text, SHIP_PR),)),
                    "private_conversation",
                )
        self.assertEqual(
            unquotable_reason(
                (("excerpt", '"the Windows install fails"', "https://acme.slack.com/archives/C123/p1"),)
            ),
            "private_conversation",
        )
        self.assertEqual(
            unquotable_reason(
                (("excerpt", '"the Windows install fails"', "https://mail.google.com/mail/u/0/#inbox/FMfc"),)
            ),
            "private_conversation",
        )
        self.assertEqual(
            unquotable_reason(
                (("excerpt", '"the Windows install fails"', "https://example.com/blog/windows-install"),)
            ),
            "quote_without_excerpt",
        )
        allowed = (
            "Local tick scores briefs and emits a draft",
            "Windows install fails with a traceback",
            "Slack integration posts the draft to a workspace",
            "email notifications stay off until a human passes",
            "hello@example.com is the support inbox",
            "demo of the local tick",
        )
        for text in allowed:
            with self.subTest(text=text):
                self.assertFalse(looks_like_private_conversation(text))
                self.assertIsNone(unquotable_reason((("signal", text, SHIP_PR),)))
        self.assertIsNone(
            unquotable_reason(
                (
                    ("issue_comment", "@bob: the Windows install fails", FEEDBACK_COMMENT),
                    ("signal", 'A stranger said "the Windows install fails"', SHIP_PR),
                )
            )
        )


class ScoreBriefTests(unittest.TestCase):
    def _brief(self, **overrides: object) -> Brief:
        facts = overrides.pop("facts", (Fact(text="local tick scores briefs", artifact_url=SHIP_PR),))
        kwargs = dict(
            project_id="app-1",
            brief_id="b1",
            facts=facts,
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        kwargs.update(overrides)
        return Brief.create(**kwargs)  # type: ignore[arg-type]

    def test_empty_facts_are_killed(self) -> None:
        score = score_brief(self._brief(facts=(), claims_ship=False, tryable=False))
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "empty_brief")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(self._brief(facts=()), score))

    def test_patch_stays_changelog_only(self) -> None:
        brief = self._brief(
            story_kind=StoryKind.PATCH,
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="typo in README"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "patch_changelog_only")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)

    def test_ship_without_artifact_is_killed(self) -> None:
        brief = self._brief(
            facts=(Fact(text="we shipped the operator"),),
            claims_ship=True,
            tryable=True,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "ship_claim_missing_artifact")

    def test_repo_root_is_a_ship_artifact_for_hn(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_REPO),
                Fact(text=human),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        self.assertEqual(decision.score.reason, "one_angle")
        assert decision.draft is not None
        self.assertEqual(decision.draft.body, f"Show HN: {human}\n\n{SHIP_REPO}")
        self.assertNotIn("/pull/1", decision.draft.body)

    def test_hype_without_tryable_demo_is_killed(self) -> None:
        brief = self._brief(tryable=False, claims_ship=True)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hype_without_demo")

    def test_hn_without_tryable_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            preferred_arena=ArenaId.HN,
            facts=(Fact(text="thinking about a launch post"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_tryable")

    def test_discord_is_not_a_launch_arena(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena="discord",
            facts=(Fact(text="stand up a Discord"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "discord_pre_pmf")

    def test_living_stack_keeps_github_costume_on_the_next_look(self) -> None:
        brief = self._brief()
        decision = apply_brief(brief, now="2026-08-13T06:00:00Z", stack_arena=ArenaId.GITHUB)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.GITHUB)
        assert decision.draft is not None
        self.assertEqual(decision.draft.costume, "workshop")
        self.assertFalse(decision.draft.body.lstrip().startswith("Show HN:"))

    def test_shopping_another_arena_while_the_stack_lives_is_silence(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.X)
        score = score_brief(brief, stack_arena=ArenaId.HN)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, LIVING_STACK_REASON)
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_same_github_or_hn_costume_on_a_living_stack_is_kept(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.HN)
        score = score_brief(brief, stack_arena=ArenaId.HN)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)

    def test_major_tryable_ship_drafts_one_hn_arena(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="Brief in, draft out on each tick", artifact_url=SHIP_PR),
                Fact(text="Dry-run still default"),
                Fact(text="Patches stay changelog-only"),
            )
        )
        decision = apply_brief(brief, now="2026-08-13T05:00:00Z")
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        self.assertEqual(decision.score.reason, "one_angle")
        self.assertIsNotNone(decision.draft)
        assert decision.draft is not None
        self.assertEqual(decision.draft.costume, "seminar")
        self.assertEqual(decision.draft.arena, ArenaId.HN)
        self.assertTrue(decision.draft.body.lstrip().startswith("Show HN:"))
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        self.assertNotIn("One angle:", decision.draft.body)
        self.assertIn(SHIP_PR, decision.draft.body)
        self.assertGreaterEqual(len(decision.draft.wave_checklist), 3)
        self.assertNotIn("linkedin", decision.draft.body.lower().split("show hn:", 1)[0])

    def test_preferred_x_uses_agora_costume_not_hn(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.X)
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.arena, ArenaId.X)
        self.assertEqual(decision.draft.costume, "agora")
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        first = decision.draft.body.splitlines()[0]
        self.assertTrue(first.strip())
        self.assertNotIn("http", first.lower())
        self.assertLess(len(decision.draft.body), 500)
        self.assertIn(SHIP_PR, decision.draft.body)

    def test_default_without_tryable_is_changelog_not_a_social_draft(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.EXPLORATION,
            facts=(Fact(text="explored adapter dry-run envelopes"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "exploration_not_a_post")
        self.assertIsNone(decision.draft)

    def test_decision_without_user_facing_change_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.DECISION,
            facts=(Fact(text="we picked SQLite over a hosted store"),),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "decision_not_user_facing")
        self.assertIsNone(decision.draft)

    def test_merged_pr_stack_is_changelog_not_show_hn(self) -> None:
        brief = self._brief(
            facts=(
                Fact(
                    text="Merged PR #190: Treat GitHub repo root as a ship artifact",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/190",
                ),
                Fact(
                    text="Merged PR #187: feat: prior operator look",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/187",
                ),
                Fact(
                    text="Merged PR #22: feat(hom): local tick scores briefs",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/22",
                ),
                Fact(text="README has an install/quickstart a stranger can run"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "merge_log_changelog")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)
        self.assertIsNone(compose_draft(brief, decision.score))

    def test_commit_noise_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.MAJOR,
            facts=(Fact(text="chore: bump deps"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "commit_noise_changelog")
        self.assertIsNone(compose_draft(brief, score))

    def test_bot_only_merges_are_changelog_not_a_launch(self) -> None:
        brief = self._brief(
            facts=(
                Fact(
                    text="Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/3",
                ),
                Fact(
                    text="Merged PR #4: chore(deps): update lockfile by renovate[bot]",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/4",
                ),
                Fact(text="README has an install/quickstart a stranger can run"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "bot_bump_week")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)
        self.assertIsNone(compose_draft(brief, decision.score))

    def test_version_diff_release_is_changelog_not_a_launch(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="Released v1.2.3", artifact_url=SHIP_RELEASE),
                Fact(
                    text="Merged PR #9: bump actions/checkout from 4 to 5 by github-actions[bot]",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/9",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "bot_bump_week")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)

    def test_version_tag_with_stale_readme_is_changelog_not_a_launch(self) -> None:
        brief = self._brief(
            facts=(
                Fact(kind="release", text="Released v1.2.3", artifact_url=SHIP_RELEASE),
                Fact(
                    kind="readme",
                    text="README has an install/quickstart a stranger can run",
                    artifact_url="https://github.com/mikolaj92/influenzer#readme",
                ),
                Fact(kind="signal", text="Local operator with a working install"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "bot_bump_week")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)

    def test_human_feat_next_to_a_bot_bump_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(
                    text="Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
                    artifact_url="https://github.com/mikolaj92/influenzer/pull/3",
                ),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_waitlist_ship_claim_is_killed(self) -> None:
        brief = self._brief(
            facts=(Fact(text="join the waitlist, coming soon", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "waitlist_not_tryable")

    def test_shortener_utm_or_click_here_is_not_tryable(self) -> None:
        cases = (
            ("https://bit.ly/try-this", "shortener: bit.ly", "shortener_not_tryable"),
            (
                "https://github.com/mikolaj92/influenzer?utm_source=hn",
                "utm farm on the artifact",
                "utm_farm_not_tryable",
            ),
            (SHIP_PR, "kliknij tu", "click_here_not_tryable"),
        )
        for url, text, reason in cases:
            with self.subTest(reason=reason):
                brief = self._brief(
                    facts=(
                        Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                        Fact(text=text, artifact_url=url),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, reason)
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

        quiet = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="kliknij tu", artifact_url=SHIP_PR),),
        )
        score = score_brief(quiet)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "click_here_not_tryable")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(quiet, score))

    def test_login_gate_ship_claim_is_killed(self) -> None:
        gated = (
            "behind a login",
            "HEAD 401",
            "GET 403",
            "za logowaniem",
            "wymaga logowania",
        )
        for text in gated:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "login_gate_not_tryable")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_login_gate_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="behind a login", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "login_gate_not_tryable")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_login_gate_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="login form validates a password"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_issues_disabled_social_arena_is_killed(self) -> None:
        closed = (
            "issues disabled",
            "hasIssuesEnabled: false",
            "repo z wyłączonymi issues",
            "no issue tracker",
        )
        for text in closed:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "issues_disabled_no_camp")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_issues_disabled_without_social_arena_is_readme_not_show_hn(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="issues disabled", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.GITHUB)
        draft = compose_draft(brief, score)
        self.assertIsNotNone(draft)
        assert draft is not None
        self.assertFalse(draft.body.startswith("Show HN:"))
        self.assertIn("## Quickstart", draft.body)

    def test_fork_is_killed_even_when_owner_is_ours(self) -> None:
        copies = (
            "isFork: true",
            "this repo is a fork",
            "forked from other/tool",
            "to jest fork",
        )
        for text in copies:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "fork_not_a_site")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_archived_repo_is_killed_even_when_a_release_exists(self) -> None:
        tombs = (
            "isArchived: true",
            "this repo is archived",
            "isDisabled: true",
            "nie launchujemy muzeum",
        )
        for text in tombs:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "archived_repo")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_private_repo_is_killed_even_when_owner_is_ours(self) -> None:
        locks = (
            "isPrivate: true",
            "this repo is private",
            "visibility: private",
            "prywatne repo",
        )
        for text in locks:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "private_repo")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_empty_repo_is_killed_even_when_a_release_exists(self) -> None:
        blanks = (
            "isEmpty: true",
            "this repo is empty",
            "no README",
            "puste repo",
        )
        for text in blanks:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "empty_repo_not_a_site")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_server_splash_is_killed_even_when_a_release_exists(self) -> None:
        splashes = (
            "Welcome to nginx",
            "Apache2 Debian Default Page",
            "Caddy placeholder page",
            "domyślna strona serwera",
        )
        for text in splashes:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.GITHUB,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "server_splash_not_a_product")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_server_splash_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="nginx reverse proxy fronts the demo"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_product_copy_without_archived_repo_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="we archive old logs each night"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_product_copy_without_private_repo_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="privacy-first local operator"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_product_copy_without_empty_repo_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="README without a GIF is a different gate"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_product_copy_without_fork_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="we do not fork the worker"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_product_copy_without_issues_disabled_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="no issues with the install"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_dead_link_ship_claim_is_killed(self) -> None:
        corpses = (
            "HEAD 404",
            "GET 410",
            "dead link",
            "martwy link",
            "HEAD timeout",
        )
        for text in corpses:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "dead_link_not_tryable")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_dead_link_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="HEAD 404", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "dead_link_not_tryable")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_dead_link_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="HTTP 200 on the demo"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_dead_release_asset_ship_claim_is_killed(self) -> None:
        corpses = (
            "asset on the list 404",
            "release asset is 404",
            "browser_download_url 410",
            "martwy plik",
            "pobranie 404",
        )
        for text in corpses:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_RELEASE),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "dead_release_asset")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_dead_release_asset_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="asset on the list 404", artifact_url=SHIP_RELEASE),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "dead_release_asset")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_dead_release_asset_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="download the tarball from the release"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_roadmap_ship_claim_is_killed(self) -> None:
        vapor = (
            "coming Q3",
            "on the roadmap",
            "shipping soon",
            "na roadmapie",
            "wkrótce",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "roadmap_not_a_ship")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_roadmap_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="coming Q3", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "roadmap_not_a_ship")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_roadmap_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="as soon as you install, the local tick scores"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_prerelease_ship_claim_is_killed(self) -> None:
        vapor = (
            "draft release",
            "isPrerelease: true",
            "v1.2.3-rc.1",
            "public beta",
            "wydanie robocze",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "prerelease_not_a_ship")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_prerelease_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="v1.2.3-rc.1", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "prerelease_not_a_ship")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_prerelease_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="Released v1.2.3"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_pending_ci_ship_claim_is_killed(self) -> None:
        vapor = (
            "CI is pending",
            "yellow CI",
            "statusCheckRollup: PENDING",
            "żółte CI",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "pending_ci_unknown")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_pending_ci_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="checks are pending", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "pending_ci_unknown")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_pending_ci_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="CI passed"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_failed_ci_ship_claim_is_killed(self) -> None:
        broken = (
            "CI failed",
            "red CI",
            "statusCheckRollup: FAILURE",
            "czerwone CI",
        )
        for text in broken:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "failed_ci_not_tryable")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_failed_ci_without_ship_claim_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="checks failed", artifact_url=SHIP_PR),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "failed_ci_not_tryable")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_failed_ci_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="CI passed"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_superlative_without_tryable_artifact_is_killed(self) -> None:
        slogans = (
            "revolutionary local tick",
            "the world's first local tick",
            "an AI-powered local tick",
        )
        for text in slogans:
            with self.subTest(text=text):
                brief = self._brief(
                    claims_ship=False,
                    tryable=False,
                    facts=(Fact(text=text),),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "superlative_without_proof")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_superlative_with_artifact_but_not_tryable_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            facts=(
                Fact(text="an AI-powered local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "superlative_without_proof")
        self.assertIsNone(compose_draft(brief, score))

    def test_reply_under_someone_elses_post_is_killed(self) -> None:
        parent = "https://x.com/other/status/123456789"
        cases = (
            (Fact(kind="parent", text="rising mid-KOL post", artifact_url=parent),),
            (Fact(text="reply under a rising thread", artifact_url=parent),),
            (Fact(text="pod postem o launchu", artifact_url=parent),),
        )
        for extra in cases:
            with self.subTest(text=extra[0].text):
                brief = self._brief(
                    facts=(
                        *extra,
                        Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "foreign_wave")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_parent_url_alone_is_not_enough(self) -> None:
        for url in ("https://x.com/other/status/1", SHIP_ISSUE):
            with self.subTest(url=url):
                brief = self._brief(
                    facts=(Fact(kind="parent", text="a parent URL alone", artifact_url=url),)
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "foreign_wave")
                self.assertIsNone(compose_draft(brief, score))

    def test_reply_under_our_ship_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.X,
            facts=(
                Fact(
                    kind="parent",
                    text="Show HN about mikolaj92/influenzer",
                    artifact_url="https://news.ycombinator.com/item?id=1",
                ),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.X)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_dunking_another_project_is_killed(self) -> None:
        dunks = (
            "Loki sucks, use this local tick instead",
            "their project is trash",
            "dunking on Loki with a local tick",
        )
        for text in dunks:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "dunking")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_engagement_bait_is_killed(self) -> None:
        bait = (
            "Agree?",
            "like if this helped",
            "comment one word",
            "Local tick scores briefs \u2193",
        )
        for text in bait:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "engagement_bait")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_contest_is_killed(self) -> None:
        contests = (
            "giveaway of the local tick",
            "raffle for a seat",
            "RT to win a license",
            "nagroda za follow",
        )
        for text in contests:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "contest")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_model_in_frame_is_killed(self) -> None:
        dumps = (
            "I asked ChatGPT how to score a brief",
            "as an AI I would ship the local tick",
            "here's the prompt I used for the launch",
            "zrzut rozmowy z modelem",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "model_in_frame")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_thread_serial_is_killed(self) -> None:
        serials = (
            "1/7 local tick scores briefs",
            "1/n local tick scores briefs",
            "a launch thread for the local tick",
            "tweetstorm about the local tick",
        )
        for text in serials:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "thread")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_ranking_dump_is_killed(self) -> None:
        dumps = (
            "HN front for the local tick",
            "stars in the corner",
            "zrzut rankingu",
            "vanity chart",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "ranking_not_an_artifact")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_hashtag_wall_is_killed(self) -> None:
        walls = (
            "#buildinpublic #saas #ai",
            "Local tick scores briefs #buildinpublic #saas #indiehackers",
            "Local tick scores briefs\n#buildinpublic #saas",
        )
        for text in walls:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hashtag_wall")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_one_inline_hashtag_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs #buildinpublic", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn("#buildinpublic", decision.draft.body)

    def test_naming_a_predecessor_or_offering_help_can_still_draft(self) -> None:
        allowed = (
            "Unlike Loki, this scores briefs locally",
            "Loki is the predecessor; the difference is a local tick",
            "Loki is worth helping with a local tick",
        )
        for text in allowed:
            with self.subTest(text=text):
                brief = self._brief(
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                decision = apply_brief(brief)
                self.assertEqual(decision.score.verdict, Verdict.DRAFT)
                self.assertEqual(decision.score.arena, ArenaId.HN)
                assert decision.draft is not None
                self.assertTrue(decision.draft.body.startswith("Show HN:"))
                self.assertIn("Loki", decision.draft.body)

    def test_superlative_with_tryable_artifact_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="an AI-powered local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_PR, decision.draft.body)

    def test_press_release_tone_on_hn_is_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="we are excited to announce a game-changer", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "press_release_tone")
        self.assertIsNone(compose_draft(brief, score))

    def test_quote_without_excerpt_url_is_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text='users said "this is great"', artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "quote_without_excerpt")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_users_love_without_excerpt_is_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="users love the local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "invented_opinion")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_number_from_brief_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick is 10x faster than the queue", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        assert decision.draft is not None
        self.assertIn("10x", decision.draft.body)

    def test_feedback_question_can_still_draft(self) -> None:
        excerpt = "How do I install this when uv is missing?"
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="issue_comment", text=f"@bob: {excerpt}", artifact_url=FEEDBACK_COMMENT),
                Fact(text=f'A stranger asked "{excerpt}"', artifact_url=SHIP_PR),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertIn(excerpt, decision.draft.body)
        self.assertNotIn("@bob", decision.draft.body)
        self.assertNotIn("Agree?", decision.draft.body)
        self.assertNotIn("like if", decision.draft.body.casefold())

    def test_quote_from_feedback_excerpt_with_url_can_still_draft(self) -> None:
        excerpt = "the Windows install fails with a traceback"
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="issue_comment", text=f"@bob: {excerpt}", artifact_url=FEEDBACK_COMMENT),
                Fact(text=f'A stranger said "{excerpt}"', artifact_url=SHIP_PR),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertIn(excerpt, decision.draft.body)
        self.assertIn(SHIP_PR, decision.draft.body)
        self.assertNotIn("@bob", decision.draft.body)

    def test_operator_mention_is_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(text="@alice try this local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "person_mention")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_private_conversation_is_killed(self) -> None:
        dumps = (
            "Slack dump: a stranger said the Windows install fails",
            "from an email: the Windows install fails",
            "in a DM a user said the Windows install fails",
            "zrzut Slacka, nawet anonimizowany",
            "prywatna rozmowa: timeout wygląda jak sukces",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "private_conversation")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_world_commentary_is_killed(self) -> None:
        takes = (
            "hot take on today's headlines",
            "brief polityczny bez artefaktu",
            "news of the day, no repo",
            "komentarz świata: wybory",
            "https://www.nytimes.com/2026/08/14/world/europe.html",
        )
        for text in takes:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "world_commentary")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_news_url_without_repo_is_killed_even_with_a_ship_claim(self) -> None:
        brief = self._brief(
            facts=(
                Fact(
                    text="read the clipping",
                    artifact_url="https://www.reuters.com/world/europe/",
                ),
                Fact(text="strangers can click the article today"),
            ),
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertIn(score.reason, {"world_commentary", "ship_claim_missing_artifact"})
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_world_commentary_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_hire_fundraise_is_killed(self) -> None:
        notices = (
            "we're hiring a CMO",
            "we are raising a seed round",
            "team offsite next week",
            "rekrutacja na CMO",
            "tablica ogłoszeń",
        )
        for text in notices:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hire_fundraise")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_product_copy_without_hire_fundraise_can_still_draft(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="job application form validates a resume"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.DRAFT)
        self.assertEqual(score.arena, ArenaId.HN)
        self.assertIsNotNone(compose_draft(brief, score))

    def test_source_available_plus_open_source_is_killed(self) -> None:
        lies = (
            "BUSL open source",
            "Commons Clause FOSS",
            "fair code OSS",
            "SSPL open source",
            "source-available open source",
        )
        for text in lies:
            with self.subTest(text=text):
                brief = self._brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                    preferred_arena=ArenaId.HN,
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "source_available_not_oss")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

        brief = self._brief(
            facts=(
                Fact(text="BUSL", artifact_url=SHIP_PR),
                Fact(text="open source"),
                Fact(text="strangers can click and run the demo today"),
            ),
            preferred_arena=ArenaId.HN,
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "source_available_not_oss")
        self.assertIsNone(compose_draft(brief, score))

    def test_source_available_without_oss_sticker_can_still_draft(self) -> None:
        honest = (
            "source-available",
            "BUSL",
            "not open source, BUSL",
            "MIT License — open source",
        )
        for text in honest:
            with self.subTest(text=text):
                brief = self._brief(
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.DRAFT)
                self.assertEqual(score.arena, ArenaId.HN)
                self.assertIsNotNone(compose_draft(brief, score))

    def test_anonymized_slack_excerpt_is_still_killed(self) -> None:
        brief = self._brief(
            facts=(
                Fact(
                    kind="excerpt",
                    text='anon said "the Windows install fails"',
                    artifact_url="https://acme.slack.com/archives/C123/p1",
                ),
                Fact(text="strangers can click and run the demo today", artifact_url=SHIP_PR),
            )
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "private_conversation")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_youtube_without_package_is_killed(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.YOUTUBE)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "cinema_missing_package")

    def test_shorts_without_hook_is_killed(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.SHORTS)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "fair_missing_hook")

    def test_reddit_without_named_room_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            preferred_arena=ArenaId.REDDIT,
            facts=(Fact(text="I struggled with subprocess timeouts looking like success"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "reddit_no_room")

    def test_x_without_tryable_is_killed_not_an_empty_feed_original(self) -> None:
        brief = self._brief(
            tryable=False,
            claims_ship=False,
            preferred_arena=ArenaId.X,
            facts=(Fact(text="thinking about posting a launch reply"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "x_empty_feed")

    def test_bluesky_without_artifact_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            preferred_arena=ArenaId.BLUESKY,
            facts=(Fact(text="vibe posting about the operator"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "bluesky_vibe_without_artifact")

    def test_mastodon_ship_claim_is_killed_as_pr_tone(self) -> None:
        brief = self._brief(preferred_arena=ArenaId.MASTODON)
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "mastodon_pr_tone")

    def test_linkedin_one_fact_is_killed_as_court_not_ready(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.LINKEDIN,
            facts=(Fact(text="shipped"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "court_not_ready")

    def test_hn_without_clickable_url_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.HN,
            facts=(Fact(text="a working demo exists on my laptop"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_tryable")

    def test_http_javascript_data_or_file_url_is_not_tryable(self) -> None:
        almost = (
            "http://github.com/mikolaj92/influenzer",
            "http://github.com/mikolaj92/influenzer/pull/12",
            "javascript:alert(1)",
            "data:text/html,<h1>demo</h1>",
            "file:///tmp/demo.html",
            "https://example.com/demo",
        )
        for url in almost:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="a stranger can almost click this", artifact_url=url),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_tryable")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_youtube_vimeo_or_loom_as_only_url_is_not_show_hn(self) -> None:
        films = (
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "https://youtu.be/dQw4w9WgXcQ",
            "https://vimeo.com/123456789",
            "https://www.loom.com/share/abc123",
        )
        for url in films:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="watch the walkthrough", artifact_url=url),
                        Fact(text="strangers can click the film today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_an_episode")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_film_next_to_repo_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(
                    text="walkthrough film as evidence",
                    artifact_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_REPO, decision.draft.body)
        self.assertNotIn("youtube.com", decision.draft.body)

    def test_app_store_play_or_testflight_as_only_url_is_not_show_hn(self) -> None:
        stores = (
            "https://apps.apple.com/app/id123456789",
            "https://itunes.apple.com/us/app/id123456789",
            "https://play.google.com/store/apps/details?id=com.example.app",
            "https://testflight.apple.com/join/abc123",
        )
        for url in stores:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="download the app", artifact_url=url),
                        Fact(text="strangers can install it today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_a_store")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_download_the_app_pitch_is_not_show_hn(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="download the app from our homepage",
                    artifact_url="https://example.com/demo",
                ),
                Fact(text="strangers can install it today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_a_store")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_store_next_to_repo_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(
                    text="also listed on the store as evidence",
                    artifact_url="https://apps.apple.com/app/id123456789",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_REPO, decision.draft.body)
        self.assertNotIn("apps.apple.com", decision.draft.body)

    def test_medium_substack_devto_or_hashnode_as_only_url_is_not_show_hn(self) -> None:
        blogs = (
            "https://medium.com/@someone/we-shipped-a-thing-abc123",
            "https://someone.medium.com/we-shipped-a-thing-abc123",
            "https://someone.substack.com/p/we-shipped-a-thing",
            "https://dev.to/someone/we-shipped-a-thing",
            "https://someone.hashnode.dev/we-shipped-a-thing",
            "https://hashnode.com/@someone/we-shipped-a-thing",
        )
        for url in blogs:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="read the writeup", artifact_url=url),
                        Fact(text="strangers can click the article today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_a_blog")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_product_hunt_or_betalist_as_only_url_is_not_show_hn(self) -> None:
        boards = (
            "https://www.producthunt.com/posts/local-tick",
            "https://producthunt.com/posts/local-tick",
            "https://www.betalist.com/startups/local-tick",
            "https://betalist.com/startups/local-tick",
        )
        for url in boards:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="see the launch card", artifact_url=url),
                        Fact(text="strangers can click the board today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_an_aggregator")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_launch_on_ph_pitch_is_not_show_hn(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="launch on PH from our homepage",
                    artifact_url="https://example.com/demo",
                ),
                Fact(text="strangers can click the board today"),
            ),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "hn_not_an_aggregator")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_launch_board_next_to_repo_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(
                    text="also listed on the launch board as evidence",
                    artifact_url="https://www.producthunt.com/posts/local-tick",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_REPO, decision.draft.body)
        self.assertNotIn("producthunt.com", decision.draft.body)

    def test_hn_front_star_chart_or_badge_as_only_url_is_not_an_artifact(self) -> None:
        charts = (
            "https://news.ycombinator.com/item?id=123",
            "https://star-history.com/#mikolaj92/influenzer",
            "https://img.shields.io/github/stars/mikolaj92/influenzer",
            "https://github.com/mikolaj92/influenzer/stargazers",
        )
        for url in charts:
            with self.subTest(url=url):
                brief = self._brief(
                    claims_ship=False,
                    tryable=True,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="see the snapshot", artifact_url=url),
                        Fact(text="strangers can click the page today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "ranking_not_an_artifact")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_ranking_chart_next_to_repo_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(
                    text="chart as evidence",
                    artifact_url="https://star-history.com/#mikolaj92/influenzer",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_REPO, decision.draft.body)
        self.assertNotIn("star-history.com", decision.draft.body)

    def test_listicle_or_clickbait_title_is_not_show_hn(self) -> None:
        bait = (
            "7 ways to score briefs",
            "N ways a stranger can try it",
            "you won't believe this local tick",
            "Local tick scores briefs!",
        )
        for title in bait:
            with self.subTest(title=title):
                brief = self._brief(
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_REPO),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "hn_not_a_listicle")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_shouty_caps_title_is_silence_on_hn_and_github(self) -> None:
        title = "LOCAL TICK SCORES BRIEFS AND EMITS A DRAFT"
        for arena in (ArenaId.HN, ArenaId.GITHUB):
            with self.subTest(arena=arena.value):
                brief = self._brief(
                    preferred_arena=arena,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_REPO),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "shouty_title")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_emoji_title_is_silence_on_hn_and_github(self) -> None:
        title = "Local tick scores briefs \U0001f680"
        for arena in (ArenaId.HN, ArenaId.GITHUB):
            with self.subTest(arena=arena.value):
                brief = self._brief(
                    preferred_arena=arena,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_REPO),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                score = score_brief(brief)
                self.assertEqual(score.verdict, Verdict.KILL)
                self.assertEqual(score.reason, "emoji_title")
                self.assertIsNone(score.arena)
                self.assertIsNone(compose_draft(brief, score))

    def test_one_or_two_acronym_words_can_still_be_a_title(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="CLI scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN: CLI scores briefs"))

    def test_curiosity_title_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertFalse(decision.draft.body.splitlines()[0].endswith("!"))
        self.assertNotIn("ways", decision.draft.body.splitlines()[0].lower())

    def test_blog_next_to_repo_can_still_be_show_hn(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_REPO),
                Fact(
                    text="writeup as evidence",
                    artifact_url="https://medium.com/@someone/we-shipped-a-thing-abc123",
                ),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.score.arena, ArenaId.HN)
        assert decision.draft is not None
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_REPO, decision.draft.body)
        self.assertNotIn("medium.com", decision.draft.body)

    def test_hard_issue_defaults_to_github_workshop_not_social(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.HARD_ISSUE,
            facts=(
                Fact(text="I struggled with timeouts looking like success"),
                Fact(text="unknown plus reconcile is the rule now"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.draft.arena, ArenaId.GITHUB)
        self.assertEqual(decision.draft.costume, "workshop")
        self.assertNotIn("Costume:", decision.draft.body)
        self.assertNotIn("One arena:", decision.draft.body)
        self.assertIn("I struggled with timeouts looking like success", decision.draft.body)

    def test_monday_without_history_is_changelog_not_a_recap(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.MAJOR,
            facts=(
                Fact(text="weekly update"),
                Fact(text="newsletter cadence stays weekly"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(decision.score.reason, "monday_without_history")
        self.assertIsNone(decision.score.arena)
        self.assertIsNone(decision.draft)
        self.assertIsNone(compose_draft(brief, decision.score))

    def test_weekly_update_without_history_is_changelog_not_a_letter(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            preferred_arena=ArenaId.NEWSLETTER,
            facts=(Fact(text="weekly update"), Fact(text="nothing shipped this week")),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "monday_without_history")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_monday_without_history_on_social_arena_is_killed(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            preferred_arena=ArenaId.LINKEDIN,
            facts=(Fact(text="weekly update"), Fact(text="nothing shipped this week")),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.KILL)
        self.assertEqual(score.reason, "monday_without_history")
        self.assertIsNone(score.arena)
        self.assertIsNone(compose_draft(brief, score))

    def test_feedback_without_ship_can_still_draft_a_hard_issue(self) -> None:
        excerpt = "How do I install this when uv is missing?"
        brief = self._brief(
            claims_ship=False,
            tryable=False,
            story_kind=StoryKind.HARD_ISSUE,
            facts=(
                Fact(kind="issue_comment", text=f"@bob: {excerpt}", artifact_url=FEEDBACK_COMMENT),
                Fact(text=f"A stranger asked {excerpt}"),
            ),
        )
        decision = apply_brief(brief)
        self.assertEqual(decision.score.verdict, Verdict.DRAFT)
        self.assertEqual(decision.draft.arena, ArenaId.GITHUB)
        assert decision.draft is not None
        self.assertIn(excerpt, decision.draft.body)

    def test_youtube_with_package_drafts_cinema_only(self) -> None:
        brief = self._brief(
            preferred_arena=ArenaId.YOUTUBE,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(kind="package", text="title plus thumb in 0.5s: one-angle operator tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.arena, ArenaId.YOUTUBE)
        self.assertEqual(decision.draft.costume, "cinema")

    def test_thin_x_brief_without_artifact_is_changelog_only(self) -> None:
        brief = self._brief(
            claims_ship=False,
            tryable=True,
            preferred_arena=ArenaId.X,
            facts=(Fact(text="shipped it"),),
        )
        score = score_brief(brief)
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(score.reason, "thin_brief")
        self.assertIsNone(compose_draft(brief, score))

    def test_every_arena_has_a_fail_closed_gate(self) -> None:
        from influenzer.playbook import ARENA_GATES

        self.assertEqual(set(ARENA_GATES), set(ARENAS))
        self.assertTrue(ARENA_GATES[ArenaId.DISCORD].always_kill)
        self.assertNotIn(ArenaId.GITHUB, SOCIAL_ARENAS)

    def test_scoring_is_deterministic(self) -> None:
        brief = self._brief()
        one = score_brief(brief)
        two = score_brief(brief)
        self.assertEqual(one.score_hash, two.score_hash)
        self.assertEqual(one.verdict, two.verdict)
        self.assertEqual(one.arena, two.arena)

    def test_unknown_arena_is_rejected_at_ingest(self) -> None:
        with self.assertRaises(HomError):
            Brief.create(
                project_id="app-1",
                brief_id="b-bad",
                facts=(Fact(text="x"),),
                story_kind=StoryKind.MAJOR,
                preferred_arena="tiktok",
            )

    def test_json_rejects_secret_fields(self) -> None:
        with self.assertRaises(HomError):
            brief_from_mapping(
                {
                    "project_id": "app-1",
                    "brief_id": "b-secret",
                    "story_kind": "major",
                    "facts": [{"text": "nope"}],
                    "token": "should-not-be-here",
                }
            )


class TickBriefPathTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cfg = Config(home=self.home, scheduler_live_enabled=False)
        write_config(self.home / "config.json", self.cfg)
        self.repo = StateRepository(self.home / "state.db", artifact_root=self.home / "artifacts")
        _project(self.repo)

    def tearDown(self) -> None:
        self.repo.close()
        self.tmp.cleanup()

    def test_tick_scores_pending_brief_and_second_tick_is_noop_for_it(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="ship-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["mutated"])
        self.assertFalse(out["operator"]["published"])
        self.assertEqual(out["operator"]["processed"], 1)
        outcome = out["operator"]["outcomes"][0]
        self.assertEqual(outcome["verdict"], "draft")
        self.assertEqual(outcome["arena"], "hn")
        self.assertFalse(outcome["published"])
        self.assertTrue(str(outcome.get("body") or "").startswith("Show HN:"))
        self.assertNotIn("Costume:", str(outcome.get("body") or ""))
        stored = self.repo.get_brief("app-1", "ship-1")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        draft = self.repo.get_operator_draft("app-1", "ship-1")
        assert draft is not None
        self.assertEqual(draft.costume, "seminar")
        self.assertTrue(draft.body.startswith("Show HN:"))
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)
        revision = self.repo.conn.execute(
            "SELECT status, source, kind FROM content_revisions WHERE revision_id=?",
            (draft.draft_id,),
        ).fetchone()
        self.assertEqual(revision["status"], "draft")
        self.assertEqual(revision["source"], "operator")
        self.assertEqual(revision["kind"], "post")

        again = tick(self.repo, self.cfg, due=(), now="2026-08-13T06:00:00Z")
        self.assertEqual(again["status"], "noop")
        self.assertEqual(again["operator"]["processed"], 0)
        drafts = list(self.repo.conn.execute("SELECT draft_id FROM operator_drafts"))
        self.assertEqual(len(drafts), 1)

    def test_next_look_in_a_living_stack_keeps_the_github_or_hn_costume(self) -> None:
        first = Brief.create(
            project_id="app-1",
            brief_id="stack-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        self.repo.save_brief(first)
        first_out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        self.assertEqual(first_out["operator"]["outcomes"][0]["arena"], "github")
        self.assertEqual(self.repo.living_stack_arena("app-1", "2026-08-14T04:59:59Z"), ArenaId.GITHUB)
        self.assertIsNone(self.repo.living_stack_arena("app-1", "2026-08-15T05:00:00Z"))

        next_look = Brief.create(
            project_id="app-1",
            brief_id="stack-2",
            facts=(
                Fact(
                    text="a stranger can click and run the demo from the README",
                    artifact_url=SHIP_PR,
                ),
            ),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(next_look)
        again = tick(self.repo, self.cfg, due=(), now="2026-08-14T04:00:00Z")
        outcome = again["operator"]["outcomes"][0]
        self.assertEqual(outcome["verdict"], "draft")
        self.assertEqual(outcome["arena"], "github")
        second = self.repo.get_operator_draft("app-1", "stack-2")
        assert second is not None
        self.assertEqual(second.arena, ArenaId.GITHUB)
        self.assertEqual(second.costume, "workshop")
        self.assertFalse(second.body.lstrip().startswith("Show HN:"))

        shop = Brief.create(
            project_id="app-1",
            brief_id="stack-3",
            facts=(
                Fact(
                    text="dry-run still default and strangers can try it",
                    artifact_url=SHIP_PR,
                ),
            ),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.X,
        )
        self.repo.save_brief(shop)
        silenced = tick(self.repo, self.cfg, due=(), now="2026-08-14T04:30:00Z")
        shop_out = silenced["operator"]["outcomes"][0]
        self.assertEqual(shop_out["verdict"], "kill")
        self.assertEqual(shop_out["reason"], LIVING_STACK_REASON)
        self.assertIsNone(self.repo.get_operator_draft("app-1", "stack-3"))

        after = Brief.create(
            project_id="app-1",
            brief_id="stack-4",
            facts=(
                Fact(
                    text="local tick scores briefs and emits a tryable draft",
                    artifact_url=SHIP_PR,
                ),
            ),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(after)
        later = tick(self.repo, self.cfg, due=(), now="2026-08-15T05:00:00Z")
        later_out = later["operator"]["outcomes"][0]
        self.assertEqual(later_out["verdict"], "draft")
        self.assertEqual(later_out["arena"], "hn")
        fourth = self.repo.get_operator_draft("app-1", "stack-4")
        assert fourth is not None
        self.assertTrue(fourth.body.startswith("Show HN:"))

    def test_hold_releases_the_stack_so_the_next_look_may_pick_again(self) -> None:
        first = Brief.create(
            project_id="app-1",
            brief_id="hold-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.GITHUB,
        )
        self.repo.save_brief(first)
        tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        draft = self.repo.get_operator_draft("app-1", "hold-1")
        assert draft is not None
        self.repo.record_draft_verdict(draft, "hold")
        self.assertIsNone(self.repo.living_stack_arena("app-1", "2026-08-13T06:00:00Z"))

        nxt = Brief.create(
            project_id="app-1",
            brief_id="hold-2",
            facts=(
                Fact(
                    text="a stranger can click and run the demo from the README",
                    artifact_url=SHIP_PR,
                ),
            ),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(nxt)
        out = tick(self.repo, self.cfg, due=(), now="2026-08-13T06:00:00Z")
        self.assertEqual(out["operator"]["outcomes"][0]["arena"], "hn")
        second = self.repo.get_operator_draft("app-1", "hold-2")
        assert second is not None
        self.assertEqual(second.costume, "seminar")

    def test_same_angle_body_as_last_is_cisza_not_a_second_draft(self) -> None:
        first = Brief.create(
            project_id="app-1",
            brief_id="ship-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        self.repo.save_brief(first)
        first_out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        first_draft = self.repo.get_operator_draft("app-1", "ship-1")
        assert first_draft is not None
        self.assertEqual(first_out["operator"]["outcomes"][0]["verdict"], "draft")
        self.assertEqual(first_draft.content_hash, angle_body_hash(first_draft.body))

        copy = Brief.create(
            project_id="app-1",
            brief_id="ship-2",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        self.repo.save_brief(copy)
        again = tick(self.repo, self.cfg, due=(), now="2026-08-13T06:00:00Z")
        outcome = again["operator"]["outcomes"][0]
        self.assertEqual(outcome["verdict"], "kill")
        self.assertEqual(outcome["reason"], "same_angle_body")
        self.assertIsNone(outcome.get("body"))
        self.assertIsNone(self.repo.get_operator_draft("app-1", "ship-2"))
        drafts = list(self.repo.conn.execute("SELECT draft_id FROM operator_drafts"))
        self.assertEqual(len(drafts), 1)
        self.assertEqual(self.repo.last_angle_body_hash("app-1"), first_draft.content_hash)

        fresh = Brief.create(
            project_id="app-1",
            brief_id="ship-3",
            facts=(Fact(text="dry-run still default and strangers can try it", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        self.repo.save_brief(fresh)
        third = tick(self.repo, self.cfg, due=(), now="2026-08-13T07:00:00Z")
        third_outcome = third["operator"]["outcomes"][0]
        self.assertEqual(third_outcome["verdict"], "draft")
        third_draft = self.repo.get_operator_draft("app-1", "ship-3")
        assert third_draft is not None
        self.assertNotEqual(third_draft.body, first_draft.body)
        self.assertNotEqual(third_draft.content_hash, first_draft.content_hash)
        self.assertTrue(third_draft.body.startswith("Show HN:"))
        self.assertNotIn("Costume:", third_draft.body)

    def test_drop_repeat_angle_is_body_hash_not_ids(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="copy-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
            preferred_arena=ArenaId.HN,
        )
        decision = apply_brief(brief, now="2026-08-13T05:00:00Z")
        assert decision.draft is not None
        same = drop_repeat_angle(decision, angle_body_hash(decision.draft.body))
        self.assertIsNone(same.draft)
        self.assertEqual(same.score.verdict, Verdict.KILL)
        self.assertEqual(same.score.reason, "same_angle_body")
        other = drop_repeat_angle(decision, angle_body_hash("Show HN: a new body\n\n" + SHIP_PR))
        self.assertIs(other.draft, decision.draft)
        self.assertEqual(angle_body_hash("one"), angle_body_hash("one"))
        self.assertNotEqual(angle_body_hash("one"), angle_body_hash("two"))

    def test_tick_kill_persists_score_without_draft_or_publish(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="kill-1",
            facts=(Fact(text="we shipped it"),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        out = tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        self.assertEqual(out["operator"]["outcomes"][0]["verdict"], "kill")
        self.assertEqual(out["operator"]["outcomes"][0]["reason"], "ship_claim_missing_artifact")
        self.assertIsNone(self.repo.get_operator_draft("app-1", "kill-1"))
        self.assertIsNone(
            self.repo.conn.execute("SELECT 1 FROM content_revisions").fetchone()
        )
        self.assertFalse(out["mutated"])

    def test_cli_readme_demo_repo_root_emits_hn_angle(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        ingest = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "ingest",
                "--project-id",
                "app-1",
                "--brief-id",
                "b-ship",
                "--story-kind",
                "major",
                "--claim-ship",
                "--tryable",
                "--artifact-url",
                SHIP_REPO,
                "--fact",
                human,
                "--arena",
                "hn",
            ]
        )
        self.assertEqual(ingest, 0)
        tick_code = tick_all_main(["--config", str(self.home / "config.json")])
        self.assertEqual(tick_code, 0)
        buf = io.StringIO()
        with redirect_stdout(buf):
            angle_code = main(["--config", str(self.home / "config.json"), "angle"])
        self.assertEqual(angle_code, 0)
        out = json.loads(buf.getvalue())
        self.assertEqual(out["status"], "ok")
        self.assertFalse(out["empty"])
        body = out["body"]
        self.assertEqual(body, f"Show HN: {human}\n\n{SHIP_REPO}")
        self.assertIn(SHIP_REPO, body)
        self.assertNotIn("/pull/1", body)
        self.assertFalse(out["published"])

    def test_cli_ingest_and_tick_all_patch_is_changelog_only(self) -> None:
        code = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "ingest",
                "--project-id",
                "app-1",
                "--brief-id",
                "patch-1",
                "--story-kind",
                "patch",
                "--fact",
                "fix README typo",
            ]
        )
        self.assertEqual(code, 0)
        code = tick_all_main(["--config", str(self.home / "config.json")])
        self.assertEqual(code, 0)
        score = self.repo.get_operator_score("app-1", "patch-1")
        assert score is not None
        self.assertEqual(score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertIsNone(self.repo.get_operator_draft("app-1", "patch-1"))

    def test_cli_json_ingest_roundtrip_show(self) -> None:
        path = self.home / "brief.json"
        path.write_text(
            json.dumps(
                {
                    "brief_id": "json-1",
                    "story_kind": "hard_issue",
                    "claims_ship": False,
                    "tryable": True,
                    "preferred_arena": "reddit",
                    "facts": [
                        {"kind": "pain", "text": "subprocess timeouts looked like success in r/SideProject"},
                        {"kind": "fix", "text": "unknown plus reconcile, no blind retry"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        code = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "ingest",
                "--project-id",
                "app-1",
                "--from-json",
                str(path),
            ]
        )
        self.assertEqual(code, 0)
        tick(self.repo, self.cfg, due=(), now="2026-08-13T05:00:00Z")
        show = main(
            [
                "--config",
                str(self.home / "config.json"),
                "brief",
                "show",
                "--project-id",
                "app-1",
                "--brief-id",
                "json-1",
            ]
        )
        self.assertEqual(show, 0)
        draft = self.repo.get_operator_draft("app-1", "json-1")
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.REDDIT)
        self.assertEqual(draft.costume, "village")

    def test_config_still_has_no_secret_fields(self) -> None:
        raw = json.loads((self.home / "config.json").read_text(encoding="utf-8"))
        blob = json.dumps(raw)
        for needle in ("token", "password", "secret", "api_key"):
            self.assertNotIn(needle, blob)

    def test_tick_all_writes_fala_subprocess_result_without_opening_runtime_db(self) -> None:
        from influenzer.tick_all import write_fala_result

        fala_out = self.home / "fala-out"
        payload = {"status": "ok", "mutated": False, "operator": {"published": False, "processed": 1}}
        path = write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(fala_out)})
        assert path is not None
        data = json.loads(path.read_text(encoding="utf-8"))
        self.assertFalse(data["metadata"]["published"])
        self.assertFalse(data["metadata"]["mutated"])
        self.assertEqual(data["reactions"][0]["kind"], "hom.decision")
        self.assertFalse((self.home / "runtime.db").exists())
        self.assertIsNone(write_fala_result(payload, env={}))
        blocked = self.home / "blocked-reaction-unit"
        blocked.write_text("not a directory", encoding="utf-8")
        self.assertIsNone(
            write_fala_result(payload, env={"FALA_EFFECTOR_OUTPUT_DIR": str(blocked)})
        )

    def test_fala_reaction_dir_pad_keeps_score_draft_and_does_not_kill_tick(self) -> None:
        brief = Brief.create(
            project_id="app-1",
            brief_id="fala-pad-1",
            facts=(Fact(text="operator emits drafts", artifact_url=SHIP_PR),),
            story_kind=StoryKind.MAJOR,
            claims_ship=True,
            tryable=True,
        )
        self.repo.save_brief(brief)
        blocked = self.home / "blocked-reaction"
        blocked.write_text("not a directory", encoding="utf-8")
        stdout = io.StringIO()
        with redirect_stdout(stdout), patch.dict(
            os.environ, {"FALA_EFFECTOR_OUTPUT_DIR": str(blocked)}, clear=False
        ):
            code = tick_all_main(["--config", str(self.home / "config.json")])
        self.assertEqual(code, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["operator"]["processed"], 1)
        stored = self.repo.get_brief("app-1", "fala-pad-1")
        assert stored is not None
        self.assertEqual(stored.status, "processed")
        score = self.repo.get_operator_score("app-1", "fala-pad-1")
        assert score is not None
        self.assertEqual(score.verdict, Verdict.DRAFT)
        draft = self.repo.get_operator_draft("app-1", "fala-pad-1")
        self.assertIsNotNone(draft)
        self.assertFalse((self.home / "runtime.db").exists())
        again = tick_all_main(["--config", str(self.home / "config.json")])
        self.assertEqual(again, 0)


class FalaPackageAndCatalogTests(unittest.TestCase):
    def test_fala_package_declares_operator_tick_on_sqlite_journal(self) -> None:
        import tomllib

        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        self.assertEqual(package["id"], "influenzer")
        self.assertEqual(package["runtime"]["backend"]["kind"], "sqlite")
        self.assertEqual(package["runtime"]["backend"]["path"], "runtime.db")
        self.assertNotEqual(package["runtime"]["backend"]["path"], "state.db")
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("operator_tick", paths)
        effectors = paths["operator_tick"]["effectors"]
        self.assertEqual(len(effectors), 1)
        self.assertEqual(effectors[0]["adapter"]["kind"], "subprocess")
        self.assertEqual(effectors[0]["adapter"]["command"], ["python3", "-m", "influenzer.tick_all"])
        blob = json.dumps(package)
        self.assertNotIn("ads", blob.lower())
        self.assertNotIn("native_function", blob)

    def test_catalog_score_brief_is_dry_and_never_publishes(self) -> None:
        from influenzer.catalog import list_effectors
        from influenzer.effector import run

        names = [entry["name"] for entry in list_effectors()]
        self.assertIn("score_brief", names)
        result = run(
            {
                "handler": "score_brief",
                "input": {
                    "project_id": "app-1",
                    "brief_id": "b-ship",
                    "story_kind": "major",
                    "claims_ship": True,
                    "tryable": True,
                    "facts": [
                        {
                            "text": "operator tick scores briefs",
                            "artifact_url": SHIP_PR,
                        }
                    ],
                },
            }
        )
        self.assertTrue(result["ok"])
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["mutated"])
        self.assertFalse(result["published"])
        self.assertEqual(result["verdict"], "draft")
        self.assertEqual(result["arena"], "hn")

        killed = run(
            {
                "handler": "score_brief",
                "input": {
                    "project_id": "app-1",
                    "brief_id": "b-kill",
                    "story_kind": "major",
                    "claims_ship": True,
                    "tryable": True,
                    "facts": [{"text": "shipped with no proof"}],
                },
            }
        )
        self.assertEqual(killed["verdict"], "kill")
        self.assertFalse(killed["mutated"])
        self.assertFalse(killed["published"])


if __name__ == "__main__":
    unittest.main()
