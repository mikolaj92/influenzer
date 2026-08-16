# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=58 -->

Repository: `mikolaj92/influenzer`  
Issue: #58 — Dwór nie jest kanałem launchu

## Goal

Dwór nie jest kanałem launchu. `claims_ship` / Show-HN energia nie idzie na LinkedIn. Court = insight z roboty (filary), nie „właśnie wypuściliśmy”. Ship → github/hn. LinkedIn bez insightu poza launchu = cisza.

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
