# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=121 -->

Repository: `mikolaj92/influenzer`  
Issue: #121 — Show HN to nie listicle

## Goal

Show HN is not a listicle. A title with “N ways”, “you won’t believe”, or a trailing bang is silence. Curiosity and a working thing, not a magazine.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_listicle_title` plus the seminar wave line
- `influenzer/hom.py` — HN gate kills `hn_not_a_listicle`
- `influenzer/hom_draft.py` — dresser refuses a listicle title even if score says draft
- `tests/test_hom_operator.py` — score / apply_brief fail-closed cases
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `uv run --extra dev python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not rewrite a good title. Silence, not a rewrite.
- Do not invent extra clickbait heuristics beyond the named patterns.
- Do not start a collector or wait for collection.

## Notes

- Same fail-closed shape as #122/#123/#125 (blog / store / film): score kills, dresser also refuses.
- Neighbor #120 (CAPS-off) is a separate title gate; this one is listicle / clickbait / trailing bang.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
