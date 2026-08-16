# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=62 -->

Repository: `mikolaj92/influenzer`  
Issue: #62 — Rytm CMO to poniedziałek, nie toczące się 7 dni

## Goal

Rytm CMO to poniedziałek (Europe/Warsaw), nie toczące się 7 dni. Look (scan-due / pass gdy pora) w inne dni milczy społecznie; tick może score’ować. Środa bo minęło 168h to nie ten rytm.

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
