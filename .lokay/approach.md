# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=135 -->

Repository: `mikolaj92/influenzer`  
Issue: #135 — Konkurs nie jest kątem

## Goal

Konkurs nie jest kątem. Giveaway, raffle, „RT to win”, nagroda za follow = cisza. To nie produkt.

## Files likely touched

- `influenzer/playbook.py` — contest detector (`CONTEST_RE`, `looks_like_contest`) and `unquotable_reason`
- `influenzer/hom.py` — score a contest brief as kill
- `influenzer/hom_draft.py` — refuse to dress a leaked contest draft
- `tests/test_hom_operator.py` — detector + score kill
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Do not treat "follow the README" / "star the repo after you try it" as a contest.
- Do not start collection or publish.

## Notes

- Same fail-closed shape as #114 (engagement bait) and #130 (hire/fundraise): playbook regex, score kill, dress silence.
- Neighbors: #28 (no begging for stars/RT) is a gesture ask; this issue is a contest, not a gesture.
