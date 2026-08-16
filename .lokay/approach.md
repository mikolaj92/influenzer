# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=63 -->

Repository: `mikolaj92/influenzer`  
Issue: #63 — Formatu nie zmieniamy, póki żyje stos

## Goal

Formatu nie zmieniamy, póki żyje. Jak stos wybrał github albo hn, następny look w tym stosie trzyma ten kostium. Żadnego shoppingu aren dla urozmaicenia. Zmiana dopiero po hold albo po śmierci okna.

## Files likely touched

- `influenzer/playbook.py` — `choose_arena` plus 48h living-stack lock
- `influenzer/hom.py` — score/apply keep the locked costume; explicit other arena is kill
- `influenzer/storage.py` — open unheld github/hn draft is the living stack
- `influenzer/scheduler.py` — tick passes the living stack into apply_brief
- `tests/test_hom_operator.py` — keep / shop / hold / dead-window cases

## Test plan

- `uv run python -m unittest tests.test_hom_operator tests.test_hom_draft tests.test_hom_verdict tests.test_hom_outbox tests.test_hom_pass tests.test_tick_loop tests.test_persistence tests.test_policy`

## Non-goals

- Shopping other arenas (x, reddit, …) while github/hn lives
- Refreshing the 48h window from later looks in the same stack
- Changing costume without hold or a dead window

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Pair of #61 (primary github/hn) and #26 (stos 48h).
