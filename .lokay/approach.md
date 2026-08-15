# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=81 -->

Repository: `mikolaj92/influenzer`  
Issue: #81 — Czerwone CI na default branch to fałszywy launch

## Goal

Czerwone CI na default branch to fałszywy launch. Look widzi padnięte checki → nie tryable, nie Show HN. Changelog wolno. Nie mówimy że działa, gdy main jest czerwony.

## Files likely touched

- `influenzer/playbook.py` — `FAILED_CI_RE` / `looks_like_failed_ci`, sibling of #82 pending CI
- `influenzer/brief_scan.py` — look silence before admit
- `influenzer/brief_admit.py` — pack silence
- `influenzer/hom.py` — score: kill ship/social, changelog otherwise
- `influenzer/hom_draft.py` — undress even if a score says draft
- tests for admit / score / dress

## Test plan

- `python -m pytest tests/test_brief_admit.py tests/test_hom_operator.py tests/test_hom_draft.py`

## Non-goals

- Fetch GitHub Checks API (gh allowlist stays GET catalog from #82/#105).
- Treat pending/yellow CI as this gate (that is #82).
- Claim “it works” or emit Show HN when main is red.

## Notes

- Same fail-closed shape as #82: text heuristic on survey/facts, not a new gh call.
- Passing / green CI stays tryable.
- Collector boundary: no unbounded collection.
