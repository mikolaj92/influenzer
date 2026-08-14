# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=107 -->

Repository: `mikolaj92/influenzer`  
Issue: #107 — Dziecko gh dostaje allowlistę env, nie cały świat

## Goal

The gh child process gets an env allowlist, not the host world. Host secrets
do not reach the process. Only what gh must have. An env outside the
allowlist is silence, not a spawn.

Sits next to #105 (GET allowlist) and #106 (argv, never shell). This latch
is the process environment.

## Files likely touched

- `github_survey/gh.py` — spawn site; build and latch the child env
- `tests/test_github_survey.py` — allowlist vs host secrets; leak is silence

## Test plan

- `python -m pytest tests/test_github_survey.py -q`

## Non-goals

- Do not inherit `os.environ` wholesale.
- Do not load Influenzer from `github_survey`.
- Do not change argv (#106) or cwd (#108) latches.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Localize seed listed `influenzer/*`; inspection found the spawn in `github_survey/gh.py` (same latch as #105/#106/#108).
