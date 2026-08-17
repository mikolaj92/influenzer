# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=87 -->

Repository: `mikolaj92/influenzer`  
Issue: #87 — Revert w tym samym oknie zabija ship

## Goal

Revert w tym samym oknie zabija ship. Jeśli look widzi merge i revert tego samego — nie claims_ship, nie Show HN. Nie reklamujemy rzeczy, której już nie ma na main.

## Files likely touched

- `github_pack/pack.py`
- `tests/test_github_pack.py`
- `tests/test_e2e_gates.py`

## Test plan

- `python -m unittest tests.test_github_pack tests.test_e2e_gates.OrderedLiveGateTests.test_same_window_revert_is_not_a_ship_or_show_hn`

## Non-goals

- Do not advertise a thing that is already gone from main.
- Do not teach HoM/draft a second revert gate; pack fail-closed is enough.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
