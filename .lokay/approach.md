# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=165 -->

Repository: `mikolaj92/influenzer`  
Issue: #165 — Ściana ciasteczek nie jest tryable

## Goal

Treat a cookie-consent wall / blocking GDPR overlay as not tryable. Ship claims
and social arenas go silent; a non-ship brief is changelog-only. A guest does
not click through the overlay to reveal the product.

## Files likely touched

- `influenzer/host.py` — focused detector + `artifact_tryable_reason`
- `influenzer/hom.py` — score kill / changelog
- `influenzer/hom_draft.py` — fail closed if a leaked score says draft
- `influenzer/playbook.py` — HN wave
- `skills/influenzer-hn/SKILL.md` — seminar guidance
- `tests/test_e2e_gates.py` — gate cases and passive-notice/product-copy negatives

## Test plan

- Run the cookie-wall e2e test, then the full e2e gate module

## Non-goals

- Clicking, accepting, or bypassing cookie consent
- Live HTTP/browser probing
- Treating a passive cookie notice or generic cookie/GDPR product copy as a wall
- Changing login-wall, CAPTCHA, age-gate, geo-block, or maintenance behavior

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
