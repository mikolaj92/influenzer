# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=80 -->

Repository: `mikolaj92/influenzer`  
Issue: #80 — Jedna pętla na jeden state.db

## Goal

Jedna pętla na jeden state.db. Druga instancja ticka (ręczna + always-on) dostaje lock i wychodzi ciszą, nie robi drugiego looku. Advisory lock jak u Lokaya, nie dwa CMO w jednym domu.

## Files likely touched

- `influenzer/storage.py` — OS advisory lock beside `state.db` (`tick.lock`, non-blocking `fcntl.flock`)
- `influenzer/tick.py` — always-on / `--once` holds the lock for the process; overlap prints cisza and exits
- `influenzer/tick_all.py` — one-shot mutator takes the same lock; overlap is cisza, no look
- `influenzer/hom_pass.py` / `influenzer/cli.py` — manual CMO look takes the same lock
- `tests/test_tick_loop.py`, `tests/test_hom_pass.py`, `tests/test_persistence.py`

## Test plan

- `python -m unittest tests.test_tick_loop tests.test_persistence tests.test_hom_pass tests.test_hom_watch`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
