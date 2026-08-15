# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=83 -->

Repository: `mikolaj92/influenzer`  
Issue: #83 — Draft i prerelease na GitHubie to nie ship

## Goal

Draft i prerelease na GitHubie to nie ship. Tylko opublikowany, nie-prerelease release (albo merge z tryable artefaktem) może stawiać claims_ship. RC/beta/draft → changelog albo cisza, nie Show HN.

## Files likely touched

- `influenzer/playbook.py` — `PRERELEASE_RE` + `looks_like_prerelease`
- `influenzer/hom.py` — score: claims_ship / social → kill, else changelog
- `influenzer/hom_draft.py` — undressable even if a score already said draft
- `tests/test_hom_operator.py` — matcher + score fail-closed
- `tests/test_hom_draft.py` — dress fail-closed

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py tests/test_github_pack.py tests/test_github_survey.py`

## Non-goals

- Do not treat operator copy such as "emits a draft" as a GitHub draft release.
- Survey already drops `isDraft` / `isPrerelease` flags; this gate is the scoring/dress fail-closed for text, tags, and flags that still reach a brief.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
