# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=103 -->

Repository: `mikolaj92/influenzer`  
Issue: #103 — Look nie odpala projektu z watcha

## Goal

Look nie odpala projektu z watcha. Tryable to heurystyka README+URL. Cudzy i nasz kod w looku jest nieufny.

## Files likely touched

- `influenzer/brief_scan.py` — look runner refuses install/start/run argv (silence, not a spawn)
- `influenzer/hom_watch.py`, `hom_pass.py`, `scan_due.py`, `hom_feedback.py` — look contract: no project launch
- `README.md`, `github_survey/README.md`, `github_pack/README.md`, `github_feedback/README.md` — tryable stays README+URL, not a run

## Test plan

- `python3 -m unittest tests.test_hom_watch tests.test_hom_pass tests.test_scan_due tests.test_brief_admit tests.test_brief_scan_cli tests.test_github_pack tests.test_hom_feedback`

## Non-goals

- Do not clone (that is #102). Do not write to GitHub. Do not execute watched project code to decide tryable.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
