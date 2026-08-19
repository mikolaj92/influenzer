# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=45 -->

Repository: `mikolaj92/influenzer`  
Issue: #45 — Głos się nie miesza, cross-dress = cisza

## Goal

W `influenzer/hom.py` funkcja `apply_brief` (ok. L1064).

## Files likely touched

- `influenzer/hom.py`
- `tests/test_hom_operator.py`

## Test plan

- `tests/test_hom_operator.py` funkcja `test_cross_project_dress_is_silence`:
- brief `project_id="app-1"`, `apply_brief(..., project_id="builder-1")` → `draft is None`, `reason == "voice_cross_dress"`.
- `project_id="app-1"` → nie ten reason.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
