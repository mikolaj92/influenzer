# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=96 -->

Repository: `mikolaj92/influenzer`  
Issue: #96 — Pad zapisu Fala nie cofa score/draft

## Goal

Pad zapisu Fala (reaction dir) nie cofa score/draft w state.db i nie zabija pętli. Domena wygrywa. Journal jest obserwacją, nie właścicielem historii.

## Files likely touched

- `influenzer/fala_result.py` — reaction-dir write is observation; OSError does not raise
- `tests/test_hom_operator.py` — pad keeps score/draft and tick-all stays up

## Test plan

- `python -m unittest tests.test_hom_operator.TickBriefPathTests.test_fala_write_pad_keeps_score_draft_and_does_not_kill_tick_all tests.test_hom_operator.TickBriefPathTests.test_tick_all_writes_fala_subprocess_result_without_opening_runtime_db`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
