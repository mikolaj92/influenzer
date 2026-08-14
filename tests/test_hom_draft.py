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
from influenzer.playbook import ARENAS, ArenaId, StoryKind, Verdict, invented_metric_reason

from tests.test_hom_operator import FEEDBACK_COMMENT, SHIP_PR, SHIP_REPO


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
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_PR),
                Fact(kind="signal", text=human),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body
        self.assertEqual(body, f"Show HN: {human}\n\n{SHIP_PR}")
        self.assertNotIn("Show HN: ship artifact", body)
        self.assertNotEqual(body.splitlines()[0].casefold(), "show hn: ship artifact")
        self.assertNotIn("Costume:", body)

    def test_hn_readme_demo_repo_root_wears_human_fact_and_repo_url(self) -> None:
        human = "Local tick scores briefs and emits a draft"
        brief = _ship_brief(
            preferred_arena=ArenaId.HN,
            facts=(
                Fact(kind="artifact", text="ship artifact", artifact_url=SHIP_REPO),
                Fact(kind="signal", text=human),
            ),
        )
        decision = apply_brief(brief)
        assert decision.draft is not None
        self.assertEqual(decision.draft.body, f"Show HN: {human}\n\n{SHIP_REPO}")
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

    def test_x_is_short_reply_not_a_thread(self) -> None:
        brief = _ship_brief(preferred_arena=ArenaId.X)
        decision = apply_brief(brief)
        assert decision.draft is not None
        body = decision.draft.body
        self.assertLessEqual(len(body), 280 + 40)
        self.assertNotIn("1/", body)
        self.assertNotIn("thread", body.lower())
        self.assertIn(SHIP_PR, body)
        self.assertNotIn("Costume:", body)

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

    def test_every_arena_dresser_refuses_the_label_dump(self) -> None:
        from influenzer.hom_draft import _DRESSERS, _FORBIDDEN_IN_BODY

        self.assertEqual(set(_DRESSERS), set(ARENAS))
        brief = _ship_brief(
            preferred_arena=ArenaId.GITHUB,
            facts=(
                Fact(text="Local tick scores briefs and emits a draft", artifact_url=SHIP_PR),
                Fact(kind="package", text="title plus thumb in 0.5s: one-angle operator tick"),
                Fact(kind="hook", text="hook in 1-3s: brief in, draft out"),
                Fact(text="I struggled with timeouts looking like success in r/SideProject"),
            ),
        )
        for arena in ARENAS:
            if arena is ArenaId.DISCORD:
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
