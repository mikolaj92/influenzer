# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=107 -->

Repository: `mikolaj92/influenzer`  
Issue: #107 — Dziecko gh dostaje allowlistę env, nie cały świat

## Goal

Dziecko gh dostaje allowlistę env, nie cały świat. Żadnego przecieku sekretów hosta do procesu. Tylko to, czego gh musi mieć.

## Files likely touched

- `github_survey/gh.py` — `run_gh` is the only `gh` spawn; it inherited the host world. Isolation lives next to cwd (#108) and argv (#106).
- `tests/test_github_survey.py` — assert allowlisted env, reject host secrets, fail closed

`github_survey` must not import Influenzer. Isolation lives next to `run_gh`.

## Test plan

- `uv run python -m pytest tests/test_github_survey.py -q`

## Non-goals

- Adapter subprocess env (`influenzer/adapters/subprocess_harness.py`)
- GET allowlist in GhRunner (#105)
- Argv list (#106) and cwd isolation (#108)
- Letting `github_survey` import `influenzer.security`

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Fail-closed: env outside the allowlist does not reach the child; an env that is not isolated is silence (no spawn).
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
