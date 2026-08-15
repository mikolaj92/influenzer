# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=96 -->

Repository: `mikolaj92/influenzer`  
Issue: #96 — Pad zapisu Fala nie cofa score/draft

## Goal

Pad zapisu Fala (reaction dir) nie cofa score/draft w state.db i nie zabija pętli. Domena wygrywa. Journal jest obserwacją, nie właścicielem historii.

## Files likely touched

- `influenzer/fala_result.py` — swallow OSError on reaction-dir write
- `tests/test_hom_operator.py` — pad keeps score/draft; organ exits 0

## Test plan

- `tests/test_hom_operator.py::TickBriefPathTests.test_tick_all_writes_fala_subprocess_result_without_opening_runtime_db`
- `tests/test_hom_operator.py::TickBriefPathTests.test_fala_reaction_dir_pad_keeps_score_draft_and_does_not_kill_tick`

## Non-goals

- Do not wipe or recreate state.db (#94).
- Do not make the journal the owner of score/draft history.
- Do not stop the organ / interval loop on a reaction-dir pad.

## Notes

- Persist in `state.db` already happens before `write_fala_result`. The hole was the journal write raising and killing the organ after domain had already committed.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
