# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=105 -->

Repository: `mikolaj92/influenzer`  
Issue: #105 — GhRunner: pozytywna allowlista, tylko odczyt

## Goal

GhRunner has a positive allowlist: read-only catalog (`repo view`, `pr list`,
`release list`, GET `api`). Any other argv is silence, not a comment, label,
close, or push. The catalog is the latch in the runner, like the effector
catalog — compose does not decide what may spawn.

## Files likely touched

- `github_survey/gh.py` — allowlist + `run_gh` latch
- `tests/test_github_survey.py` — read catalog vs write argv

## Test plan

- `python -m unittest tests.test_github_survey tests.test_github_feedback`

## Non-goals

- Env allowlist (#107), cwd isolation (#108), argv-vs-shell (#106)
- Teaching survey/feedback new GitHub endpoints
- Writing comments, labels, closes, or pushes

## Notes

- Localize seed `comment/label/close/push` was token noise. GhRunner lives in
  `github_survey/gh.py`; that is the latch, same as #106–#108.
- Collector boundary: no unbounded collection in this patch.
