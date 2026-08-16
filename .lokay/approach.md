# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=57 -->

Repository: `mikolaj92/influenzer`  
Issue: #57 — Pusta tawerna nie dostaje zaproszenia

## Goal

Discord bez podziału intencji (help / show / contribute / lounge) albo bez sygnału że jest ~10 builderów — cisza na tavern. Publiczny invite na pustkę to nie kostium.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `tests/test_e2e_gates.py`
- `tests/test_hom_operator.py`

## Test plan

- `python3 -m pytest tests/test_e2e_gates.py tests/test_hom_operator.py::ScoreBriefTests::test_discord_is_not_a_launch_arena tests/test_hom_operator.py::ScoreBriefTests::test_every_arena_has_a_fail_closed_gate tests/test_hom_draft.py::HomDraftCostumeTests::test_discord_cannot_be_dressed -q`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
