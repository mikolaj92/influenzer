# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=96 -->

Repository: `mikolaj92/influenzer`  
Issue: #96 — Pad zapisu Fala nie cofa score/draft

## Goal

Pad zapisu Fala (reaction dir) nie cofa score/draft w state.db i nie zabija pętli. Domena wygrywa. Journal jest obserwacją, nie właścicielem historii.

## Files likely touched

- `influenzer/fala_result.py` — swallow OSError on reaction-dir write
- `tests/test_hom_operator.py` — pad keeps score/draft; tick-all still returns 0
- `tests/test_tick_loop.py` — pad does not stop the interval loop

## Test plan

- `python3 -m unittest tests.test_hom_operator.TickBriefPathTests tests.test_tick_loop.TickLoopTests.test_fala_reaction_dir_pad_does_not_undo_score_or_stop_loop`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
