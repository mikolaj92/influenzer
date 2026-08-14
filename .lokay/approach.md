# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=129 -->

Repository: `mikolaj92/influenzer`  
Issue: #129 — Roadmap to nie ship

## Goal

Roadmap is not a ship. “Coming Q3”, “soon”, “on the roadmap” in a title or
facts is a calendar, not a tryable artifact. Social silence. Changelog is
allowed. Steam behind a waitlist is a date, not a mailing list.

Neighbors: #46 (waitlist is not a ship) and #83 (draft/prerelease is not a ship).

## Files likely touched

- `influenzer/playbook.py` — `looks_like_roadmap` + calendar regex
- `influenzer/hom.py` — score: ship/social claim → kill, else changelog
- `influenzer/hom_draft.py` — refuse to dress a leaked roadmap draft
- `tests/test_hom_operator.py` — detector + score coverage
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python3 -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not treat a glued-on GitHub URL as making a calendar tryable.
- Do not silence “as soon as …” or a file named `roadmap.md`.
- Do not start a collector or edit `github_pack/` (out of localize scope).

## Notes

- Same fail-closed shape as waitlist: claims_ship or social arena → kill;
  otherwise changelog-only. Dressing refuses the same shape even if scoring
  is bypassed.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
