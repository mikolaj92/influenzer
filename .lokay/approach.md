# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=109 -->

Repository: `mikolaj92/influenzer`  
Issue: #109 — state.db i config są 0600, katalog 0700

## Goal

state.db i config są 0600, katalog 0700. Briefy nie są world-readable na wspólnym mini. Inny uid (gość, inny proces) nie czyta kątów z dysku.

## Files likely touched

- (infer from repo inspection)

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
