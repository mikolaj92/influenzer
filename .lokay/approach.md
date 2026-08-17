# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=40 -->

Repository: `mikolaj92/influenzer`  
Issue: #40 — Show HN bez tryable ship = cisza

## Goal

Show HN is not a lab notebook. `story_kind` exploration / decision / failure
without a tryable ship must not sit on HN. Workshop or silence. Seminar only
when a stranger can click and run it. Small `choose_arena` block, not a second
bag. Composes onto #32 (Show HN format). Not live. One story.

## Files likely touched

- `influenzer/playbook.py` — `choose_arena` no longer seats preferred HN for
  exploration / decision / failure; major / hard_issue still sit so a missing
  demo can die as `hn_not_tryable`.
- `skills/influenzer-hn/SKILL.md` — costume note: lab notebook is not Show HN.
- `tests/test_e2e_gates.py` — e2e gate: those kinds do not pick HN.

## Test plan

- `python -m pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_show_hn_without_tryable_ship_does_not_sit tests/test_e2e_gates.py::OrderedLiveGateTests::test_show_hn_is_title_url_and_backstory_or_silence tests/test_hom_operator.py::HomOperatorTests::test_choose_arena_keeps_living_github_or_hn_costume tests/test_hom_operator.py::HomOperatorTests::test_hn_without_tryable_is_killed -q`

## Non-goals

- Do not change living-stack / camp behavior after a real Show HN.
- Do not invent a new reason bag; reuse workshop / existing `hn_not_tryable`.
- Not live. One story.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Localization listed only the HN skill and e2e tests; inspection found the
  sit-path in `choose_arena` (`parse_stack_arena(preferred)` returned HN
  before story_kind / tryable). Refined file list accordingly.
