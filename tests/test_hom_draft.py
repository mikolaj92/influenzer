from __future__ import annotations

import io
import json
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from influenzer.hom import Brief, Fact, Score, apply_brief, brief_to_mapping, compose_draft, score_brief
from influenzer.hom_draft import dress_brief, dress_payload, main as draft_main
from influenzer.playbook import (
    ARENAS,
    ArenaId,
    BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON,
    LIVING_STACK_REASON,
    StoryKind,
    Verdict,
    cafe_artifact_reason,
    invented_metric_reason,
)

from tests.test_hom_operator import FEEDBACK_COMMENT, SHIP_PR, SHIP_RELEASE, SHIP_REPO


def _ship_brief(**overrides: object) -> Brief:
    facts = overrides.pop(
        "facts",
        (
            Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
            Fact(text="Dry-run still default"),
            Fact(text="Patches stay changelog-only"),
        ),
    )
    kwargs = dict(
        project_id="app-1",
        brief_id="b-ship",
        facts=facts,
        story_kind=StoryKind.MAJOR,
        claims_ship=True,
        tryable=True,
    )
    kwargs.update(overrides)
    return Brief.create(**kwargs)  # type: ignore[arg-type]


def _import_lines(path: Path) -> list[str]:
    found: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")):
            found.append(stripped)
    return found


class HomDraftCostumeTests(unittest.TestCase):
    def test_hn_ship_tryable_is_show_hn_not_a_costume_prefix(self) -> None:
        brief = _ship_brief()
        with patch("subprocess.run", side_effect=AssertionError("draft must not call subprocess")):
            decision = apply_brief(brief, now="2026-08-13T05:00:00Z")
        assert decision.draft is not None
        body = decision.draft.body
        self.assertTrue(body.startswith("Show HN:"))
        self.assertNotIn("Costume:", body)
        self.assertNotIn("One arena:", body)
        self.assertNotIn("One angle:", body)
        self.assertNotIn("Wave checklist:", body)
        self.assertIn(SHIP_PR, body)
        self.assertEqual(decision.draft.costume, "seminar")
        self.assertIn("body", __import__("influenzer.hom", fromlist=["decision_to_dict"]).decision_to_dict(decision))

    def test_hn_title_wears_the_human_fact_not_the_ship_artifact_stub(self) -> None:
        """README demo ingest: --artifact-url inserts kind=artifact text='ship artifact' first."""
        human = "Local tick scores briefs and emits a draft"
        backstory = "Dry-run still default"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(kind="signal", text=human),
                Fact(kind="signal", text=backstory),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body
        self.assertEqual(body, f"Show HN: {human}\n\n{SHIP_PR}\n\n{backstory}")
        self.assertNotIn("Show HN: ship artifact", body)
        self.assertNotEqual(body.splitlines()[0].casefold(), "show hn: ship artifact")
        self.assertNotIn("Costume:", body)

    def test_hn_readme_demo_repo_root_wears_human_fact_and_repo_url(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        backstory = "Dry-run still default"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_REPO),
                Fact(kind="signal", text=human),
                Fact(kind="signal", text=backstory),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.body, f"Show HN: {human}\n\n{SHIP_REPO}\n\n{backstory}")
        self.assertNotIn("/pull/1", decision.draft.body)
        self.assertNotIn("Show HN: ship artifact", decision.draft.body)

    def test_hn_keeps_distinct_rest_as_backstory_under_the_url(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        backstory = "Dry-run still default"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(kind="signal", text=human),
                Fact(kind="signal", text=backstory),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(
            decision.draft.body,
            f"Show HN: {human}\n\n{SHIP_PR}\n\n{backstory}",
        )

    def test_hn_without_backstory_is_undressable_even_when_score_says_draft(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(kind="signal", text=human),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("Show HN:", dumped)
        self.assertNotIn(human, dumped)

    def test_hn_first_comment_is_backstory_not_a_blog_dump(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        backstory = "Dry-run still default"
        extra = "Patches stay changelog-only"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(kind="signal", text=human),
                Fact(kind="signal", text=backstory),
                Fact(kind="signal", text=extra),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(
            decision.draft.body,
            f"Show HN: {human}\n\n{SHIP_PR}\n\n{backstory}",
        )
        self.assertNotIn(extra, decision.draft.body)
        self.assertEqual(len(decision.draft.body.split("\n\n")), 3)

    def test_github_ship_tryable_is_readme_shaped_with_artifact_url(self) -> None:
        brief = _ship_brief(preferred_arena=ArenaId.GITHUB)
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body
        self.assertEqual(decision.draft.arena, ArenaId.GITHUB)
        self.assertEqual(decision.draft.costume, "workshop")
        self.assertFalse(body.startswith("Costume:"))
        self.assertNotIn("Costume:", body)
        self.assertNotIn("One arena:", body)
        self.assertIn(SHIP_PR, body)
        self.assertIn("## Quickstart", body)
        first = body.splitlines()[0]
        self.assertTrue(first)
        self.assertNotEqual(first, "Costume: workshop")

    def test_kill_and_changelog_still_emit_no_draft(self) -> None:
        killed = _ship_brief(
            facts=(Fact(text="we shipped it"),),
            claims_ship=True,
            tryable=True,
        )
        killed_score = score_brief(killed)
        self.assertEqual(killed_score.verdict, Verdict.KILL)
        self.assertIsNone(compose_draft(killed, killed_score))
        self.assertIsNone(dress_brief(killed, killed_score))

        patch_brief = _ship_brief(
            story_kind=StoryKind.PATCH,
            claims_ship=False,
            tryable=False,
            facts=(Fact(text="typo in README"),),
        )
        patch_score = score_brief(patch_brief)
        self.assertEqual(patch_score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertIsNone(compose_draft(patch_brief, patch_score))
        self.assertIsNone(dress_brief(patch_brief, patch_score))

        stacked = _ship_brief(preferred_arena=ArenaId.GITHUB)
        stacked_score = score_brief(stacked, stack_arena=ArenaId.GITHUB)
        self.assertEqual(stacked_score.verdict, Verdict.CHANGELOG_ONLY)
        self.assertEqual(stacked_score.reason, LIVING_STACK_REASON)
        self.assertIsNone(compose_draft(stacked, stacked_score))
        self.assertIsNone(dress_brief(stacked, stacked_score))

    def test_quote_without_excerpt_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(text='users said "this is great"', artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("this is great", dumped)
        self.assertNotIn("Show HN:", dumped)

    def test_dress_does_not_invent_10x_or_1m_users_or_benchmarks(self) -> None:
        brief = _ship_brief()
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body.casefold()
        self.assertNotIn("10x", body)
        self.assertNotIn("1m users", body)
        self.assertNotIn("benchmark", body)
        triples = tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)
        self.assertIsNone(invented_metric_reason(triples, extra=decision.draft.body))

    def test_invented_metric_in_body_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief()
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        dressed = dress_brief(brief, fake)
        assert dressed is not None
        invented = dressed.body + "\n10x faster, 1M users, benchmark included"
        triples = tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)
        self.assertEqual(invented_metric_reason(triples, extra=invented), "invented_metric")
        from influenzer.playbook import unquotable_reason

        self.assertEqual(unquotable_reason(triples, extra=invented), "invented_metric")

    def test_number_from_brief_stays_in_hn_body(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick is 10x faster than the queue", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("10x", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        triples = tuple((fact.kind, fact.text, fact.artifact_url) for fact in brief.facts)
        self.assertIsNone(invented_metric_reason(triples, extra=decision.draft.body))

    def test_monday_without_history_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            tryable=False,
            facts=(
                Fact(text="weekly update"),
                Fact(text="newsletter cadence stays weekly"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.NEWSLETTER,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.NEWSLETTER].wave,
            canon_url=ARENAS[ArenaId.NEWSLETTER].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "newsletter",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.NEWSLETTER].wave),
                    "canon_url": ARENAS[ArenaId.NEWSLETTER].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("weekly update", dumped.lower())
        self.assertNotIn("Weekly update", dumped)

    def test_superlative_without_proof_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            tryable=False,
            facts=(
                Fact(text="the world's first local tick"),
                Fact(text="strangers should hear about it today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("world's first", dumped)
        self.assertNotIn("Show HN:", dumped)

    def test_dunking_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(text="Loki sucks, use this local tick instead", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("Loki sucks", dumped)
        self.assertNotIn("Show HN:", dumped)

    def test_foreign_wave_is_undressable_even_when_score_says_draft(self) -> None:
        parent = "https://x.com/other/status/123456789"
        brief = _ship_brief(
            facts=(
                Fact(kind="parent", text="rising mid-KOL post", artifact_url=parent),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.X,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.X].wave,
            canon_url=ARENAS[ArenaId.X].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "x",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.X].wave),
                    "canon_url": ARENAS[ArenaId.X].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn(parent, dumped)
        self.assertNotIn("rising mid-KOL", dumped)

    def test_reply_under_our_ship_can_still_dress(self) -> None:
        brief = _ship_brief(
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
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("Local tick scores briefs and emits a draft", decision.draft.body)
        self.assertNotIn("Show HN about mikolaj92/influenzer", decision.draft.body)

    def test_naming_a_predecessor_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Unlike Loki, this scores briefs locally", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("Unlike Loki", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))

    def test_engagement_bait_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(text="like if this local tick helped", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("like if", dumped)
        self.assertNotIn("Show HN:", dumped)

    def test_contest_is_undressable_even_when_score_says_draft(self) -> None:
        contests = (
            "giveaway of the local tick",
            "raffle for a seat",
            "RT to win a license",
            "nagroda za follow",
        )
        for text in contests:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("giveaway", dumped.lower())
                self.assertNotIn("raffle", dumped.lower())
                self.assertNotIn("RT to win", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_a_contest_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="follow the README to run the demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("follow the README", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("giveaway", decision.draft.body.lower())
        self.assertNotIn("raffle", decision.draft.body.lower())

    def test_poll_is_undressable_even_when_score_says_draft(self) -> None:
        polls = (
            "poll: dark mode or light",
            "this or that: CLI or TUI",
            "quiz: can you score a thin brief?",
            "ankieta o lokalnym ticku",
        )
        for text in polls:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("poll:", dumped.lower())
                self.assertNotIn("this or that", dumped.lower())
                self.assertNotIn("quiz:", dumped.lower())
                self.assertNotIn("ankieta", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_a_poll_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="follow the README to run the demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("follow the README", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("poll", decision.draft.body.lower())
        self.assertNotIn("quiz", decision.draft.body.lower())
        self.assertNotIn("ankieta", decision.draft.body.lower())

    def test_model_in_frame_is_undressable_even_when_score_says_draft(self) -> None:
        dumps = (
            "I asked ChatGPT how to score a brief",
            "as an AI I would ship the local tick",
            "here's the prompt I used for the launch",
            "zrzut rozmowy z modelem",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("chatgpt", dumped.lower())
                self.assertNotIn("as an ai", dumped.lower())
                self.assertNotIn("prompt", dumped.lower())
                self.assertNotIn("modelem", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_a_model_in_frame_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="prompt the operator with a brief, not a chat"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("prompt the operator", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("chatgpt", decision.draft.body.lower())
        self.assertNotIn("as an ai", decision.draft.body.lower())

    def test_calendar_filler_is_undressable_even_when_score_says_draft(self) -> None:
        greetings = (
            "happy Friday",
            "repo birthday",
            "urodziny repo",
            "wesołych świąt",
        )
        for text in greetings:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("happy friday", dumped.lower())
                self.assertNotIn("birthday", dumped.lower())
                self.assertNotIn("urodziny", dumped.lower())
                self.assertNotIn("świąt", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_calendar_filler_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="shipped Friday after the timeout fix"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("shipped Friday", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("happy friday", decision.draft.body.lower())
        self.assertNotIn("birthday", decision.draft.body.lower())

    def test_counter_thanks_is_undressable_even_when_score_says_draft(self) -> None:
        greetings = (
            "thanks for 1000 stars",
            "milestone follow",
            "dziękujemy za gwiazdki",
            "podziękowanie za licznik",
        )
        for text in greetings:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("thanks for", dumped.lower())
                self.assertNotIn("milestone follow", dumped.lower())
                self.assertNotIn("gwiazdki", dumped.lower())
                self.assertNotIn("podziękowanie", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_counter_thanks_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="thanks for the issue that named the timeout"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("thanks for the issue", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("thanks for 1000 stars", decision.draft.body.lower())
        self.assertNotIn("milestone follow", decision.draft.body.lower())

    def test_fog_is_undressable_even_when_score_says_draft(self) -> None:
        hints = (
            "subtweet about the local tick",
            "you know who still scores remotely",
            "aluzja bez artefaktu",
            "mgła",
        )
        for text in hints:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("subtweet", dumped.lower())
                self.assertNotIn("you know who", dumped.lower())
                self.assertNotIn("aluzja", dumped.lower())
                self.assertNotIn("mgła", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_fog_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="Unlike Loki, this scores briefs locally"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("Unlike Loki", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("subtweet", decision.draft.body.lower())
        self.assertNotIn("you know who", decision.draft.body.lower())

    def test_founder_journal_is_undressable_even_when_score_says_draft(self) -> None:
        lifestyle = (
            "desk setup for the local tick",
            "tools I use to score briefs",
            "day in the life of a local tick",
            "morning routine before the demo",
            "dziennik założyciela",
        )
        for text in lifestyle:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("desk setup", dumped.lower())
                self.assertNotIn("tools i use", dumped.lower())
                self.assertNotIn("day in the life", dumped.lower())
                self.assertNotIn("morning routine", dumped.lower())
                self.assertNotIn("dziennik", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_founder_journal_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="this morning we shipped the local tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("this morning we shipped", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("desk setup", decision.draft.body.lower())
        self.assertNotIn("morning routine", decision.draft.body.lower())

    def test_lead_magnet_is_undressable_even_when_score_says_draft(self) -> None:
        magnets = (
            "ebook for the local tick",
            "free guide to scoring briefs",
            "typeform for an email",
            "download the free pdf",
            "ebook za maila",
        )
        for text in magnets:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("ebook", dumped.lower())
                self.assertNotIn("free guide", dumped.lower())
                self.assertNotIn("typeform", dumped.lower())
                self.assertNotIn("free pdf", dumped.lower())
                self.assertNotIn("za maila", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_lead_magnet_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="user guide for the local tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("user guide", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("ebook", decision.draft.body.lower())
        self.assertNotIn("typeform", decision.draft.body.lower())

    def test_fomo_is_undressable_even_when_score_says_draft(self) -> None:
        pressure = (
            "only 5 spots for the local tick",
            "countdown to the launch",
            "last chance to try the local tick",
            "tylko 3 miejsca",
            "ostatnia szansa",
        )
        for text in pressure:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("only 5 spots", dumped.lower())
                self.assertNotIn("countdown", dumped.lower())
                self.assertNotIn("last chance", dumped.lower())
                self.assertNotIn("tylko 3", dumped.lower())
                self.assertNotIn("ostatnia szansa", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_fomo_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="parking spots near the office"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("parking spots", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("last chance", decision.draft.body.lower())
        self.assertNotIn("countdown", decision.draft.body.lower())

    def test_meme_is_undressable_even_when_score_says_draft(self) -> None:
        pictures = (
            "drake meme for the local tick",
            "wojak of the local tick",
            "reaction image without a demo",
            "tablica z memami",
            "ściana memów",
        )
        for text in pictures:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("drake", dumped.lower())
                self.assertNotIn("wojak", dumped.lower())
                self.assertNotIn("reaction image", dumped.lower())
                self.assertNotIn("tablica z mem", dumped.lower())
                self.assertNotIn("ściana mem", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_meme_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="screenshot of the local tick demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("screenshot", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("drake", decision.draft.body.lower())
        self.assertNotIn("wojak", decision.draft.body.lower())

    def test_logo_reveal_is_undressable_even_when_score_says_draft(self) -> None:
        looks = (
            "rebrand of the local tick",
            "new palette for the local tick",
            "moodboard for the launch",
            "logo reveal this week",
            "odsłona logo",
        )
        for text in looks:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("rebrand", dumped.lower())
                self.assertNotIn("palette", dumped.lower())
                self.assertNotIn("moodboard", dumped.lower())
                self.assertNotIn("logo reveal", dumped.lower())
                self.assertNotIn("odsłona", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_logo_reveal_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="logo intro then the demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("logo intro", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("rebrand", decision.draft.body.lower())
        self.assertNotIn("moodboard", decision.draft.body.lower())

    def test_thread_serial_is_undressable_even_when_score_says_draft(self) -> None:
        serials = (
            "1/7 local tick scores briefs",
            "1/n local tick scores briefs",
            "a launch thread for the local tick",
            "tweetstorm about the local tick",
        )
        for text in serials:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("1/7", dumped)
                self.assertNotIn("1/n", dumped)
                self.assertNotIn("thread", dumped.lower())
                self.assertNotIn("tweetstorm", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_a_thread_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="thread-safe local tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("thread-safe", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("1/", decision.draft.body)
        self.assertNotIn("tweetstorm", decision.draft.body.lower())

    def test_ranking_dump_is_undressable_even_when_score_says_draft(self) -> None:
        dumps = (
            "HN front for the local tick",
            "stars in the corner",
            "zrzut rankingu",
            "vanity chart",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("HN front", dumped)
                self.assertNotIn("stars in the corner", dumped)
                self.assertNotIn("zrzut rankingu", dumped)
                self.assertNotIn("vanity chart", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_a_ranking_dump_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="product dashboard for the local tick"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("product dashboard for the local tick", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("HN front", decision.draft.body)
        self.assertNotIn("vanity chart", decision.draft.body.lower())

    def test_press_release_tone_is_undressable_even_when_score_says_draft(self) -> None:
        phrases = (
            "we're excited",
            "announcement",
            "unveiling",
            "delighted to share",
        )
        arenas = (ArenaId.HN, ArenaId.GITHUB, ArenaId.X)
        for text in phrases:
            for arena in arenas:
                with self.subTest(text=text, arena=arena.value):
                    brief = _ship_brief(
                        preferred_arena=arena,
                        facts=(
                            Fact(text=text, artifact_url=SHIP_PR),
                            Fact(text="strangers can click and run the demo today"),
                        ),
                    )
                    fake = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(dress_brief(brief, fake))
                    payload = dress_payload(
                        {
                            "brief": brief_to_mapping(brief),
                            "score": {
                                "brief_id": brief.brief_id,
                                "verdict": "draft",
                                "reason": "one_angle",
                                "arena": arena.value,
                                "angle": "what shipped and why a stranger should try it",
                                "wave_checklist": list(ARENAS[arena].wave),
                                "canon_url": ARENAS[arena].canon_url,
                            },
                        }
                    )
                    self.assertEqual(payload["status"], "noop")
                    self.assertIsNone(payload["body"])
                    dumped = json.dumps(payload)
                    self.assertNotIn("we're excited", dumped.lower())
                    self.assertNotIn("delighted to share", dumped.lower())
                    self.assertNotIn("Show HN:", dumped)
                    self.assertNotIn("Costume:", dumped)

    def test_star_upvote_follow_or_rt_ask_is_undressable_even_when_score_says_draft(self) -> None:
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
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("star the repo", dumped)
                self.assertNotIn("upvote", dumped.lower())
                self.assertNotIn("follow us", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_hn_ranking_only_url_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="see the chart",
                    artifact_url="https://news.ycombinator.com/item?id=123",
                ),
                Fact(text="strangers can click the chart today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN:", json.dumps(payload))
        self.assertNotIn("news.ycombinator.com", json.dumps(payload.get("body") or ""))

    def test_feedback_question_can_still_dress(self) -> None:
        excerpt = "How do I install this when uv is missing?"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="issue_comment", text=f"@bob: {excerpt}", artifact_url=FEEDBACK_COMMENT),
                Fact(text=f'A stranger asked "{excerpt}"', artifact_url=SHIP_PR),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn(excerpt, decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("@bob", decision.draft.body)
        self.assertNotIn("Agree?", decision.draft.body)

    def test_hashtag_wall_is_undressable_even_when_score_says_draft(self) -> None:
        walls = (
            "#buildinpublic #saas #ai",
            "Local tick scores briefs #buildinpublic #saas #indiehackers",
            "Local tick scores briefs\n#buildinpublic #saas",
        )
        for text in walls:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                for arena in (ArenaId.HN, ArenaId.X, ArenaId.LINKEDIN):
                    fake = Score(
                        brief_id=brief.brief_id,
                        verdict=Verdict.DRAFT,
                        reason="one_angle",
                        arena=arena,
                        angle="what shipped and why a stranger should try it",
                        wave_checklist=ARENAS[arena].wave,
                        canon_url=ARENAS[arena].canon_url,
                    )
                    self.assertIsNone(dress_brief(brief, fake))
                    payload = dress_payload(
                        {
                            "brief": brief_to_mapping(brief),
                            "score": {
                                "brief_id": brief.brief_id,
                                "verdict": "draft",
                                "reason": "one_angle",
                                "arena": arena.value,
                                "angle": "what shipped and why a stranger should try it",
                                "wave_checklist": list(ARENAS[arena].wave),
                                "canon_url": ARENAS[arena].canon_url,
                            },
                        }
                    )
                    self.assertEqual(payload["status"], "noop")
                    self.assertIsNone(payload["body"])
                    dumped = json.dumps(payload)
                    self.assertNotIn("#saas", dumped)
                    self.assertNotIn("Show HN:", dumped)

    def test_one_inline_hashtag_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs #buildinpublic", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("#buildinpublic", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))

    def test_users_love_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(text="users love the local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("users love", json.dumps(payload))

    def test_quote_from_feedback_excerpt_with_url_can_still_dress(self) -> None:
        excerpt = "the Windows install fails with a traceback"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="issue_comment", text=f"@bob: {excerpt}", artifact_url=FEEDBACK_COMMENT),
                Fact(text=f'A stranger said "{excerpt}"', artifact_url=SHIP_PR),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn(excerpt, decision.draft.body)
        self.assertIn(f'"{excerpt}"', decision.draft.body)
        self.assertNotIn("@bob", decision.draft.body)

    def test_private_conversation_is_undressable_even_when_score_says_draft(self) -> None:
        dumps = (
            "Slack dump: a stranger said the Windows install fails",
            "from an email: the Windows install fails",
            "in a DM a user said the Windows install fails",
            "zrzut Slacka, nawet anonimizowany",
        )
        for text in dumps:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Slack dump", dumped)
                self.assertNotIn("from an email", dumped)
                self.assertNotIn("in a DM", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_world_commentary_is_undressable_even_when_score_says_draft(self) -> None:
        takes = (
            "hot take on today's headlines",
            "brief polityczny bez artefaktu",
            "news of the day, no repo",
            "komentarz świata: wybory",
        )
        for text in takes:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("hot take", dumped)
                self.assertNotIn("brief polityczny", dumped)
                self.assertNotIn("news of the day", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_news_url_only_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(
                    text="read the clipping",
                    artifact_url="https://www.nytimes.com/2026/08/14/world/europe.html",
                ),
                Fact(text="strangers can click the article today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("Show HN:", dumped)
        self.assertNotIn("nytimes.com", dumped)

    def test_product_copy_without_world_commentary_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="newsletter cadence stays weekly"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("newsletter cadence", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("hot take", decision.draft.body.lower())
        self.assertNotIn("headline", decision.draft.body.lower())

    def test_hire_fundraise_is_undressable_even_when_score_says_draft(self) -> None:
        notices = (
            "we're hiring a CMO",
            "we are raising a seed round",
            "team offsite next week",
            "rekrutacja na CMO",
        )
        for text in notices:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("hiring", dumped.lower())
                self.assertNotIn("fundraise", dumped.lower())
                self.assertNotIn("offsite", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_hire_fundraise_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="job application form validates a resume"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("job application form", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("hiring", decision.draft.body.lower())
        self.assertNotIn("fundraise", decision.draft.body.lower())
        self.assertNotIn("offsite", decision.draft.body.lower())

    def test_login_gate_is_undressable_even_when_score_says_draft(self) -> None:
        gated = (
            "behind a login",
            "HEAD 401",
            "GET 403",
            "za logowaniem",
        )
        for text in gated:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("behind a login", dumped.lower())
                self.assertNotIn("za logowaniem", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_login_gate_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="login form validates a password"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("login form validates a password", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("behind a login", decision.draft.body.lower())
        self.assertNotIn("za logowaniem", decision.draft.body.lower())

    def test_dead_link_is_undressable_even_when_score_says_draft(self) -> None:
        corpses = (
            "HEAD 404",
            "GET 410",
            "404/410",
            "dead link",
            "martwy link",
        )
        for text in corpses:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("HEAD 404", dumped)
                self.assertNotIn("martwy link", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_issues_disabled_is_undressable_on_hn_even_when_score_says_draft(self) -> None:
        closed = (
            "issues disabled",
            "hasIssuesEnabled: false",
            "repo z wyłączonymi issues",
            "no issue tracker",
        )
        for text in closed:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("issues disabled", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_issues_disabled_can_still_dress_github_readme(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.GITHUB,
            facts=(
                Fact(text="issues disabled", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.arena, ArenaId.GITHUB)
        self.assertFalse(decision.draft.body.startswith("Show HN:"))
        self.assertIn("## Quickstart", decision.draft.body)
        self.assertIn(SHIP_PR, decision.draft.body)

    def test_fork_is_undressable_even_when_score_says_draft(self) -> None:
        copies = (
            "isFork: true",
            "this repo is a fork",
            "forked from other/tool",
            "to jest fork",
        )
        for text in copies:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("isFork", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_archived_repo_is_undressable_even_when_score_says_draft(self) -> None:
        tombs = (
            "isArchived: true",
            "this repo is archived",
            "isDisabled: true",
            "nie launchujemy muzeum",
        )
        for text in tombs:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("isArchived", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_private_repo_is_undressable_even_when_score_says_draft(self) -> None:
        locks = (
            "isPrivate: true",
            "this repo is private",
            "visibility: private",
            "prywatne repo",
        )
        for text in locks:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("isPrivate", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_empty_repo_is_undressable_even_when_score_says_draft(self) -> None:
        blanks = (
            "isEmpty: true",
            "this repo is empty",
            "no README",
            "puste repo",
        )
        for text in blanks:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("isEmpty", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_server_splash_is_undressable_even_when_score_says_draft(self) -> None:
        splashes = (
            "Welcome to nginx",
            "Apache2 Debian Default Page",
            "Caddy placeholder page",
            "domyślna strona serwera",
        )
        for text in splashes:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Welcome to nginx", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_server_splash_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="nginx reverse proxy fronts the demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("nginx reverse proxy fronts the demo", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("Welcome to nginx", decision.draft.body)
        self.assertNotIn("Caddy placeholder", decision.draft.body)

    def test_bot_bump_week_is_undressable_even_when_score_says_draft(self) -> None:
        bumps = (
            "Merged PR #3: chore(deps): bump lodash from 4.17.20 to 4.17.21 by dependabot[bot]",
            "Released v1.2.3",
            "tydzień samych bump",
        )
        for text in bumps:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(kind="release", text="Released v1.2.3", artifact_url=SHIP_RELEASE),
                        Fact(
                            kind="pull",
                            text=text
                            if text.startswith("Merged")
                            else "Merged PR #9: bump actions/checkout from 4 to 5 by github-actions[bot]",
                            artifact_url="https://github.com/mikolaj92/influenzer/pull/9",
                        ),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Show HN:", dumped)
                self.assertNotIn("dependabot", dumped)

    def test_dead_star_count_is_undressable_even_when_score_says_draft(self) -> None:
        corpses = (
            "N stars",
            "5k\u2605",
            "we hit 1200 stars",
            "martwe gwiazdki",
        )
        for text in corpses:
            with self.subTest(text=text):
                brief = _ship_brief(
                    claims_ship=False,
                    tryable=False,
                    facts=(
                        Fact(text=text),
                        Fact(text="README has an install/quickstart a stranger can run"),
                    ),
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.GITHUB,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.GITHUB].wave,
                    canon_url=ARENAS[ArenaId.GITHUB].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "github",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.GITHUB].wave),
                            "canon_url": ARENAS[ArenaId.GITHUB].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("N stars", dumped)
                self.assertNotIn("1200 stars", dumped)
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_archived_repo_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="we archive old logs each night"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("we archive old logs each night", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("isArchived", decision.draft.body)

    def test_product_copy_without_private_repo_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="privacy-first local operator"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("privacy-first local operator", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("isPrivate", decision.draft.body)

    def test_product_copy_without_empty_repo_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="README without a GIF is a different gate"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("README without a GIF is a different gate", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("isEmpty", decision.draft.body)

    def test_product_copy_without_fork_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="we do not fork the worker"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("we do not fork the worker", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("isFork", decision.draft.body)

    def test_product_copy_without_issues_disabled_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="no issues with the install"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("no issues with the install", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("issues disabled", decision.draft.body.lower())

    def test_product_copy_without_dead_link_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="HTTP 200 on the demo"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("HTTP 200 on the demo", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("404", decision.draft.body)
        self.assertNotIn("410", decision.draft.body)
        self.assertNotIn("dead link", decision.draft.body.lower())
        self.assertNotIn("martwy", decision.draft.body.lower())

    def test_dead_release_asset_is_undressable_even_when_score_says_draft(self) -> None:
        corpses = (
            "asset on the list 404",
            "release asset is 404",
            "browser_download_url 410",
            "martwy plik",
        )
        for text in corpses:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_RELEASE),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("asset on the list", dumped.lower())
                self.assertNotIn("martwy plik", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_dead_release_asset_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="download the tarball from the release"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("download the tarball from the release", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("404", decision.draft.body)
        self.assertNotIn("410", decision.draft.body)
        self.assertNotIn("martwy", decision.draft.body.lower())

    def test_roadmap_is_undressable_even_when_score_says_draft(self) -> None:
        vapor = (
            "coming Q3",
            "on the roadmap",
            "shipping soon",
            "na roadmapie",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("roadmap", dumped.lower())
                self.assertNotIn("coming q3", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_roadmap_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="as soon as you install, the local tick scores"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("as soon as you install", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("roadmap", decision.draft.body.lower())
        self.assertNotIn("coming q3", decision.draft.body.lower())

    def test_prerelease_is_undressable_even_when_score_says_draft(self) -> None:
        vapor = (
            "draft release",
            "isPrerelease: true",
            "v1.2.3-rc.1",
            "public beta",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("prerelease", dumped.lower())
                self.assertNotIn("draft release", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_pending_ci_is_undressable_even_when_score_says_draft(self) -> None:
        vapor = (
            "CI is pending",
            "yellow CI",
            "statusCheckRollup: PENDING",
            "żółte CI",
        )
        for text in vapor:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("pending ci", dumped.lower())
                self.assertNotIn("yellow ci", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_failed_ci_is_undressable_even_when_score_says_draft(self) -> None:
        broken = (
            "CI failed",
            "red CI",
            "statusCheckRollup: FAILURE",
            "czerwone CI",
        )
        for text in broken:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("failed ci", dumped.lower())
                self.assertNotIn("red ci", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_product_copy_without_failed_ci_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="CI passed"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("CI passed", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("failed", decision.draft.body.lower())
        self.assertNotIn("red ci", decision.draft.body.lower())

    def test_product_copy_without_pending_ci_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="CI passed"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("CI passed", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("pending", decision.draft.body.lower())
        self.assertNotIn("yellow ci", decision.draft.body.lower())

    def test_product_copy_without_prerelease_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="Released v1.2.3"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("Released v1.2.3", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("prerelease", decision.draft.body.lower())
        self.assertNotIn("rc.1", decision.draft.body.lower())

    def test_source_available_plus_open_source_is_undressable_even_when_score_says_draft(self) -> None:
        lies = (
            "BUSL open source",
            "Commons Clause FOSS",
            "fair code OSS",
            "SSPL open source",
        )
        for text in lies:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("open source", dumped.lower())
                self.assertNotIn("Show HN:", dumped)

    def test_source_available_without_oss_sticker_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="source-available", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("source-available", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        lowered = decision.draft.body.lower()
        self.assertNotIn("open source", lowered)
        self.assertNotRegex(lowered, r"\bfoss\b")
        self.assertNotRegex(lowered, r"\boss\b")

    def test_product_copy_without_a_private_conversation_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="Slack integration posts the draft to a workspace"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertIn("Slack integration", decision.draft.body)
        self.assertTrue(decision.draft.body.startswith("Show HN:"))
        self.assertNotIn("Slack dump", decision.draft.body)
        self.assertNotIn("direct message", decision.draft.body.lower())

    def test_operator_mention_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(text="@alice try this local tick", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            )
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn("@alice", dumped)
        self.assertNotIn("Show HN:", dumped)

    def test_hn_refuses_merged_pr_title_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            facts=(
                Fact(
                    text="Merged PR #190: Treat GitHub repo root as a ship artifact",
                    artifact_url=SHIP_PR,
                ),
                Fact(text="Merged PR #187: feat: prior operator look"),
                Fact(text="Merged PR #22: feat(hom): local tick scores briefs"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN: Merged PR", json.dumps(payload))

    def test_hn_http_javascript_data_or_file_url_is_undressable(self) -> None:
        almost = (
            "http://github.com/mikolaj92/influenzer",
            "javascript:alert(1)",
            "data:text/html,<h1>demo</h1>",
            "file:///tmp/demo.html",
        )
        for url in almost:
            with self.subTest(url=url):
                brief = _ship_brief(
                    claims_ship=False,
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text="a stranger can almost click this", artifact_url=url),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Show HN:", dumped)
                self.assertNotIn(url, dumped)

    def test_hn_film_only_url_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="watch the walkthrough",
                    artifact_url="https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                ),
                Fact(text="strangers can click the film today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN:", json.dumps(payload))
        self.assertNotIn("youtube.com", json.dumps(payload.get("body") or ""))

    def test_hn_store_only_url_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="download the app",
                    artifact_url="https://apps.apple.com/app/id123456789",
                ),
                Fact(text="strangers can install it today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN:", json.dumps(payload))
        self.assertNotIn("apps.apple.com", json.dumps(payload.get("body") or ""))

    def test_hn_blog_only_url_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="read the writeup",
                    artifact_url="https://medium.com/@someone/we-shipped-a-thing-abc123",
                ),
                Fact(text="strangers can click the article today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN:", json.dumps(payload))
        self.assertNotIn("medium.com", json.dumps(payload.get("body") or ""))

    def test_hn_launch_only_url_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(
            claims_ship=False,
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(
                    text="see the launch card",
                    artifact_url="https://www.producthunt.com/posts/local-tick",
                ),
                Fact(text="strangers can click the board today"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "hn",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                    "canon_url": ARENAS[ArenaId.HN].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        self.assertNotIn("Show HN:", json.dumps(payload))
        self.assertNotIn("producthunt.com", json.dumps(payload.get("body") or ""))

    def test_hn_listicle_title_is_undressable_even_when_score_says_draft(self) -> None:
        bait = (
            "7 ways to score briefs",
            "you won't believe this local tick",
            "Local tick scores briefs!",
        )
        for title in bait:
            with self.subTest(title=title):
                brief = _ship_brief(
                    preferred_arena=ArenaId.HN,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.HN,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.HN].wave,
                    canon_url=ARENAS[ArenaId.HN].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "hn",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.HN].wave),
                            "canon_url": ARENAS[ArenaId.HN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                self.assertNotIn("Show HN:", json.dumps(payload))

    def test_shouty_title_is_undressable_on_hn_and_github_even_when_score_says_draft(self) -> None:
        title = "LOCAL TICK SCORES BRIEFS AND EMITS A DRAFT"
        for arena in (ArenaId.HN, ArenaId.GITHUB):
            with self.subTest(arena=arena.value):
                brief = _ship_brief(
                    preferred_arena=arena,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=arena,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[arena].wave,
                    canon_url=ARENAS[arena].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": arena.value,
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[arena].wave),
                            "canon_url": ARENAS[arena].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Show HN:", dumped)
                self.assertNotIn(title, dumped)

    def test_emoji_title_is_undressable_on_hn_and_github_even_when_score_says_draft(self) -> None:
        title = "Local tick scores briefs \U0001f680"
        for arena in (ArenaId.HN, ArenaId.GITHUB):
            with self.subTest(arena=arena.value):
                brief = _ship_brief(
                    preferred_arena=arena,
                    facts=(
                        Fact(text=title, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    ),
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=arena,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[arena].wave,
                    canon_url=ARENAS[arena].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": arena.value,
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[arena].wave),
                            "canon_url": ARENAS[arena].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Show HN:", dumped)
                self.assertNotIn(title, dumped)

    def test_hn_without_tryable_url_is_undressable_not_a_label_dump(self) -> None:
        brief = _ship_brief(
            facts=(Fact(text="a working demo exists on my laptop"), Fact(text="strangers can run it locally")),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.HN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.HN].wave,
            canon_url=ARENAS[ArenaId.HN].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))

    def test_linkedin_fold_is_insight_first_and_under_210(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.LINKEDIN,
            claims_ship=False,
            facts=(
                Fact(text="Dry-run still default on every tick"),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.costume, "court")
        fold = decision.draft.body.split("\n\n", 1)[0]
        self.assertLessEqual(len(fold), 210)
        self.assertNotIn("http", fold.lower())
        self.assertFalse(fold.lower().startswith("shipped"))
        self.assertIn(SHIP_PR, decision.draft.body)
        self.assertNotIn("Costume:", decision.draft.body)

    def test_linkedin_fold_starting_with_pitch_cta_or_url_is_undressable_even_when_score_says_draft(self) -> None:
        stalls = (
            "we're launching the operator today",
            "we’re launching the operator today",
            "we are launching the operator today",
            "Learn more in the comments",
            "Comment if you agree this local tick helps",
            "https://example.com/launch",
        )
        fake = Score(
            brief_id="b-court-stall",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.LINKEDIN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.LINKEDIN].wave,
            canon_url=ARENAS[ArenaId.LINKEDIN].canon_url,
        )
        for text in stalls:
            with self.subTest(text=text):
                brief = _ship_brief(
                    brief_id="b-court-stall",
                    preferred_arena=ArenaId.LINKEDIN,
                    claims_ship=False,
                    facts=(
                        Fact(text=text, artifact_url=SHIP_PR),
                        Fact(text=text),
                    ),
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "linkedin",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.LINKEDIN].wave),
                            "canon_url": ARENAS[ArenaId.LINKEDIN].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Costume:", dumped)
                self.assertNotIn(text, dumped)

    def test_linkedin_skips_a_launch_line_and_wears_the_insight_as_fold(self) -> None:
        insight = "Dry-run still default on every tick"
        brief = _ship_brief(
            preferred_arena=ArenaId.LINKEDIN,
            claims_ship=False,
            facts=(
                Fact(text="we're launching the operator today"),
                Fact(text=insight, artifact_url=SHIP_PR),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.LINKEDIN,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.LINKEDIN].wave,
            canon_url=ARENAS[ArenaId.LINKEDIN].canon_url,
        )
        draft = dress_brief(brief, fake)
        assert draft is not None
        fold = draft.body.split("\n\n", 1)[0]
        self.assertEqual(fold, insight)
        self.assertLessEqual(len(fold), 210)
        self.assertFalse(fold.lower().startswith("we"))
        self.assertNotIn("http", fold.lower())
        self.assertNotIn("launching", fold.lower())
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_mastodon_x_punchline_or_clip_is_undressable_even_when_score_says_draft(self) -> None:
        punchline = "Local tick scores briefs and emits a draft"
        clips = (
            (punchline,),
            (punchline, punchline),
            (punchline, "Local tick scores briefs"),
            (punchline, "local tick scores briefs and emits a draft."),
        )
        fake = Score(
            brief_id="b-parish-punchline",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.MASTODON,
            angle="I struggled with X",
            wave_checklist=ARENAS[ArenaId.MASTODON].wave,
            canon_url=ARENAS[ArenaId.MASTODON].canon_url,
        )
        for texts in clips:
            with self.subTest(texts=texts):
                brief = _ship_brief(
                    brief_id="b-parish-punchline",
                    preferred_arena=ArenaId.MASTODON,
                    claims_ship=False,
                    story_kind=StoryKind.HARD_ISSUE,
                    facts=tuple(Fact(text=text, artifact_url=SHIP_PR if idx == 0 else None) for idx, text in enumerate(texts)),
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "mastodon",
                            "angle": "I struggled with X",
                            "wave_checklist": list(ARENAS[ArenaId.MASTODON].wave),
                            "canon_url": ARENAS[ArenaId.MASTODON].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Costume:", dumped)
                self.assertNotIn(punchline, dumped)

    def test_mastodon_wears_own_conversation_not_the_x_punchline(self) -> None:
        punchline = "Local tick scores briefs and emits a draft"
        talk = "The dry-run still sat with us on every tick"
        brief = _ship_brief(
            preferred_arena=ArenaId.MASTODON,
            claims_ship=False,
            story_kind=StoryKind.HARD_ISSUE,
            facts=(
                Fact(text=punchline, artifact_url=SHIP_PR),
                Fact(text=talk),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.MASTODON,
            angle="I struggled with X",
            wave_checklist=ARENAS[ArenaId.MASTODON].wave,
            canon_url=ARENAS[ArenaId.MASTODON].canon_url,
        )
        draft = dress_brief(brief, fake)
        assert draft is not None
        self.assertEqual(draft.costume, "parish")
        self.assertEqual(draft.body, talk)
        self.assertNotEqual(draft.body, punchline)
        self.assertFalse(draft.body.casefold().startswith("local tick"))
        self.assertNotIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_x_is_short_reply_not_a_thread(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.X,
            facts=(
                Fact(
                    kind="parent",
                    text="Show HN about mikolaj92/influenzer",
                    artifact_url="https://news.ycombinator.com/item?id=1",
                ),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="Dry-run still default"),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body
        self.assertLessEqual(len(body), 280 + 40)
        self.assertNotIn("1/", body)
        self.assertNotIn("thread", body.lower())
        self.assertIn(SHIP_PR, body)
        self.assertNotIn("Costume:", body)

    def test_bluesky_without_artifact_url_is_undressable_even_when_score_says_draft(self) -> None:
        living = (
            "starter pack of 30 active accounts in the local-first niche",
            "two custom feeds retain the same people",
        )
        almost = (
            None,
            "https://example.com/demo",
            "https://bsky.app/profile/did:plc:demo/post/1",
            "https://github.com/mikolaj92/influenzer/commit/abc",
        )
        fake = Score(
            brief_id="b-empty-cafe-artifact",
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.BLUESKY,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.BLUESKY].wave,
            canon_url=ARENAS[ArenaId.BLUESKY].canon_url,
        )
        for idx, url in enumerate(almost):
            with self.subTest(url=url):
                self.assertEqual(
                    cafe_artifact_reason((url,) if url else ()),
                    BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON,
                )
                brief = _ship_brief(
                    brief_id=f"b-empty-cafe-artifact-{idx}",
                    preferred_arena=ArenaId.BLUESKY,
                    claims_ship=False,
                    facts=(
                        Fact(text="vibe posting about the operator", artifact_url=url),
                        Fact(text=living[0]),
                        Fact(text=living[1]),
                    ),
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "bluesky",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.BLUESKY].wave),
                            "canon_url": ARENAS[ArenaId.BLUESKY].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Costume:", dumped)
                if url:
                    self.assertNotIn(url, dumped)

    def test_bluesky_without_pack_and_feed_is_undressable_even_when_score_says_draft(self) -> None:
        brief = _ship_brief(preferred_arena=ArenaId.BLUESKY)
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.BLUESKY,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.BLUESKY].wave,
            canon_url=ARENAS[ArenaId.BLUESKY].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))
        payload = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "draft",
                    "reason": "one_angle",
                    "arena": "bluesky",
                    "angle": "what shipped and why a stranger should try it",
                    "wave_checklist": list(ARENAS[ArenaId.BLUESKY].wave),
                    "canon_url": ARENAS[ArenaId.BLUESKY].canon_url,
                },
            }
        )
        self.assertEqual(payload["status"], "noop")
        self.assertIsNone(payload["body"])
        dumped = json.dumps(payload)
        self.assertNotIn(SHIP_PR, dumped)
        self.assertNotIn("Costume:", dumped)

    def test_bluesky_with_pack_and_feed_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.BLUESKY,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(text="starter pack of 30 active accounts in the local-first niche"),
                Fact(text="two custom feeds retain the same people"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.BLUESKY,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.BLUESKY].wave,
            canon_url=ARENAS[ArenaId.BLUESKY].canon_url,
        )
        draft = dress_brief(brief, fake)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.BLUESKY)
        self.assertEqual(draft.costume, "newer cafe")
        self.assertIn(SHIP_PR, draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_discord_cannot_be_dressed(self) -> None:
        brief = _ship_brief(preferred_arena=ArenaId.DISCORD, claims_ship=False)
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.DISCORD,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.DISCORD].wave,
            canon_url=ARENAS[ArenaId.DISCORD].canon_url,
        )
        self.assertIsNone(dress_brief(brief, fake))

    def test_shorts_without_loop_is_undressable_even_when_score_says_draft(self) -> None:
        missing = (
            "hook in 1-3s: brief in, draft out",
            "first 3s: picture plus voice plus text",
        )
        for text in missing:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(kind="hook", text=text, artifact_url=SHIP_PR),
                        Fact(text="strangers can click and run the demo today"),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.SHORTS,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.SHORTS].wave,
                    canon_url=ARENAS[ArenaId.SHORTS].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "shorts",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.SHORTS].wave),
                            "canon_url": ARENAS[ArenaId.SHORTS].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("hook in 1-3s", dumped)
                self.assertNotIn("first 3s", dumped)

    def test_shorts_cta_and_loop_together_is_undressable_even_when_score_says_draft(self) -> None:
        both = (
            "last frame into first, then subscribe",
            "rewatch the cut — link in bio",
            "ostatnia klatka w pierwszą i CTA",
        )
        for text in both:
            with self.subTest(text=text):
                brief = _ship_brief(
                    facts=(
                        Fact(kind="hook", text="hook in 1-3s: brief in, draft out", artifact_url=SHIP_PR),
                        Fact(text=text),
                    )
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.SHORTS,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.SHORTS].wave,
                    canon_url=ARENAS[ArenaId.SHORTS].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "shorts",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.SHORTS].wave),
                            "canon_url": ARENAS[ArenaId.SHORTS].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("subscribe", dumped.lower())
                self.assertNotIn("link in bio", dumped.lower())
                self.assertNotIn("CTA", dumped)

    def test_shorts_loop_without_cta_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.SHORTS,
            facts=(
                Fact(kind="hook", text="hook in 1-3s: brief in, draft out", artifact_url=SHIP_PR),
                Fact(text="last frame into first; rewatch is the signal"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.SHORTS,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.SHORTS].wave,
            canon_url=ARENAS[ArenaId.SHORTS].canon_url,
        )
        draft = dress_brief(brief, fake)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.SHORTS)
        self.assertEqual(draft.costume, "fair")
        self.assertIn("hook in 1-3s", draft.body)
        self.assertIn("last frame into first", draft.body)
        self.assertNotIn("subscribe", draft.body.lower())
        self.assertNotIn("cta", draft.body.lower())
        self.assertNotIn("Costume:", draft.body)

    def test_reddit_without_disclosure_is_undressable_even_when_score_says_draft(self) -> None:
        empties = (
            (
                Fact(text="timeouts looked like success in r/SideProject", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
            (
                Fact(text="I built a local tick in r/SideProject"),
                Fact(text="strangers can click and run the demo today"),
            ),
            (
                Fact(text="bez ujawnienia, native self-post in r/SideProject", artifact_url=SHIP_PR),
                Fact(text="strangers can click and run the demo today"),
            ),
        )
        for facts in empties:
            with self.subTest(text=facts[0].text):
                brief = _ship_brief(
                    preferred_arena=ArenaId.REDDIT,
                    claims_ship=False,
                    facts=facts,
                )
                fake = Score(
                    brief_id=brief.brief_id,
                    verdict=Verdict.DRAFT,
                    reason="one_angle",
                    arena=ArenaId.REDDIT,
                    angle="what shipped and why a stranger should try it",
                    wave_checklist=ARENAS[ArenaId.REDDIT].wave,
                    canon_url=ARENAS[ArenaId.REDDIT].canon_url,
                )
                self.assertIsNone(dress_brief(brief, fake))
                payload = dress_payload(
                    {
                        "brief": brief_to_mapping(brief),
                        "score": {
                            "brief_id": brief.brief_id,
                            "verdict": "draft",
                            "reason": "one_angle",
                            "arena": "reddit",
                            "angle": "what shipped and why a stranger should try it",
                            "wave_checklist": list(ARENAS[ArenaId.REDDIT].wave),
                            "canon_url": ARENAS[ArenaId.REDDIT].canon_url,
                        },
                    }
                )
                self.assertEqual(payload["status"], "noop")
                self.assertIsNone(payload["body"])
                dumped = json.dumps(payload)
                self.assertNotIn("Show HN:", dumped)
                self.assertNotIn("Costume:", dumped)

    def test_reddit_with_disclosure_and_repo_can_still_dress(self) -> None:
        brief = _ship_brief(
            preferred_arena=ArenaId.REDDIT,
            facts=(
                Fact(text="I built a local tick that scores briefs", artifact_url=SHIP_PR),
                Fact(text="native self-post in r/SideProject"),
            ),
        )
        fake = Score(
            brief_id=brief.brief_id,
            verdict=Verdict.DRAFT,
            reason="one_angle",
            arena=ArenaId.REDDIT,
            angle="what shipped and why a stranger should try it",
            wave_checklist=ARENAS[ArenaId.REDDIT].wave,
            canon_url=ARENAS[ArenaId.REDDIT].canon_url,
        )
        draft = dress_brief(brief, fake)
        assert draft is not None
        self.assertEqual(draft.arena, ArenaId.REDDIT)
        self.assertEqual(draft.costume, "village")
        self.assertIn("I built", draft.body)
        self.assertIn(SHIP_PR, draft.body)
        self.assertIn("r/SideProject", draft.body)
        self.assertNotIn("Costume:", draft.body)

    def test_every_arena_dresser_refuses_the_label_dump(self) -> None:
        from influenzer.hom_draft import _DRESSERS, _FORBIDDEN_IN_BODY

        self.assertEqual(set(_DRESSERS), set(ARENAS))
        brief = _ship_brief(
            preferred_arena=ArenaId.GITHUB,
            facts=(
                Fact(
                    kind="parent",
                    text="Show HN about mikolaj92/influenzer",
                    artifact_url="https://news.ycombinator.com/item?id=1",
                ),
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(kind="package", text="title plus thumb in 0.5s: one-angle operator tick"),
                Fact(kind="hook", text="hook in 1-3s: brief in, draft out"),
                Fact(text="last frame into first; rewatch is the signal"),
                Fact(text="I built a local tick; this is my project in r/SideProject"),
                Fact(text="Mikolaj Nowak"),
            ),
        )
        for arena in ARENAS:
            if arena in {ArenaId.DISCORD, ArenaId.LINKEDIN, ArenaId.BLUESKY}:
                continue
            score = Score(
                brief_id=brief.brief_id,
                verdict=Verdict.DRAFT,
                reason="one_angle",
                arena=arena,
                angle="what shipped and why a stranger should try it",
                wave_checklist=ARENAS[arena].wave,
                canon_url=ARENAS[arena].canon_url,
            )
            draft = dress_brief(brief, score)
            self.assertIsNotNone(draft, arena.value)
            assert draft is not None
            for marker in _FORBIDDEN_IN_BODY:
                self.assertNotIn(marker, draft.body, arena.value)


class HomDraftBlockBoundaryTests(unittest.TestCase):
    def test_module_lists_what_it_refuses(self) -> None:
        src = Path(__file__).resolve().parents[1] / "influenzer" / "hom_draft.py"
        blob = src.read_text(encoding="utf-8")
        self.assertIn("Does not survey GitHub", blob)
        self.assertIn("Does not call gh", blob)
        self.assertIn("Does not write state.db", blob)
        self.assertIn("Does not pick the arena", blob)
        self.assertIn("Does not score", blob)
        self.assertIn("Does not publish", blob)
        self.assertIn("Does not enable live social", blob)
        self.assertIn("Does not know Heimdall", blob)
        imports = _import_lines(src)
        self.assertFalse(any("github_survey" in line or "github_pack" in line for line in imports))
        self.assertFalse(any("storage" in line for line in imports))
        self.assertFalse(any("scheduler" in line or "tick_all" in line for line in imports))
        self.assertFalse(any("subprocess" in line for line in imports))
        init = (Path(__file__).resolve().parents[1] / "influenzer" / "__init__.py").read_text(encoding="utf-8")
        self.assertNotIn("hom_draft", init)
        hom = (Path(__file__).resolve().parents[1] / "influenzer" / "hom.py").read_text(encoding="utf-8")
        self.assertNotIn("from influenzer.hom_draft import", hom.split("def compose_draft", 1)[0])

    def test_stdin_json_dresses_or_silences_without_state_db(self) -> None:
        brief = _ship_brief()
        score = score_brief(brief)
        payload = {
            "brief": brief_to_mapping(brief),
            "score": {
                "brief_id": score.brief_id,
                "verdict": score.verdict.value,
                "reason": score.reason,
                "arena": score.arena.value if score.arena else None,
                "angle": score.angle,
                "wave_checklist": list(score.wave_checklist),
                "canon_url": score.canon_url,
            },
            "now": "2026-08-13T05:00:00Z",
        }
        with patch("subprocess.run", side_effect=AssertionError("draft must not call subprocess")):
            out = dress_payload(payload)
        self.assertEqual(out["status"], "ok")
        self.assertTrue(out["body"].startswith("Show HN:"))
        self.assertIn(SHIP_PR, out["body"])
        self.assertFalse(out["published"])

        killed = dress_payload(
            {
                "brief": brief_to_mapping(brief),
                "score": {
                    "brief_id": brief.brief_id,
                    "verdict": "kill",
                    "reason": "empty_brief",
                    "arena": None,
                    "angle": None,
                    "wave_checklist": [],
                    "canon_url": score.canon_url,
                },
            }
        )
        self.assertEqual(killed["status"], "noop")
        self.assertEqual(killed["reason"], "kill")
        self.assertIsNone(killed["body"])

        buf = io.StringIO()
        with patch("sys.stdin", io.StringIO(json.dumps(payload))), redirect_stdout(buf):
            code = draft_main([])
        self.assertEqual(code, 0)
        printed = json.loads(buf.getvalue())
        self.assertTrue(printed["body"].startswith("Show HN:"))

    def test_fala_package_lists_draft_only_organ(self) -> None:
        root = Path(__file__).resolve().parents[1]
        package = tomllib.loads((root / "fala-package.toml").read_text(encoding="utf-8"))
        caps = {item["id"] for item in package["capabilities"]}
        self.assertIn("hom_draft", caps)
        paths = {item["id"]: item for item in package["correlation_paths"]}
        self.assertIn("hom_draft", paths)
        commands = [item["adapter"]["command"] for item in paths["hom_draft"]["effectors"]]
        self.assertEqual(commands, [["python3", "-m", "influenzer.hom_draft"]])
        self.assertEqual(len(paths["operator_tick"]["effectors"]), 1)
        blob = json.dumps(package)
        self.assertNotIn("native_function", blob)
        self.assertNotIn("ads", blob.lower())


if __name__ == "__main__":
    unittest.main()
