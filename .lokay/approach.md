# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=39 -->

Repository: `mikolaj92/influenzer`  
Issue: #39 — Nowe issue w oknie launchu to fakt, nie drugi worek

## Goal

Siedzenie na repo w oknie launchu to też nowe issue, nie tylko komentarze. Feedback look pakuje otwarte issue (pytanie/bug) z watch-repo w oknie ~48h do faktów. „+1” / thanks = cisza. Jedna historia. Nie odpowiada sam, nie zamyka ticketów.

## Files likely touched

- `github_feedback/feedback.py` — pack open issues in the ~48h launch window into the existing comment bag
- `github_survey/gh.py`, `github_survey/survey.py` — allowlist/classify the read-only `/issues` GET so the look can see tickets
- `tests/gh_scripts.py`, `tests/test_github_feedback.py`, `tests/test_hom_feedback.py`, `tests/test_hom_watch.py`, `tests/test_e2e_gates.py`

## Test plan

- `python -m unittest tests.test_github_feedback tests.test_hom_feedback tests.test_hom_watch tests.test_github_survey tests.test_e2e_gates`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
