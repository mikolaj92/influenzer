# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=117 -->

Repository: `mikolaj92/influenzer`  
Issue: #117 — Superlatyw bez dowodu milczy

## Goal

Superlatyw bez dowodu milczy. „Revolutionary”, „world’s first”, „AI-powered” bez tryable artefaktu = cisza. To gimmick, nie historia. Dowód albo nic.

## Files likely touched

- `influenzer/playbook.py` — detect revolutionary / world's first / AI-powered
- `influenzer/hom.py` — kill a superlative without a tryable ship artifact
- `influenzer/hom_draft.py` — stay silent even if a forged score says draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py`

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Do not relax press-release tone (#29). Revolutionary with proof still dies on social as PR tone.
- Do not invent a new publish path. Score/dress only.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
