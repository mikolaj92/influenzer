# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=103 -->

Repository: `mikolaj92/influenzer`  
Issue: #103 — Look nie odpala projektu z watcha

## Goal

Look does not run the watched project. Launching on watch is silence.
Tryable is a README+URL heuristic. Foreign and our own code in look is
untrusted.

Sits next to #102 (look does not clone). This latch is the live run.

## Files likely touched

- `github_survey/survey.py` — fail-closed latch: `uv`/`npm`/`make`/`docker`/interpreter is silence, not a spawn
- `github_pack/classify.py`, `github_pack/pack.py` — tryable = README+URL only; a release is not a run
- `influenzer/brief_admit.py` — do not invent tryable; missing flag is silence
- `influenzer/brief_scan.py`, `influenzer/scan_due.py`, `influenzer/hom_pass.py`, `influenzer/hom_watch.py`, `influenzer/hom_feedback.py` — document the refuse list
- `README.md`, `github_pack/README.md`, `github_survey/README.md`, `github_feedback/README.md` — same latch in prose

## Test plan

- `python3 -m unittest tests.test_github_survey tests.test_github_pack tests.test_brief_admit tests.test_hom_watch tests.test_hom_pass tests.test_scan_due tests.test_hom_feedback tests.test_scan_path`

## Non-goals

- Do not clone or worktree (#102).
- Do not fetch the demo URL or run README install commands.
- Do not grow `github_survey/gh.py` (owned by sibling isolation issues).
- Do not post, comment, label, or write on GitHub.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Inspection refined tryable from "any release" to README+URL; launching the project stays silence.
