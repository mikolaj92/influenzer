# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=38 -->

Repository: `mikolaj92/influenzer`  
Issue: #38 — Decyzje nie mieszkają na Discordzie

## Goal

`story_kind=decision` → warsztat (GitHub), nigdy tawerna. Discord celebruje merge, nie uchwałę. Durable Q&A idzie do Discussions, nie w search discorda.

## Files likely touched

- `influenzer/playbook.py` — small `choose_arena` sit-exception
- `skills/influenzer-discord/SKILL.md`
- `tests/test_e2e_gates.py`

## Test plan

- `python -m unittest tests.test_e2e_gates.OrderedLiveGateTests.test_decision_does_not_sit_on_discord tests.test_e2e_gates.OrderedLiveGateTests.test_durable_qa_does_not_go_to_discord_search tests.test_e2e_gates.OrderedLiveGateTests.test_empty_tavern_does_not_get_an_invite`

## Non-goals

- Live publish
- Moving durable Q&A (that's #52)
- New Discord story-kind reason; reuse existing workshop fallthrough

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Small block on `choose_arena`: preferred Discord sits for merge/celebration, not for `story_kind=decision`.
