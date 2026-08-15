# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=161 -->

Repository: `mikolaj92/influenzer`  
Issue: #161 — Domyślna strona serwera nie jest produktem

## Goal

Domyślna strona serwera nie jest produktem. Welcome to nginx, Apache default, Caddy placeholder = cisza.

## Files likely touched

- `influenzer/playbook.py` — splash detector + wave copy
- `influenzer/hom.py` — score/gate kill
- `influenzer/hom_draft.py` — dresser fail-closed
- `tests/test_hom_operator.py` — detector + score tests
- `tests/test_hom_draft.py` — dress tests

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not probe live hosts. Do not treat a parked domain (#157) or a broken site (#25) as this gate. A working nginx/Apache/Caddy config stays.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
