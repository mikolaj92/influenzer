# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=148 -->

Repository: `mikolaj92/influenzer`  
Issue: #148 — Odsłona logo nie jest shipem

## Goal

Odsłona logo nie jest shipem. Rebrand, paleta, moodboard = cisza. To nie produkt.

## Files likely touched

- `influenzer/playbook.py` — `LOGO_REVEAL_RE` / `looks_like_logo_reveal` / `LOGO_REVEAL_NOT_A_SHIP`
- `influenzer/hom.py` — score kill/changelog
- `influenzer/hom_draft.py` — undress rebrand copy
- `github_pack/classify.py` + `github_pack/pack.py` — inbound rebrand silence
- `influenzer/brief_admit.py` — admit fail-closed
- tests for score, dress, pack, admit, e2e

## Test plan

- Run the smallest useful tests for files touched
- `pytest` on logo-reveal cases in `test_e2e_gates`, `test_hom_operator`, `test_hom_draft`, `test_brief_admit`, `test_github_pack`

## Non-goals

- Do not treat a README logo, a Shorts logo intro, or an outro-logo as a rebrand.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Pair of founder journal (#146, lifestyle) and roadmap (#129, a calendar). Here it is the look, not a tryable drop.
