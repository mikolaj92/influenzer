# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=116 -->

Repository: `mikolaj92/influenzer`  
Issue: #116 — Nie kopiemy w innych

## Goal

Nie kopiemy w innych. Draft który wyśmiewa cudzy projekt = cisza. Wolno nazwać poprzednika i powiedzieć czym się różnimy albo że warto mu pomóc. Nie wolno dunka.

## Files likely touched

- `influenzer/playbook.py` — fail-closed dunk detector (`looks_like_dunk`)
- `influenzer/hom.py` — score kill `dunking`
- `influenzer/hom_draft.py` — dress-time silence even if score leaks draft
- `tests/test_hom_operator.py` — detector + score cases
- `tests/test_hom_draft.py` — undress even when score says draft

## Test plan

- `uv run --extra dev python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py`

## Non-goals

- #43 (nie reklamujemy gorszego klona): existence / worse-clone, not tone
- No LLM classifier; keep the same regex/table style as press-release and superlative

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Naming a predecessor plus a difference, or offering help, must still draft.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
