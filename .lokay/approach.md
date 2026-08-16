# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=61 -->

Repository: `mikolaj92/influenzer`  
Issue: #61 — Nie gramy w arenę, której nie umiemy obstawić

## Goal

Nie gramy w arenę, której nie umiemy obstawić. Feedback dziś jest z GitHuba (i obóz HN). Primary kąt = github albo hn. X/LI/YT/shorts/discord/bsky bez słuchacza nie są pierwszym kostiumem — cisza albo changelog. Ship idzie tam, gdzie siedzimy.

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
