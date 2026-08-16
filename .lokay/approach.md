# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=66 -->

Repository: `mikolaj92/influenzer`  
Issue: #66 — Crash w połowie przebiegu wznawia, nie zaczyna od zera

## Goal

Crash w połowie przebiegu wznawia, nie zaczyna od zera. Pending brief po padzie → tylko score+kąt, bez drugiego survey/gh. Look „już zrobiony” i look „w trakcie” to dwa stany. Drugi gh na półotwartą historię = błąd.

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
