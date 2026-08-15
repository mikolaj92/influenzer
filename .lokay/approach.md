# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=85 -->

Repository: `mikolaj92/influenzer`  
Issue: #85 — Tydzień samych bumpów to nie historia

## Goal

Tydzień samych bumpów to nie historia. Jeśli w oknie looku merge’e są tylko z botów (dependabot, renovate, github-actions) — cisza społeczna. Changelog wolno. Nie robimy launchu z diffów wersji.

## Files likely touched

- `influenzer/playbook.py` — bot-author / version-diff detectors and `looks_like_bot_bump_week`
- `influenzer/hom.py` — score bot-only / version-diff looks as `CHANGELOG_ONLY` (`bot_bump_week`)
- `influenzer/hom_draft.py` — refuse to dress a bot-bump week even if a stale score says draft
- `tests/test_hom_operator.py` — heuristic + scoring coverage
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py tests/test_github_pack.py -q --tb=short`

## Non-goals

- Do not change github_pack / github_survey (outside this worktree's required scoring gate).
- Do not launch from a version tag. Changelog may keep the date.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Pair of no-noise (#64): chore/typo vs author is a bot. A human feat next to a bump stays.
- A stale README/description next to a version tag is not a story.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
