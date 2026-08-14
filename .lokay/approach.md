# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=130 -->

Repository: `mikolaj92/influenzer`  
Issue: #130 — Hire i fundraise to nie kąt produktu

## Goal

Hire i fundraise to nie kąt produktu. Brief o rekrutacji, rundzie, offsite = cisza na arenach produktu. CMO nie robi tablicy ogłoszeń.

## Files likely touched

- `influenzer/playbook.py` — detect hire / funding-round / offsite copy
- `influenzer/hom.py` — score those briefs as kill
- `influenzer/hom_draft.py` — refuse to dress a leaked draft of the same shape
- `tests/test_hom_operator.py` — lock the detector and the score kill
- `tests/test_hom_draft.py` — lock dress silence even when score says draft

## Test plan

- `uv run pytest tests/test_hom_operator.py tests/test_hom_draft.py`

## Non-goals

- Do not invent a new arena for jobs or fundraising.
- Do not treat a job-application form or a funding README as a hire/round.

## Notes

- Same fail-closed pattern as #131 (world commentary) and #135 (contest).
- A ship URL glued onto a hire/round/offsite brief is still silence.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
