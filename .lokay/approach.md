# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=123 -->

Repository: `mikolaj92/influenzer`  
Issue: #123 — Show HN nie jest sklepem

## Goal

Show HN nie jest sklepem. App Store / Play / TestFlight / „download the app” = cisza na seminar. Klik-i-odpal w przeglądarce albo repo, nie bramka sklepu.

## Files likely touched

- `influenzer/playbook.py` — store hosts + “download the app” pitch
- `influenzer/hom.py` — seminar kill `hn_not_a_store`
- `influenzer/hom_draft.py` — refuse to dress a store URL / store pitch as Show HN
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not treat a waitlist, blog, or film (those are #46 / #122 / #125).
- A store URL next to a repo can stay as evidence; the store itself is not click-and-run.

## Notes

- Same fail-closed shape as #125 (`hn_not_an_episode`): host table + gate + undressable draft.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
