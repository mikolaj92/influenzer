# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=52 -->

Repository: `mikolaj92/influenzer`  
Issue: #52 — Trwałe Q&A nie idzie w Discord search

## Goal

Pytanie z feedbacku, które ma żyć (how-to, bug, decyzja) → GitHub (issue/Discussions), nie tawerna. Discord tylko na merge/celebrację. Score nie wybiera discord dla `hard_issue`.

## Files likely touched

- `tests/test_e2e_gates.py` — lock the existing Discord story-kind gate: `hard_issue` / durable Q&A is GitHub or silence, never a tavern draft.

## Test plan

- `python -m unittest tests.test_e2e_gates -v`

## Non-goals

- No playbook / scorer rewrite: `ARENA_GATES[DISCORD].allowed_story_kinds` is already `{MAJOR}`, so `hard_issue` and `decision` already die with `discord_pre_pmf` even on a living tavern.
- Do not change `choose_arena` sitting on preferred Discord (same #57 pattern: sit so the gate can fire).
- Do not publish. Do not go live.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Production already fails closed. The e2e gap was the missing lock that a living tavern still cannot carry how-to / bug / decision.
- Default `hard_issue` (no preferred arena) drafts the GitHub workshop.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
