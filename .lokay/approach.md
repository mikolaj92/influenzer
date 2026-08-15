# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=100 -->

Repository: `mikolaj92/influenzer`  
Issue: #100 — Inbound nie poszerza watcha

## Goal

Inbound nie poszerza watcha. Link do cudzego repo w issue zostaje tekstem, nie nowym surveyem. Look zostaje na zadeklarowanym repo.

## Files likely touched

- `github_survey/survey.py` — look stays on the declared repo; foreign argv is silence
- `influenzer/brief_scan.py` — host compose wraps look with the declared slug
- `influenzer/hom_feedback.py` — inbound collect does not survey a foreign slug
- `influenzer/hom_watch.py`, `influenzer/scan_due.py`, `influenzer/hom_pass.py` — refuse inbound expanding watch

## Test plan

- `tests/test_github_survey.py` — foreign slug is silence; issue body stays text
- `tests/test_hom_watch.py` — due look does not change the declared watch
- `tests/test_hom_feedback.py` — inbound foreign link stays excerpt text

## Non-goals

- Do not grow excerpt retention (#99)
- Do not invent a second watch from inbound

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
