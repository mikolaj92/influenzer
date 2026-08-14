# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=107 -->

Repository: `mikolaj92/influenzer`  
Issue: #107 — Dziecko gh dostaje allowlistę env, nie cały świat

## Goal

The gh child process gets a positive env allowlist, never the host world.
Host secrets do not inherit. Only what gh must have (PATH/HOME/locale/tmp
plus GH_TOKEN/GITHUB_TOKEN). An env outside that allowlist is silence,
not a spawn.

## Files likely touched

- `github_survey/gh.py` — same latch as #106 (argv) and #108 (cwd)
- `tests/test_github_survey.py`

## Test plan

- `python -m pytest tests/test_github_survey.py -q`

## Non-goals

- Do not import influenzer from github_survey
- Do not change adapter/subprocess child env (#107 is the gh child)
- Do not start a collector

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Sibling latches: #105 GET allowlist, #106 argv not shell, #108 empty temp cwd.
- Fail-closed: extra env keys → no spawn (look = silence).
