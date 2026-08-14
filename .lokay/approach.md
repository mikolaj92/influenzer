# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=171 -->

Repository: `mikolaj92/influenzer`  
Issue: #171 — Martwy plik w release nie jest shipem

## Goal

A listed release asset whose download is 404/410 is silence, not a ship.
Do not promise a binary that is not there.

## Files likely touched

- `influenzer/playbook.py` — fail-closed `DEAD_RELEASE_ASSET_RE` / `looks_like_dead_release_asset`
- `influenzer/hom.py` — ship/social kill, otherwise changelog
- `influenzer/hom_draft.py` — undress even if a score says draft
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Empty release / empty tag (#170)
- Generic dead link without a listed asset (#92)
- Live HTTP HEAD of GitHub assets
- Survey/pack collectors

## Notes

- Same shape as login-wall / waitlist: text evidence in the brief, not a network check.
- Bare `HEAD 404` stays out of this gate so #92 can own a generic corpse.
