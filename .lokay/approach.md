# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=124 -->

Repository: `mikolaj92/influenzer`  
Issue: #124 — Show HN nie jest kartą na agregatorze

## Goal

Show HN is not a launch-board card. A Product Hunt / BetaList URL, or a
"launch on PH" pitch, is silence on seminar. Link to the thing, not the
launch board. A board next to a repo can stay as evidence.

## Files likely touched

- `influenzer/playbook.py` — `LAUNCH_HOSTS`, `LAUNCH_PITCH_RE`, host/pitch helpers
- `influenzer/hom.py` — HN kill `hn_not_an_aggregator`
- `influenzer/hom_draft.py` — refuse to dress a launch-board URL as Show HN
- `tests/test_hom_operator.py` — host, pitch, only-URL, next-to-repo
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- Do not treat a Product Hunt / BetaList listing as a tryable demo.
- Do not invent new arenas or publish paths.
- A launch card next to a repo can stay as evidence; the board itself is not click-and-run.

## Notes

- Same fail-closed shape as #122 (blog) and #123 (store).
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
