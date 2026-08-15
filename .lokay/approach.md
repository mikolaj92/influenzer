# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=101 -->

Repository: `mikolaj92/influenzer`  
Issue: #101 — Paginacja gh ma sufit

## Goal

Paginacja gh ma sufit. Survey/feedback kończą po N stronach. Nie zjadamy całej historii repo w poniedziałek. Reszta czeka na następne okno albo ginie — look ma być krótki.

## Files likely touched

- `github_survey/survey.py` — fail-closed latch: look stops after `MAX_PAGES`; `--paginate` / huge `--limit` is silence
- `github_feedback/feedback.py` — same short-look wrapper on inbound comments
- `influenzer/brief_scan.py` — look compose reuses the latch
- `influenzer/scan_due.py`, `influenzer/hom_pass.py`, `influenzer/hom_watch.py`, `influenzer/hom_feedback.py` — document the refuse list
- `tests/test_github_survey.py`, `tests/test_github_feedback.py` — ceiling + whole-history silence

## Test plan

- `python3 -m unittest tests.test_github_survey tests.test_github_feedback tests.test_scan_due tests.test_hom_feedback tests.test_brief_scan_cli tests.test_scan_path`

## Non-goals

- Do not grow `github_survey/gh.py` (owned by sibling isolation / timeout / byte-limit issues).
- Do not walk every GitHub page or cache whole-repo history on the mini.
- Do not post, comment, label, or write on GitHub.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Sibling of #78 (byte ceiling) and #79 (timeout). This latch is page count.
