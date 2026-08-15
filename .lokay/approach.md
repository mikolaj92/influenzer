# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=77 -->

Repository: `mikolaj92/influenzer`  
Issue: #77 — Schemat URL jest częścią bramki: tylko https

## Goal

Schemat URL jest częścią bramki. `http://`, `javascript:`, `data:`, `file:` nie są tryable. Tylko `https` na already-allowlisted hoście (`TRYABLE_ARTIFACT_HOSTS`, dziś `github.com`). Inaczej cisza, nie „prawie klikalne”.

## Files likely touched

- `influenzer/playbook.py` — HTTPS + allowlisted-host predicate
- `influenzer/hom.py` — clickable/tryable gate uses that predicate
- `influenzer/hom_draft.py` — Show HN dress refuses almost-clickable schemes
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Host allowlist itself (#76)
- Redirect hops (#93)
- Dead-link status (#92)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
