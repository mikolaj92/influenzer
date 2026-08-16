# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=74 -->

Repository: `mikolaj92/influenzer`  
Issue: #74 — Prywatne repo nie jest witryną

## Goal

Prywatne repo nie jest witryną. Watch na private → look milczy (nawet gdy owner nasz). Warsztat to publiczny README. Survey i tak public — tu fail-closed na watch, nie 404 w pętli.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_private_repo` + workshop/HN copy
- `influenzer/brief_scan.py` — `repo_is_private` before survey, payload gate
- `influenzer/brief_admit.py` / `influenzer/hom_feedback.py` — admit silence
- `influenzer/hom.py` / `influenzer/hom_draft.py` — score/dress kill
- `github_survey/survey.py` — keep `private_repo` fail-closed (visibility too)
- READMEs — workshop is a public README

## Test plan

- `tests/test_brief_admit.py` private look/pack
- `tests/test_hom_feedback.py` private look
- `tests/test_hom_operator.py` detector + kill
- `tests/test_hom_draft.py` undressable
- `tests/test_github_survey.py` private survey

## Non-goals

- Do not start a 404 retry loop.
- Do not treat owner-is-ours as an exception.
- Do not expand survey beyond public GitHub.

## Notes

- Same fail-closed shape as #90 fork, #89 empty, #75 archived.
- Survey already returned `private_repo`; watch/look/score/dress now match.
