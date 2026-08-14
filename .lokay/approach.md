# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=119 -->

Repository: `mikolaj92/influenzer`  
Issue: #119 — Cytat tylko z feedbacku z URL-em

## Goal

Cytat tylko z feedbacku z URL-em. Żadnego „users love” / zmyślonej opinii. Nie ma excerptu — nie ma cudzysłowu.

## Files likely touched

- `influenzer/playbook.py` — `unquotable_reason`: quote marks need an excerpt/comment + https URL; `users love` is invented opinion
- `influenzer/hom.py` — score-time kill (`quote_without_excerpt` / `invented_opinion`)
- `influenzer/hom_draft.py` — dress-time refuse so a leaked DRAFT still cannot invent a quote
- `tests/test_hom_operator.py` — helper + score cases
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py tests/test_hom_pass.py tests/test_hom_feedback.py tests/test_hom_outbox.py -q`

## Non-goals

- Neighbor #118 (a number from the brief)
- Neighbor #99 (excerpt, not the whole thread)
- Changing github_feedback collection / admit

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Fail-closed: quote without excerpt+URL = silence; invented opinion = silence.
- A sourced `issue_comment` / `pull_comment` / `excerpt` with an https URL may be quoted.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
