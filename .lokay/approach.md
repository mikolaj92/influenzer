# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=141 -->

Repository: `mikolaj92/influenzer`  
Issue: #141 — Ankieta nie jest kątem

## Goal

Ankieta nie jest kątem. Poll, „this or that”, quiz = cisza. To nie produkt.

## Files likely touched

- `influenzer/playbook.py` — fail-closed poll / this-or-that / quiz / ankieta detector
- `influenzer/hom.py` — score kills a poll as not an angle
- `influenzer/hom_draft.py` — refuse to dress a leaked poll draft
- `tests/test_hom_operator.py` — detector + score silence
- `tests/test_hom_draft.py` — undressable even when score says draft
- `tests/test_e2e_gates.py` — scoped e2e: poll/quiz/this-or-that is silence

## Test plan

- Run the smallest useful tests for files touched:
  - `uv run python -m unittest tests.test_e2e_gates tests.test_hom_operator.PlaybookCopyTests.test_poll_is_quiz_this_or_that_or_ankieta tests.test_hom_operator.ScoreBriefTests.test_poll_is_killed tests.test_hom_draft.HomDraftCostumeTests.test_poll_is_undressable_even_when_score_says_draft tests.test_hom_draft.HomDraftCostumeTests.test_product_copy_without_a_poll_can_still_dress`

## Non-goals

- Do not treat GitHub survey / pack as a social poll.
- Do not silence product copy that merely mentions polling an API.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Same fail-closed path as #135 (contest) and #114 (engagement bait).
- Deterministic localize only listed `tests/test_e2e_gates.py` (token `gate`). Inspection refined the file list to the HOM playbook path.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
