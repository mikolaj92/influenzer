# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=25 -->

Repository: `mikolaj92/influenzer`  
Issue: #25 — Nie reklamować zepsutej witryny

## Goal

Watch-repo bez działającego quickstartu w README (jedna strona: one-liner → start) to fałszywy launch. Brief ze `claims_ship` pada na changelog/kill, nie na kąt społeczny. HN/X nie dostają waitlisty ani „Show HN” bez `uv run`/`pip`/`brew` które da się skopiować.

## Files likely touched

- `github_pack/pack.py` — fail-closed pack gate: prose pip/uv/brew is not a start
- `tests/test_github_pack.py` — pack silence without a copyable one-liner
- `tests/test_e2e_gates.py` — no Show HN / waitlist from a broken README
- `tests/test_brief_admit.py` — look/admit inherit pack silence
- `tests/test_brief_scan_cli.py` — CLI scan writes no brief
- `tests/test_hom_watch.py` — due watch stays cisza, no social angle

## Test plan

- `python -m unittest tests.test_github_pack tests.test_e2e_gates tests.test_brief_admit tests.test_brief_scan_cli tests.test_hom_watch`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
