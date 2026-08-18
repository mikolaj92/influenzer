# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=149 -->

Repository: `mikolaj92/influenzer`  
Issue: #149 — Sztuczny FOMO nie jest kątem

## Goal

Sztuczny FOMO nie jest kątem. „Only N spots”, countdown, last chance = cisza. To nie produkt.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `influenzer/brief_admit.py`
- `github_pack/classify.py`
- `github_pack/pack.py`
- `tests/test_e2e_gates.py`
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`
- `tests/test_brief_admit.py`
- `tests/test_github_pack.py`

## Test plan

- Run the smallest useful tests for files touched: playbook detector, score, dress, pack, admit

## Non-goals

- Do not treat waitlist, click-bait, or a contest as this gate
- Do not start a collection job

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
