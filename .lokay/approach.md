# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=125 -->

Repository: `mikolaj92/influenzer`  
Issue: #125 — Show HN nie jest odcinkiem

## Goal

Show HN nie jest odcinkiem. YouTube/Vimeo/Loom jako jedyny URL = cisza na seminar. Film może być dowodem przy repo; sam film nie jest klik-i-odpal.

## Files likely touched

- `influenzer/playbook.py` — classify YouTube/Vimeo/Loom URLs
- `influenzer/hom.py` — seminar kill when the only URL is a film
- `influenzer/hom_draft.py` — refuse to dress a film as Show HN
- `tests/test_hom_operator.py` — film-only silence; film+repo still drafts
- `tests/test_hom_draft.py` — leaked HN score with a film URL stays undressable

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Cinema / YouTube arena packaging (separate #36/#37)
- Blog / shop / aggregator URL gates (#122/#123/#124)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
