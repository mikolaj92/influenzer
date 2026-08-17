# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=41 -->

Repository: `mikolaj92/influenzer`  
Issue: #41 — Reply na X bez nowej myśli = cisza

## Goal

Reply na X bez nowej treści to martwy RT. Przy URL-u rodzica (#27) body musi dodać jedną nową myśl, nie echo i nie sam link. Inaczej cisza na agora. Ratio jest z komentarza, nie z pustego cytatu.

## Files likely touched

- `influenzer/playbook.py` — agora_reason / preferred X sits
- `influenzer/hom.py` — score kills X reply without a new thought
- `influenzer/hom_draft.py` — dress skips parent echo, fails closed
- `tests/test_e2e_gates.py` — one-story silence lock
- `tests/test_hom_draft.py` — reply under our ship wears the new thought

## Test plan

- `pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_x_reply_without_a_new_thought_is_silence`
- nearby preferred-X / reply-under-our-ship dress tests

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
