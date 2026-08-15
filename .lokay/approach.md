# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=91 -->

Repository: `mikolaj92/influenzer`  
Issue: #91 — Repo z wyłączonymi issues nie dostaje social launchu

## Goal

Repo z wyłączonymi issues nie dostaje social launchu. Nie ma gdzie usiąść w spike. README/changelog wolno. Show HN i kąt społeczny milczą — nie gramy areny bez obozu.

## Files likely touched

- `influenzer/playbook.py` — fail-closed detector for a closed issue tracker
- `influenzer/hom.py` — score: no Show HN / social arena without a camp; README/changelog stay
- `influenzer/hom_draft.py` — dress: social costumes stay silent; GitHub workshop may still draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py` — detector + score + dress

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not add a `gh` probe or expand survey fields.
- Do not kill README / changelog / GitHub workshop drafts.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
