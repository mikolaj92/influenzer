# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=43 -->

Repository: `mikolaj92/influenzer`  
Issue: #43 — Nie reklamujemy gorszego klona

## Goal

Jeśli fakty mówią, że ktoś już to zrobił lepiej (albo „znowu wymyśliliśmy X”) — score zabija kąt społeczny. Changelog albo cisza. Albo pomóc tamtemu, albo mieć wyraźnie lepszy pomysł. To mandat, nie kostium.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_worse_clone` detector + reason
- `influenzer/hom.py` — score kills social / changelog otherwise
- `influenzer/hom_draft.py` — leaked DRAFT still undressable
- `tests/test_e2e_gates.py` — e2e lock for kill / changelog / better-idea draft

## Test plan

- Run `tests/test_e2e_gates.py` plus the predecessor/dunk operator cases

## Non-goals

- Do not dunk a predecessor (already covered).
- Do not silence a named difference or an offer to help.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent refined the file list after inspection: localize seed was only the e2e test, but the mandate is a score-level gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
