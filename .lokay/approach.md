# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=35 -->

Repository: `mikolaj92/influenzer`  
Issue: #35 — Bluesky bez URL-a artefaktu = cisza

## Goal

Bluesky to zasięg, GitHub konwertuje. Draft na Bluesky bez URL-a artefaktu (repo, demo, release) = cisza. Vibe bez dowodu nie wychodzi. Pack/feed to kostium, nie treść.

Score already sat preferred Bluesky and killed `bluesky_vibe_without_artifact` when `require_ship_artifact` missed. Dress still needed an explicit cafe artifact fail-closed so a leaked draft cannot go out without a ship URL. Pack/feed (#55) stays a separate costume check.

## Files likely touched

- `influenzer/playbook.py` — named `cafe_artifact_reason` / `BLUESKY_VIBE_WITHOUT_ARTIFACT_REASON`
- `influenzer/hom.py` — score Bluesky before draft
- `influenzer/hom_draft.py` — dress refuses vibe without a ship URL
- `skills/influenzer-bluesky/SKILL.md`
- `skills/influenzer-hom/SKILL.md`
- `tests/test_e2e_gates.py`
- `tests/test_hom_draft.py`
- `tests/test_hom_operator.py`

## Test plan

- `python -m unittest tests.test_e2e_gates.OrderedLiveGateTests.test_bluesky_without_artifact_url_is_silence tests.test_e2e_gates.OrderedLiveGateTests.test_bluesky_without_pack_and_feed_is_silence tests.test_hom_draft.HomDraftCostumeTests.test_bluesky_without_artifact_url_is_undressable_even_when_score_says_draft tests.test_hom_draft.HomDraftCostumeTests.test_bluesky_with_pack_and_feed_can_still_dress tests.test_hom_operator.ScoreBriefTests.test_bluesky_without_artifact_is_killed`

## Non-goals

- Changing pack/feed costume (#55)
- Publishing or enabling live social
- Broadening ship-artifact hosts beyond the existing GitHub allowlist

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
