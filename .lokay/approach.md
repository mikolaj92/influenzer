# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=98 -->

Repository: `mikolaj92/influenzer`  
Issue: #98 — Always-on nie sączy treści kąta do logów

## Goal

Always-on nie sączy treści kąta do logów. Body tylko przez jawne `angle` / pass stdout. Pętla pisze status (cisza/admitted/scored), nie copy. Mniej wycieku, mniej recapu w journald.

## Files likely touched

- `influenzer/tick.py` — always-on stdout is status only
- `influenzer/hom_watch.py` — `loop_status` maps envelopes to cisza/admitted/scored
- `tests/test_tick_loop.py`, `tests/test_hom_watch.py` — lock the journald contract

## Test plan

- `uv run python -m unittest tests.test_tick_loop tests.test_hom_watch tests.test_hom_pass tests.test_hom_outbox`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
