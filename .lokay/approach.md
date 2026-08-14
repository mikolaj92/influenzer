# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=115 -->

Repository: `mikolaj92/influenzer`  
Issue: #115 — Show HN i one-liner GitHuba bez emoji

## Goal

Show HN and the GitHub README one-liner stay without emoji. Seminar and
workshop are not a fair. Emoji in the title is silence on those arenas.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_emoji_title` plus wave copy
- `influenzer/hom.py` — fail-closed score kill on HN / GitHub
- `influenzer/hom_draft.py` — undressable even if a score says draft
- `tests/test_hom_operator.py` — detector + score silence
- `tests/test_hom_draft.py` — dress-path silence

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py`
- `python -m pytest tests/test_hom_pass.py tests/test_hom_outbox.py tests/test_hom_verdict.py tests/test_policy.py`

## Non-goals

- Length limits (neighbor of #70). This issue is the sign, not the length.
- Costume language (#69).
- Emoji elsewhere in the body / first comment / backstory.
- Other arenas (X, LinkedIn, Reddit, …).

## Notes

- Same shape as #120 shouty CAPS: score kill + dress refuse.
- ASCII, C++, and the workshop arrow `→` stay wearable.
- Collector boundary: no collection job.
