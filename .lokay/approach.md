# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=114 -->

Repository: `mikolaj92/influenzer`  
Issue: #114 — Bait na klik to nie kąt

## Goal

Bait na klik to nie kąt. „Agree?”, „like if”, „comment one word”, strzałka w dół = cisza. Pytanie z feedbacku jest ok; prośba o gest nie.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_engagement_bait` + `ENGAGEMENT_BAIT_RE`
- `influenzer/hom.py` — score kill `engagement_bait`
- `influenzer/hom_draft.py` — dress fail-closed even if score says draft
- `tests/test_hom_operator.py` — detector + score tests
- `tests/test_hom_draft.py` — dress silence vs feedback question

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- Do not treat a sourced feedback question as bait.
- Do not invent a new costume or arena.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
