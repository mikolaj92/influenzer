# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=86 -->

Repository: `mikolaj92/influenzer`  
Issue: #86 — Samo docs/typo/chore to nie ship

## Goal

A look window of only docs / typo / chore — even human-authored — is not a ship.
Social look is silence. Changelog on GitHub is allowed. This is not bot-bumpy
(#85); author does not matter. A human feat next to a typo still drafts.

## Files likely touched

- `influenzer/playbook.py` — window detector + workshop/seminar wave copy
- `influenzer/hom.py` — score as changelog_only (`docs_typo_chore`)
- `influenzer/hom_draft.py` — fail-closed dress (no Show HN leak)
- `tests/test_hom_operator.py` — window vs feat-next-to-typo
- `tests/test_hom_draft.py` — undressable even if score says draft

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- Bot-only bump weeks (#85)
- Changing github_pack ingest (already drops isolated noise PRs)
- Social publish / live adapters

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- `github_pack` prefixes release/tag names as `Released …` / `Tag …`. The window
  detector must peel that wrapper or a human docs-only release still drafts Show HN.
