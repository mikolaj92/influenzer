# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=24 -->

Repository: `mikolaj92/influenzer`  
Issue: #24 — Compose feedback into the weekly CMO pass

## Goal

`influenzer feedback` is on main. `run_pass` still only does scan-due → tick → angle. The weekly look never **listens**. After hop, 24/7 ships-or-silences but stays deaf unless a human runs `influenzer feedback`. Workshop: sit on the repo.

## Files likely touched

- `tests/test_hom_pass.py`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
