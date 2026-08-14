# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=113 -->

Repository: `mikolaj92/influenzer`  
Issue: #113 — Ściana hashtagów to nie kostium

## Goal

Ściana hashtagów to nie kostium. Draft z dumpem tagów (więcej niż jeden-dwa, albo sam ogonek tagów) = cisza. Dwór i agora nie są katalogiem SEO.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_hashtag_wall`; court/agora wave lines
- `influenzer/hom.py` — score kill `hashtag_wall`
- `influenzer/hom_draft.py` — dress silence on blob and body
- `tests/test_hom_operator.py` — detector + score
- `tests/test_hom_draft.py` — dress fail-closed on HN/X/LinkedIn

## Test plan

- `python3 -m pytest tests/test_hom_draft.py tests/test_hom_operator.py -q --tb=short`

## Non-goals

- Do not invent a new costume. One or two inline tags can stay.
- Do not treat `#190` / URL fragments as tags.

## Notes

- Same fail-closed pattern as #114 (engagement bait) and #116 (dunking).
- Neighbor of #45 (voice) and #63 (format): court and agora stay insight/reply, not an SEO catalog.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
