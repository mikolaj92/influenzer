# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=27 -->

Repository: `mikolaj92/influenzer`  
Issue: #27 — X nie dostaje pustego feedu

## Goal

X nie dostaje pustego feedu. Score nie wybiera X, chyba że brief ma URL posta-rodzica (reply, pożyczony heat). Ship bez wątku → github albo HN gdy tryable, inaczej cisza. Żadnego oryginału w pustkę.

## Files likely touched

- `influenzer/playbook.py` — sit on X only with a parent-post URL; empty feed is not a first costume
- `influenzer/hom.py` — pass parent proof into score; kill leaked X originals
- `influenzer/hom_draft.py` — refuse to dress X without a parent URL
- `skills/influenzer-x/SKILL.md`, `skills/influenzer-hom/SKILL.md` — no original into an empty feed
- `tests/test_e2e_gates.py` — empty-feed original is github/HN or silence, not agora
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py` — preferred X without a thread no longer drafts an original

## Test plan

- `pytest tests/test_e2e_gates.py tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- No publish, no live, no second story. Small score block, not a new path.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
