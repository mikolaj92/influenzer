# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=122 -->

Repository: `mikolaj92/influenzer`  
Issue: #122 — Show HN nie jest blogiem: URL na Medium/Substack = cisza

## Goal

Show HN nie jest blogiem. URL na Medium/Substack/dev.to/hashnode = cisza na seminar. Link to repo albo działające demo, nie artykuł o rzeczy.

## Files likely touched

- `influenzer/playbook.py` — `BLOG_HOSTS` + `is_blog_host_url` (Medium / Substack / dev.to / hashnode)
- `influenzer/hom.py` — HN gate: blog-only URL is `hn_not_a_blog`; blog host is not clickable
- `influenzer/hom_draft.py` — seminar dress refuses a blog URL even if score says draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py` — fail-closed host + dress tests

## Test plan

- `python -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q --tb=short`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
