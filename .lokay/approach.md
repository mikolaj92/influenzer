# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=103 -->

Repository: `mikolaj92/influenzer`  
Issue: #103 — Look nie odpala projektu z watcha

## Goal

Look from a declared watch must not launch or run the project. Tryable is a
README+URL heuristic, not a process we spawned. Foreign and our code in look
is untrusted. Launching the project on watch is silence.

## Files likely touched

- `influenzer/brief_scan.py` — fail-closed latch: launch/run argv is silence
- `influenzer/brief_admit.py` — tryable = README+URL, never "we ran it"
- `influenzer/hom_watch.py`, `influenzer/hom_pass.py`, `influenzer/scan_due.py`,
  `influenzer/hom_feedback.py` — refuse list
- `README.md`, `github_pack/README.md`, `github_survey/README.md`,
  `github_feedback/README.md` — document the latch
- `tests/test_brief_admit.py`, `tests/test_hom_watch.py` — lock the contract

## Test plan

- `python3 -m unittest tests.test_brief_admit tests.test_hom_watch tests.test_hom_pass tests.test_scan_due tests.test_hom_feedback tests.test_github_pack tests.test_brief_scan_cli`

## Non-goals

- Do not clone or make a worktree (owned by #102).
- Do not post, comment, label, or write on GitHub (owned by #104).
- Do not execute README install commands to prove tryable.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
