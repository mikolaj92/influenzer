# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=71 -->

Repository: `mikolaj92/influenzer`  
Issue: #71 — Ten sam tekst nie wychodzi drugi raz

## Goal

Ten sam tekst nie wychodzi drugi raz. Format stosu zostaje, body musi być nowe. Identyczny content_hash co ostatni kąt = cisza. Nie recap, nie copy-paste.

## Files likely touched

- `influenzer/hom.py` — body-only `content_hash`; `drop_repeat_angle`
- `influenzer/storage.py` — `last_angle_body_hash` (held still counts)
- `influenzer/scheduler.py` — tick drops a repeat before persist
- `tests/test_hom_operator.py` — same body is kill; new body still drafts

## Test plan

- `uv run python -m unittest tests.test_hom_operator.TickBriefPathTests tests.test_hom_outbox tests.test_hom_draft.HomDraftCostumeTests`

## Non-goals

- Not #65 (two ticks = one brief) and not #64 (Monday with no history = cisza).
- No fuzzy recap detector. Exact body hash only.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
