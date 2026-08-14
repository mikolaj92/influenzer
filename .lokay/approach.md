# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=133 -->

Repository: `mikolaj92/influenzer`  
Issue: #133 — Nie wpinamy produktu w cudzą falę

## Goal

Nie wpinamy produktu w cudzą falę. Reply pod postem, który nie jest o naszym watchu/shipie = cisza. Sam parent URL nie wystarczy. To nie dunk i nie echo — to kradzież fali.

## Files likely touched

- `influenzer/playbook.py` — detect a reply under a foreign parent
- `influenzer/hom.py` — score that shape as silence
- `influenzer/hom_draft.py` — refuse to dress a leaked draft of the same shape
- `tests/test_hom_operator.py`, `tests/test_hom_draft.py`

## Test plan

- Reply under a post that is not our watch/ship is killed
- A parent URL alone is not enough
- A parent about our ship can still draft
- Existing dunk / empty-feed / costume tests stay green

## Non-goals

- Live publish, X empty-feed gate (#27), reply-without-new-thought (#41)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
