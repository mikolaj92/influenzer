# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=51 -->

Repository: `mikolaj92/influenzer`  
Issue: #51 — List ma imię, bez nazwiska = cisza

## Goal

Newsletter dresses from `BrandProfile` (display_name / maintainer), not “we” / “the team”. One named editor, first and last name. A given name without a surname is silence on the letter. Same fail-closed pattern as #54 (gift first) and #53 (seminar brand voice).

## Files likely touched

- `influenzer/playbook.py` — letter surname / team-voice gate
- `tests/test_e2e_gates.py` — e2e silence + living named letter
- `influenzer/hom.py` / `influenzer/hom_draft.py` — already call `letter_reason`; no extra wiring

## Test plan

- `python -m unittest tests.test_e2e_gates`

## Non-goals

- Injecting a byline from stored BrandProfile (Brief has no profile; gate reads the wearable copy)
- Changing newsletter ESP / publish path

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Localization seed was tests-only; sibling gates (#53/#54) live in playbook + dress + e2e.
- Collector boundary: no unbounded collection.
