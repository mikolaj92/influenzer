# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=142 -->

Repository: `mikolaj92/influenzer`  
Issue: #142 — Prompt i I asked ChatGPT nie są kątem

## Goal

Prompt i „I asked ChatGPT” nie są kątem. Dump rozmowy z modelem, „as an AI” = cisza. HoM nie jest modelem w kadrze.

Neighbor of #117 (AI-powered slogan without proof). This issue is the model in the frame, not the slogan.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_model_in_frame`, model-chat hosts, `unquotable_reason`
- `influenzer/hom.py` — score kill `model_in_frame`
- `influenzer/hom_draft.py` — undressable even when a fake score says draft
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`
- `tests/test_e2e_gates.py`

## Test plan

- Detector: I asked ChatGPT / as an AI / prompt dump / zrzut rozmowy z modelem / chat.openai.com = silence
- Negative: AI-powered slogan, "prompt the operator", Claude Shannon, GPT tokenizer still draft
- Dress refuses a model dump even when score is forced to DRAFT
- Superlative (#117) still works independently

## Non-goals

- Do not kill an honest "AI-powered" slogan that already has a tryable artifact (#117)
- Do not change arena seating / costume choice
- No collector / no live publish

## Notes

- Same fail-closed shape as #141 (poll) and #132 (private conversation).
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
