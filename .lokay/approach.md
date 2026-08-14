# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=120 -->

Repository: `mikolaj92/influenzer`  
Issue: #120 — Krzykliwy CAPS w tytule = cisza na HN/GitHub

## Goal

Krzykliwy CAPS w tytule = cisza na HN/GitHub. Seminarium nie wrzeszczy. Jedno-dwa słowa akronimu wolno; CAŁY TYTUŁ WIELKIMI nie.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_shouting_title` (letter-words only; 1–2 all-caps tokens are acronyms)
- `influenzer/hom.py` — score-time kill on HN/GitHub when the wearable title shouts
- `influenzer/hom_draft.py` — dress-time refuse so a leaked DRAFT still cannot shout
- `tests/test_hom_operator.py` — score + helper cases
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Length limits (neighbor #70)
- Emoji in titles (neighbor #115)
- Other arenas (X, LinkedIn, …)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Fail-closed: whole title in CAPS is silence; one or two acronym words may stay.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
