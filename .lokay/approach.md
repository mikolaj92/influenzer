# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=26 -->

Repository: `mikolaj92/influenzer`  
Issue: #26 — Launch to jeden stos 24–48h, nie drugi kąt społeczny

## Goal

Launch to jeden stos 24–48h, nie tydzień kranika. Jeśli w oknie 48h jest już noszalny draft github/hn (nawet po verdict pass), kolejny scan/score nie puszcza drugiego kąta społecznego — changelog albo cisza. Jedna historia, jeden stos.

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
