# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=150 -->

Repository: `mikolaj92/influenzer`  
Issue: #150 — Sam meme nie jest kątem

## Goal

Sam meme nie jest kątem. Drake, wojak, reaction image bez artefaktu = cisza. Kostium nie jest tablicą z memami.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_meme` / `MEME_REASON`
- `influenzer/hom.py` — kill at score
- `influenzer/hom_draft.py` — refuse to dress a leaked meme draft
- `influenzer/brief_admit.py` — pack admit silence
- `github_pack/classify.py` + `github_pack/pack.py` — survey pack silence
- tests: e2e, operator, draft, admit, pack

## Test plan

- Run the smallest useful tests for files touched:
  - `tests/test_e2e_gates.py`
  - `tests/test_hom_operator.py`
  - `tests/test_hom_draft.py`
  - `tests/test_brief_admit.py`
  - `tests/test_github_pack.py`

## Non-goals

- Do not invent a costume that posts memes.
- Do not treat a demo screenshot or "remember" as a meme.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Fail closed at score, dress, pack, and admit — same shape as #149 FOMO and #134 ranking dump.
- Neighbor of #45 (voice mix) and #134 (vanity chart). Here it is the picture, not a product.
