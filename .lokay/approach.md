# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=34 -->

Repository: `mikolaj92/influenzer`  
Issue: #34 — Parafia nie dostaje punchline’u z X

## Goal

Jeśli draft na Mastodon jest tym samym tekstem co X (albo jego obcięciem) — cisza na parish. Wolna rozmowa albo nic, nie broadcast.

## Files likely touched

- `influenzer/hom_draft.py` — parish dresser: skip the X one-liner and clips of it; fail-closed if nothing else remains
- `skills/influenzer-hom/SKILL.md` — parish is own conversation or silence
- `tests/test_hom_draft.py` — leaked-score silence + own conversation
- `tests/test_e2e_gates.py` — compose_draft refuses an X punchline paste

## Test plan

- `python -m pytest tests/test_hom_draft.py::HomDraftCostumeTests::test_mastodon_x_punchline_or_clip_is_undressable_even_when_score_says_draft tests/test_hom_draft.py::HomDraftCostumeTests::test_mastodon_wears_own_conversation_not_the_x_punchline tests/test_hom_draft.py::HomDraftCostumeTests::test_every_arena_dresser_refuses_the_label_dump tests/test_e2e_gates.py::OrderedLiveGateTests::test_parish_does_not_get_the_x_punchline -q`

## Non-goals

- No playbook/scoring rewrite outside the Mastodon dress path
- No publish / live / multi-story changes
- Do not invent an influenzer-mastodon skill directory

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Leak before the patch: `_dress_mastodon` pasted `one_liner` + rest, so parish wore the same hook X would wear.
- Mastodon already kills ship-claim as `mastodon_pr_tone`; this issue is the dress fold, not the PR-tone gate.
- Collector boundary: no collector.
