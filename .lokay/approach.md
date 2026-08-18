# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=151 -->

Repository: `mikolaj92/influenzer`  
Issue: #151 — Deck nie jest artefaktem

## Goal

Deck nie jest artefaktem. Pitch, PDF slajdów, Notion one-pager bez klikalnego produktu = cisza.

## Files likely touched

- `influenzer/playbook.py` — detector, hosts, wave copy
- `influenzer/hom.py` — score fail-closed
- `influenzer/hom_draft.py` — refuse leaked deck drafts
- `influenzer/brief_admit.py` — admit silence
- `github_pack/classify.py` / `github_pack/pack.py` — pack silence
- `skills/influenzer-hn/SKILL.md` — seminar copy
- tests: `test_hom_operator.py`, `test_hom_draft.py`, `test_e2e_gates.py`, `test_brief_admit.py`, `test_github_pack.py`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- Do not treat a deck next to a real GitHub ship as a tryable demo.
- Do not confuse court "pitch in line one" with a pitch deck.

## Notes

- Same fail-closed shape as #150 (meme) plus host-only silence like #122/#134.
- Neighbor of #40 (Show HN without tryable) and #122 (blog URL): here it is slides, not a blog.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
