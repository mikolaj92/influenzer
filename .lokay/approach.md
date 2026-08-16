# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=59 -->

Repository: `mikolaj92/influenzer`  
Issue: #59 — Pętla Shorts: ostatnia klatka wchodzi w pierwszą

## Goal

Pętla Shorts: ostatnia klatka wchodzi w pierwszą. Draft na fair bez pętli (albo z CTA i pętlą naraz) — cisza. Swipe nagradza rewatch, nie zakończenie. Składa się na haczyk (#36) i jedno-CTA (#42).

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `tests/test_e2e_gates.py`
- `tests/test_hom_draft.py`

## Test plan

- `python3 -m pytest tests/test_e2e_gates.py tests/test_hom_draft.py -q`

## Non-goals

- Not #36 (hook 1–3s) and not #42 (end does not announce the end).
- Do not remap `choose_arena` so Shorts becomes a first costume.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Localize listed only the two test files; inspection put the gate in playbook + score + dress.
