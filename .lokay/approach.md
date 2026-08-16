# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=56 -->

Repository: `mikolaj92/influenzer`  
Issue: #56 — Martwe gwiazdki to nie historia

## Goal

Jeśli fakty to tylko „N stars” / ranking bez instalacji, issue, albo życia po spike — score zabija kąt. Changelog wolno. Warsztat liczy użycie, nie trupa na tle.

## Files likely touched

- `influenzer/playbook.py` — dead-star count detector + usage-after-spike exception
- `influenzer/hom.py` — score a star-only look as changelog, not a launch
- `influenzer/hom_draft.py` — refuse to dress a leaked star-only draft
- `tests/test_e2e_gates.py` — e2e: corpse count is changelog; install/issue stays
- `tests/test_hom_operator.py` — detector + score
- `tests/test_hom_draft.py` — leaked draft stays silent

## Test plan

- `python -m unittest tests.test_e2e_gates tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not treat a ranking dump / HN front as this gate (#134 stays kill).
- Do not treat “star the repo after you try it” as a corpse count.

## Notes

- Pair of #134 (ranking dump is not an artifact) and #85 (a week of bumps is not a story).
- Collector boundary: no unbounded collection in this patch.
