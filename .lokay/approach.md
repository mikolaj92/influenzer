# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=97 -->

Repository: `mikolaj92/influenzer`  
Issue: #97 — Look/pass nie publikuje nawet przy live_enabled

## Goal

Look/pass/angle nie publikują nawet gdy ktoś włączy live_enabled. Ściana dry-run: adapterów nie ma na tej ścieżce. Live to osobny, jawny grant+intent, nie „przy okazji poniedziałku”.

## Files likely touched

- `influenzer/effector.py` — look/pass/angle names stay dry-run even if a caller sets dry_run=False / live_enabled
- `influenzer/scheduler.py` — `score_only=True` drops due plans and never dispatches adapters
- `influenzer/hom_pass.py` — look/pass scores via `tick(..., score_only=True)`
- `influenzer/hom_outbox.py` — angle stays a read; no adapters
- `tests/test_envelope.py` — effector lock
- `tests/test_operator.py` — score-only tick ignores live + due plans
- `tests/test_hom_pass.py` — live_enabled look does not resolve adapters

## Test plan

- `uv run python -m unittest tests.test_envelope tests.test_operator tests.test_hom_pass tests.test_hom_outbox`

## Non-goals

- Do not add a new costume / ads path
- Do not make look/pass/angle a live publisher when grant+intent exist
- Do not change the explicit scheduler live path (`tick` without `score_only`)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Lock is on the effector / score-only tick, not a new costume.
