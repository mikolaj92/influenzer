# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=108 -->

Repository: `mikolaj92/influenzer`  
Issue: #108 — cwd dziecka gh to pusta tymczasowa, nie HOME

## Goal

cwd dziecka gh to pusta tymczasowa, nie HOME i nie checkout z plikami hosta. Proces nie widzi lokalnych plików hosta przez przypadek.

## Files likely touched

- `github_survey/gh.py` — `run_gh` is the only `gh` spawn; it inherited the host cwd
- `tests/test_github_survey.py` — assert empty temp cwd, reject HOME/checkout, fail closed

`github_survey` must not import Influenzer. Isolation lives next to `run_gh`.

## Test plan

- `uv run python -m pytest tests/test_github_survey.py -q`

## Non-goals

- Adapter subprocess cwd (`influenzer/adapters/subprocess_harness.py`)
- Env allowlist (#107)
- Letting `github_survey` import `influenzer.security`

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Fail-closed: cwd outside an empty system temp, or equal to HOME / host cwd, is silence (no spawn).
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
