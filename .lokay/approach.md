# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=48 -->

Repository: `mikolaj92/influenzer`  
Issue: #48 — README bez dema to martwa witryna

## Goal

Kąt GitHub (warsztat) wymaga na jednym ekranie: one-liner, widoczne demo (GIF/screenshot), działający quickstart. Sam tekst bez obrazu → changelog, nie launch.

## Files likely touched

- `github_pack/pack.py` — fail closed when a ship README has no visible demo (GIF/screenshot).
- `tests/test_github_pack.py` — pack silence vs launch for text-only vs GIF README.
- `tests/test_e2e_gates.py` — workshop launch still drafts only with a visible demo.
- `tests/gh_scripts.py` — default ship fixture is a one-screen README (quickstart + GIF).

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
