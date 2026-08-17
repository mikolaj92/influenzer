# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=32 -->

Repository: `mikolaj92/influenzer`  
Issue: #32 — Show HN to tytuł, URL i backstory, nie blog

## Goal

Show HN to tytuł + URL + pierwszy komentarz jako backstory, nie blog. Draft na HN ma trzy pola: `Show HN: …`, URL w polu linku, backstory pod spodem (człowiek, nie komunikat). Bez waitlisty, bez „please upvote”.

## Files likely touched

- `influenzer/hom_draft.py` — require title + tryable URL + first leftover fact; dump of the rest is a blog; missing backstory is silence.
- `skills/influenzer-hn/SKILL.md` — three fields or silence.
- `tests/test_hom_draft.py` — title-only is undressable; leftover dump stays out of the first comment.
- `tests/test_e2e_gates.py` — same fail-closed gate through score/compose.

## Test plan

- `python3 -m unittest tests.test_hom_draft tests.test_e2e_gates`

## Non-goals

- Do not publish, do not enable live, do not open a second Show HN.
- Do not change scoring in `hom.py` / `playbook.py` (outside localize scope).

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
