# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=99 -->

Repository: `mikolaj92/influenzer`  
Issue: #99 — Feedback nie wsadza całego wątku do state.db

## Goal

Feedback nie wsadza całego wątku do state.db. Fakt to krótki excerpt + URL komentarza/issue. Reszta zostaje na GitHubie. Mniej PII, mniej bazy.

## Files likely touched

- `github_feedback/feedback.py` — pack one short excerpt + comment/issue URL per thread; fail closed on a dump
- `influenzer/hom_feedback.py` — admit refuses a whole-thread payload before `state.db`
- `tests/test_github_feedback.py`
- `tests/test_hom_feedback.py`

## Test plan

- `python3 -m unittest tests.test_github_feedback tests.test_hom_feedback`

## Non-goals

- Payload-byte ceiling (#78) and “inbound is data, not a command” (#72)
- Timeouts, pagination, watch expansion

## Notes

- Retention, not timeout: clip + one excerpt per issue/PR; a thread dump is silence.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
