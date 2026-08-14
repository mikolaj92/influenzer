# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=102 -->

Repository: `mikolaj92/influenzer`  
Issue: #102 — Look nie klonuje

## Goal

Look nie klonuje. Survey/feedback tylko przez gh api, zero `git clone` / worktree na hoście. Mini nie jest cache’em checkoutów.

## Files likely touched

- `github_survey/survey.py` — fail-closed latch: survey/feedback only through gh api; `git clone` / worktree is silence
- `github_feedback/feedback.py` — same latch on inbound comments
- `influenzer/brief_scan.py` — look compose reuses the latch; Mini is not a checkout cache
- `influenzer/scan_due.py`, `influenzer/hom_pass.py`, `influenzer/hom_watch.py`, `influenzer/hom_feedback.py` — document the refuse list

## Test plan

- `python3 -m unittest tests.test_github_survey tests.test_github_feedback tests.test_scan_due tests.test_hom_feedback tests.test_hom_pass tests.test_hom_watch tests.test_brief_scan_cli tests.test_scan_path`

## Non-goals

- Do not grow `github_survey/gh.py` (owned by sibling isolation issues).
- Do not clone, worktree, or cache checkouts on the mini.
- Do not post, comment, label, or write on GitHub.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
