# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=126 -->

Repository: `mikolaj92/influenzer`  
Issue: #126 — Artefakt za logowaniem nie jest tryable

## Goal

A login-gated artifact is not tryable. Copy that says the demo is behind a
login / sign-in / 401/403 is silence on Show HN and ship claims. This is a
gate, not a 404 corpse. A stranger must be able to run it without logging in.

## Files likely touched

- `influenzer/playbook.py` — `LOGIN_GATE_RE` + `looks_like_login_gate`
- `influenzer/hom.py` — fail-closed score (`login_gate_not_tryable`)
- `influenzer/hom_draft.py` — undressable even if a score leaks draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py`

## Test plan

- Heuristic: login wall / HEAD-GET 401/403 / za logowaniem match; login form
  as a product feature and 404 do not
- Ship claim or social arena + login gate → KILL `login_gate_not_tryable`
- Same copy without ship/social → CHANGELOG_ONLY
- Dress refuses a leaked draft score; product copy still dresses

## Non-goals

- Live HEAD/GET of artifact URLs (HOM stays rule-only; no provider calls)
- 404/410 dead-link (#92) and waitlist (#46) — neighbors, not this gate
- github_pack survey packing (login walls do not arrive as GH release names)

## Notes

- Same shape as waitlist/roadmap: playbook detector, score kill/changelog,
  dress fail-closed.
- Collector boundary: no unbounded collection.
