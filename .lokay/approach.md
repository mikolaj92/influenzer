# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=177 -->

Repository: `mikolaj92/influenzer`  
Issue: #177 — Bez profilu marki milczymy

## Goal

W `influenzer/hom.py` funkcja `apply_brief` (ok. L1064).

## Files likely touched

- `influenzer/hom.py`
- `tests/test_hom_operator.py`

## Test plan

- `tests/test_hom_operator.py` funkcja `test_empty_brand_is_silence`:
- `BrandProfile(display_name="", voice="product", ...)` + brief major/tryable → `decision.draft is None` i `reason == "empty_brand"`.
- `display_name="Influenzer"` `voice="product"` → `decision.draft is not None`.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
