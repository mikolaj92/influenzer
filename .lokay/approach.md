# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=29 -->

Repository: `mikolaj92/influenzer`  
Issue: #29 — Ton notki prasowej nie idzie na kąt społeczny

## Goal

Ton notki prasowej umiera. Jeśli brief/draft brzmi jak PR (we’re excited, announcement, unveiling, delighted to share) — score nie daje kąta społecznego. HN/GitHub/X: kill albo changelog. Kostium zostaje warsztatem/seminarium, nie komunikatem.

## Files likely touched

- `influenzer/playbook.py` — broaden press-release detector to we’re excited / announcement / unveiling / delighted to share.
- `influenzer/hom.py` — score PR tone as kill (ship/social) or changelog, never a social angle. GitHub included.
- `influenzer/hom_draft.py` — dress stays fail-closed even if score leaks draft.
- `tests/test_hom_operator.py`, `tests/test_e2e_gates.py`, `tests/test_hom_draft.py` — HN/GitHub/X kill, workshop changelog, leaked draft undressable.
- `skills/influenzer-hom/SKILL.md`, `skills/influenzer-hn/SKILL.md` — costume stays workshop/seminar, not a komunikat.

## Test plan

- `python -m unittest tests.test_hom_operator.ScoreBriefTests.test_press_release_tone_on_hn_is_killed tests.test_hom_operator.ScoreBriefTests.test_press_release_tone_is_kill_or_changelog_not_a_social_angle tests.test_e2e_gates.OrderedLiveGateTests.test_press_release_tone_is_changelog_or_silence_not_an_angle tests.test_hom_draft.HomDraftCostumeTests.test_press_release_tone_is_undressable_even_when_score_says_draft`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
