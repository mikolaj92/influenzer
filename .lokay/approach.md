# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=163 -->

Repository: `mikolaj92/influenzer`  
Issue: #163 — Bramka wieku nie jest tryable

## Goal

Treat an age gate / 18+ declaration on an artifact as not tryable. Ship claims
and social arenas go silent; a non-ship brief is changelog-only. A guest does
not click through an age declaration.

## Files likely touched

- `influenzer/host.py` — detector + `artifact_tryable_reason`
- `influenzer/hom.py` — score kill / changelog
- `influenzer/hom_draft.py` — fail closed if a leaked score says draft
- `influenzer/playbook.py` — HN wave
- `skills/influenzer-hn/SKILL.md` — seminar guidance
- `tests/test_e2e_gates.py` — gate cases and product-copy negatives

## Test plan

- Run the age-gate e2e test, then the full e2e gate module if practical

## Non-goals

- Clicking or bypassing an age declaration
- Live HTTP/browser probing
- Treating generic age-related product copy or runtime versions such as Node.js 18+ as a gate
- Changing login-wall, captcha, or geo-block behavior

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
