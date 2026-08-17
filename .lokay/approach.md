# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=145 -->

Repository: `mikolaj92/influenzer`  
Issue: #145 — Mgła nie jest kątem

## Goal

Mgła nie jest kątem. Subtweet, „you know who”, aluzja bez artefaktu = cisza. Albo konkret, albo nic.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `influenzer/brief_admit.py`
- `github_pack/classify.py`
- `github_pack/pack.py`
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`
- `tests/test_e2e_gates.py`
- `tests/test_brief_admit.py`
- `tests/test_github_pack.py`

## Test plan

- Detector + `unquotable_reason` for subtweet / you know who / aluzja / mgła
- Score kills fog even with a ship URL glued on
- Dress refuses a leaked draft of the same shape
- Pack and admit fail closed
- Named predecessor / unlike Loki still drafts

## Non-goals

- Do not treat dunk (#116) or world commentary (#131) as this gate
- Do not start a collector or wait for collection

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Neighbor of #116 (nie kopiemy w innych) and #131 (komentarz świata). Here it is the hint, not the dunk.
