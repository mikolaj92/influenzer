# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=53 -->

Repository: `mikolaj92/influenzer`  
Issue: #53 — Show HN pisze człowiek, nie marka

## Goal

Backstory i nick z `BrandProfile.maintainer`, pierwsza osoba. „We at Product announced” = cisza na seminar.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `tests/test_e2e_gates.py`
- `tests/test_product_improvements.py`

`BrandProfile.maintainer` is a field, not a path. Seminar dress uses that nick and first person; brand voice is silence.

## Test plan

- `uv run python -m unittest tests.test_e2e_gates tests.test_product_improvements`

## Non-goals

- Publish / live social
- More than one seminar story

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
