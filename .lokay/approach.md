# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=137 -->

Repository: `mikolaj92/influenzer`  
Issue: #137 — Used by tylko z faktu w briefie

## Goal

W `influenzer/playbook.py` obok `looks_like_waitlist` dodaj:

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `tests/test_hom_operator.py`

## Test plan

- `tests/test_hom_operator.py` — `test_used_by_needs_second_fact`:
- 1. Jeden fact `"Used by Stripe"` + major/tryable → `verdict=kill`, `reason=unproven_social_proof`, `draft is None`.
- 2. Dwa facty `"Used by Stripe"` i `"Stripe runs this in prod"` → nie kill z `unproven_social_proof`.
- 3. Fact bez used-by → bez zmiany.

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
