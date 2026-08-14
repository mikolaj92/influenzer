# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=110 -->

Repository: `mikolaj92/influenzer`  
Issue: #110 — SQL tylko przez bind, zero sklejania stringów

## Goal

SQL tylko przez bind. Zero sklejania stringów z slugów, excerptów, JSON-a z gh. Inbound nie staje się zapytaniem.

## Files likely touched

- `influenzer/storage.py` — bind-only execute latch; drop f-string draft filter
- `tests/test_persistence.py` — inbound slug / excerpt / gh JSON stay bound

## Test plan

- `python -m unittest tests.test_persistence tests.test_hom_feedback tests.test_brief_admit tests.test_hom_verdict tests.test_hom_watch tests.test_operator tests.test_x_handoff tests.test_e2e_gates tests.test_hom_outbox tests.test_scan_due -q`

## Non-goals

- No schema / collector / watch-widening changes
- Do not rewrite call sites that already bind

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Fail-closed: spliced inbound SQL raises `UnboundSqlError` (a `StorageError`); admit paths already turn `StorageError` into silence.
- Static SQL stays allowlisted (`pending`, `now`, empty `coalesce` literal). Migrations keep the raw connection so schema scripts are unchanged.
