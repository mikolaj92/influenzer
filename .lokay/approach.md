# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=159 -->

Repository: `mikolaj92/influenzer`  
Issue: #159 — Tag a friend to cisza

## Goal

„Tag a friend” to cisza. Send this to, quote this, chain = bait, nie produkt.

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
