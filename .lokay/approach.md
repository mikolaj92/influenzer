# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=92 -->

Repository: `mikolaj92/influenzer`  
Issue: #92 — Martwy link nie jest tryable

## Goal

A generic HEAD/GET 404/410 on an artifact is not tryable. Silence on Show HN
and ship claims. This is status evidence, not a URL scheme. A recorded
timeout is the same silence. Do not promise a click on a corpse.

## Files likely touched

- `influenzer/playbook.py` — fail-closed `DEAD_LINK_RE` / `looks_like_dead_link`
- `influenzer/hom.py` — ship/social kill, otherwise changelog
- `influenzer/hom_draft.py` — undress even if a score says draft
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Live HTTP HEAD/GET of artifact URLs (HOM stays rule-only; look is GitHub
  GET via the gh catalog; scan-due/pass/watch must not fetch)
- Listed release-asset 404 (#171) and login wall 401/403 (#126)
- Redirect allowlist (#93) and host+https (#76/#77)
- github_survey / github_pack collectors

## Notes

- Same shape as login-wall / listed corpse: text evidence in the brief, not
  a network check. Bare `HEAD 404` / `GET 410` / `dead link` is this gate.
- `404/410` matches the detector but is also a thread-number shape (`\d+/\d+`);
  score uses the clearer HEAD/GET phrases so the thread gate does not steal it.
- A probe, if look ever recorded one, would be bounded like gh (#79). The
  recorded timeout phrase is silence, not a retry or a click.
- Collector boundary: no unbounded collection.
