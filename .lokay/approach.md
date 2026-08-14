# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=136 -->

Repository: `mikolaj92/influenzer`  
Issue: #136 — Wątek 1/n nie jest kątem

## Goal

Wątek 1/n nie jest kątem. Numeracja, „thread”, storm = cisza. Jeden post, nie serial.

## Files likely touched

- `influenzer/playbook.py` — fail-closed `looks_like_thread_serial` (1/n, launch/tweet thread, storm)
- `influenzer/hom.py` — score kills a serial brief
- `influenzer/hom_draft.py` — dress refuses a serial even if score says draft
- `tests/test_hom_operator.py` — detector + score tests
- `tests/test_hom_draft.py` — dress-time silence tests

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not kill sitting in an HN thread ("camp the thread") or "rising threads".
- Do not invent a multi-post serial publisher.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Distinct from #44 (one story for the whole machine) and #50 (after Show HN we sit in the thread).
