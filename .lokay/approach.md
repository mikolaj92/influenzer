# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=129 -->

Repository: `mikolaj92/influenzer`  
Issue: #129 — Roadmap to nie ship

## Goal

Roadmap to nie ship. „Coming Q3”, „soon”, „on the roadmap” w tytule/faktach bez działającego artefaktu = cisza społeczna. Changelog wolno. Para za waitlistą, to kalendarz nie lista mailowa.

## Files likely touched

- `influenzer/playbook.py` — `ROADMAP_RE` + `looks_like_roadmap`
- `influenzer/hom.py` — score: social/ship claim = kill, else changelog
- `influenzer/hom_draft.py` — undressable even if a fake score says draft
- `tests/test_hom_operator.py`, `tests/test_hom_draft.py`

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- Do not treat a tryable ship as social copy just because a date is mentioned in changelog.
- Do not match “as soon as”, “too soon”, “soon after”, `roadmap.md`, or hyphenated “soon-to-be”.

## Notes

- Same fail-closed split as waitlist: ship claim or social arena → kill; otherwise changelog.
- Bare “soon” only as a title/sentence, or after coming/shipping/launching/…
- Collector boundary: none. No collection.
