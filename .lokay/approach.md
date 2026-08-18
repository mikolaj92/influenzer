# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=167 -->

Repository: `mikolaj92/influenzer`  
Issue: #167 — Karta zanim produkt nie jest tryable

## Goal

A card, payment, or paid subscription before the product is not tryable.
“Subscribe to continue” on the artifact is silence; Show HN must not ask a
stranger for a wallet before they can try the product.

## Files likely touched

- `influenzer/host.py` — payment-gate evidence detector and tryable reason
- `influenzer/hom.py` / `influenzer/hom_draft.py` — score and dress fail closed
- `github_pack/classify.py` / `github_pack/pack.py` — README/release pack fails closed
- `skills/influenzer-hn/SKILL.md` / `influenzer/playbook.py` — document the HN gate
- `tests/test_e2e_gates.py` / `tests/test_github_pack.py` — focused regressions

## Test plan

- Run the payment-gate tests in `tests/test_e2e_gates.py` and `tests/test_github_pack.py`
- Run the complete touched test modules when practical

## Non-goals

- No live artifact probing or payment-provider integration
- Do not reject products that merely implement billing/card features
- Do not reject an explicitly card-free trial

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
