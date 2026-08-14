# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=120 -->

Repository: `mikolaj92/influenzer`  
Issue: #120 — Krzykliwy CAPS w tytule = cisza na HN/GitHub

## Goal

Krzykliwy CAPS w tytule = cisza na HN/GitHub. Seminarium nie wrzeszczy. Jedno-dwa słowa akronimu wolno; CAŁY TYTUŁ WIELKIMI nie.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_shouty_title`; whole title uppercase fails closed; 1–2 letter-words allowed
- `influenzer/hom.py` — score HN/GitHub shouty titles as `shouty_title` kill
- `influenzer/hom_draft.py` — refuse to dress a shouty title even if a score already says draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py` — detector + score + dress coverage

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- Title length (#70) or emoji (#115)
- Auto-rewriting shouty titles into sentence case
- Applying the gate to X / LinkedIn / other borrowed-attention costumes

## Notes

- Same fail-closed shape as listicle / store / blog / film: detector in playbook, kill in score, undressable in dresser.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
