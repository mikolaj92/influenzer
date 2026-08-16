# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=75 -->

Repository: `mikolaj92/influenzer`  
Issue: #75 — Zarchiwizowane repo jest martwe, nie launchujemy muzeum

## Goal

Zarchiwizowane albo disabled repo jest martwe. Watch na archived → look milczy. Nie launchujemy muzeum.

## Files likely touched

- `github_survey/survey.py` — fail-closed on `isArchived` / disabled meta before a look is a feast
- `influenzer/brief_scan.py`, `influenzer/brief_admit.py`, `influenzer/hom_feedback.py` — watch/scan/admit stay silent
- `influenzer/playbook.py`, `influenzer/hom.py`, `influenzer/hom_draft.py` — kill / undress a museum launch

## Test plan

- `tests/test_github_survey.py`, `tests/test_brief_admit.py`, `tests/test_hom_feedback.py`
- `tests/test_hom_operator.py`, `tests/test_hom_draft.py`

## Non-goals

- Do not start a collection job. Do not launch, publish, or clone.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
