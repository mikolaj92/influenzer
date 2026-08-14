# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=131 -->

Repository: `mikolaj92/influenzer`  
Issue: #131 — Komentarz świata nie jest kątem produktu

## Goal

Komentarz świata nie jest kątem produktu. Brief polityczny, kulturalny, news dnia bez artefaktu z repo = cisza. Mówimy co budujemy, nie co myślimy o headlines.

## Files likely touched

- `influenzer/playbook.py` — world-commentary detector (politics / culture / news-of-the-day + news hosts)
- `influenzer/hom.py` — fail-closed score: headlines without a product angle = kill
- `influenzer/hom_draft.py` — refuse to dress a leaked draft of the same shape
- `tests/test_hom_operator.py`, `tests/test_hom_draft.py`

## Test plan

- `uv run pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Do not start collecting headlines or polling news feeds.
- Do not treat a product brief (ship + tryable repo) as world commentary.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
