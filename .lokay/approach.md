# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=106 -->

Repository: `mikolaj92/influenzer`  
Issue: #106 — gh leci listą argv, nigdy przez shell

## Goal

gh leci listą argv, nigdy przez shell. Slug watcha walidowany zanim trafi do procesu. Żadnej interpolacji stringa z bazy.

## Files likely touched

- `github_survey/gh.py` — `run_gh` is the only `gh` spawn; lock argv list + `shell=False`, refuse a shell string or a bad slug before spawn
- `influenzer/hom_watch.py` — a poisoned watch slug from the database is silence, not a process
- `tests/test_github_survey.py` — argv list, never shell; bad slug is silence
- `tests/test_hom_watch.py` — poisoned `hom_watch.repo_slug` does not reach gh

`github_survey` must not import Influenzer. Isolation lives next to `run_gh`.

## Test plan

- `uv run python -m pytest tests/test_github_survey.py tests/test_hom_watch.py -q`

## Non-goals

- Adapter subprocess argv (`influenzer/adapters/subprocess_harness.py`)
- GET allowlist in GhRunner (#105)
- Child env allowlist (#107) and cwd isolation (#108)
- Letting `github_survey` import `influenzer`

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Fail-closed: gh only as an argv list; a bad watch slug is silence and does not reach the process; a string from the database does not compose a command.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
