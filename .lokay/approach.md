# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=68 -->

Repository: `mikolaj92/influenzer`  
Issue: #68 — Pad gh to cisza, nie śmierć pętli

## Goal

Pad gh (auth, sieć, rate) to cisza, nie śmierć pętli. Survey/feedback zwracają empty i idą spać. Interval żyje. To nie jest crash-w-połowie-stanu (#66) — to provider fail-closed.

## Files likely touched

- `github_survey/gh.py` — classify rate/network pads
- `github_survey/survey.py` — provider pad → empty_survey
- `github_feedback/feedback.py` — provider pad → empty_feedback
- `influenzer/brief_scan.py`, `influenzer/scan_due.py`, `influenzer/hom_feedback.py` — pad is empty, interval lives
- tests for survey/feedback/watch/scan-due

## Test plan

- `tests/test_github_survey.py`, `tests/test_github_feedback.py`
- `tests/test_hom_watch.py`, `tests/test_scan_due.py`, `tests/test_hom_feedback.py`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
