# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=88 -->

Repository: `mikolaj92/influenzer`  
Issue: #88 — Dwa watche na to samo repo to jeden look

## Goal

Dwa watche na to samo repo to jeden look. Nie dwa briefy i dwa kąty z jednego gita, nawet gdy project_id różne. Drugi watch milczy.

## Files likely touched

- `influenzer/scan_due.py` — look watermark is per git, not per project_id
- `influenzer/brief_admit.py` — already_told is machine-wide for the same artifact URLs
- `influenzer/storage.py` — list_briefs() can read every project
- `influenzer/hom_watch.py` — same-repo second watch stays silent
- tests for admit / scan-due / pass / watch

## Test plan

- `tests/test_brief_admit.py` — second project, same git = already_told
- `tests/test_scan_due.py` — other project's watermark is not due
- `tests/test_hom_watch.py` — switching watch to another project on the same repo does not look again
- `tests/test_hom_pass.py` — second project_id on the same repo is silence, no second angle

## Non-goals

- Machine-wide one-story lock across *different* repos (#44)
- Process lock for a second tick instance (#80)
- Multi-row watch inventory; v1 watch table stays singleton

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
