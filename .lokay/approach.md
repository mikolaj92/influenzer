# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=147 -->

Repository: `mikolaj92/influenzer`  
Issue: #147 — Lead magnet nie jest kątem

## Goal

Lead magnet is not an angle. Ebook / free guide / typeform for an email is
silence, not tryable. Fail closed at score, dress, pack, and admit.

Neighbor of #46 (waitlist is not a ship) and #126 (artifact behind login).
Here the gate is the mail form, not the waitlist.

## Files likely touched

- `influenzer/playbook.py`
- `github_pack/classify.py`
- `github_pack/pack.py`
- `influenzer/brief_admit.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `tests/test_e2e_gates.py`
- `tests/test_brief_admit.py`
- `tests/test_github_pack.py`
- `tests/test_hom_draft.py`
- `tests/test_hom_operator.py`

## Test plan

- Run the smallest useful tests for files touched:
  `tests/test_e2e_gates.py`, `tests/test_brief_admit.py`,
  `tests/test_github_pack.py`, `tests/test_hom_draft.py`,
  `tests/test_hom_operator.py`

## Non-goals

- Do not fold this into waitlist (`join the list` stays #46).
- Do not fold this into login gate (`za logowaniem` stays #126).
- A user guide and email notifications stay.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
