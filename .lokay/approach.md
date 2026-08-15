# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=78 -->

Repository: `mikolaj92/influenzer`  
Issue: #78 — Za duży payload z gh to cisza, nie ucztowanie

## Goal

Za duży payload z gh to cisza, nie ucztowanie. README/komentarze/JSON ponad twardy limit bajtów → empty look, pętla żyje. Żadnego 50MB w state.db.

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
