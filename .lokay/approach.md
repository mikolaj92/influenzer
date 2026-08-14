# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=134 -->

Repository: `mikolaj92/influenzer`  
Issue: #134 — Zrzut rankingu nie jest artefaktem

## Goal

Zrzut rankingu nie jest artefaktem. HN front, dashboard, licznik gwiazdek w kącie = cisza. Witryna to repo, nie wykres próżności.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not start collecting live HN/star charts. The website stays the repo.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
