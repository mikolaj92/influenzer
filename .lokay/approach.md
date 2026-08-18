# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=162 -->

Repository: `mikolaj92/influenzer`  
Issue: #162 — Geo-block nie jest tryable

## Goal

Treat a 451 / country wall / “not available in your region” artifact as not
tryable. Show HN is global: ship claims and social arenas go silent; a
non-ship brief is changelog-only. Neighbor of #126 (login wall) and #160
(captcha): here it is region, not login or a bot challenge.

## Files likely touched

- `influenzer/host.py` — detector + `artifact_tryable_reason`
- `influenzer/hom.py` — score kill / changelog
- `influenzer/hom_draft.py` — undress even if a leaked score says draft
- `influenzer/playbook.py` — HN wave
- `skills/influenzer-hn/SKILL.md` — seminar copy
- `tests/test_e2e_gates.py` — fail-closed cases and product-copy negatives

## Test plan

- `python -m unittest tests.TestE2eGates.OrderedLiveGateTests.test_geo_block_is_silence_not_tryable tests.TestE2eGates.OrderedLiveGateTests.test_captcha_bot_wall_is_silence_not_tryable`

## Non-goals

- Live HTTP probes of the artifact
- Treating generic “available in N countries” product copy as a gate
- Changing login-wall (#126) or captcha (#160) detectors

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
