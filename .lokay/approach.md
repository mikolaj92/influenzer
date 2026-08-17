# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=144 -->

Repository: `mikolaj92/influenzer`  
Issue: #144 — Podziękowanie za licznik nie jest kątem

## Goal

Podziękowanie za licznik nie jest kątem. „Thanks for N stars”, milestone follow = cisza. To nie historia produktu.

Fail-closed at score, dress, pack, and admit. Neighbor of #56 (dead stars are not a story) and #134 (a ranking dump is not an artifact). Here it is the thank-you, not the chart.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_counter_thanks` / `COUNTER_THANKS_REASON`
- `influenzer/hom.py` — kill at score
- `influenzer/hom_draft.py` — undress even when a leaked score says draft
- `github_pack/classify.py` / `github_pack/pack.py` — pack silence
- `influenzer/brief_admit.py` — admit silence
- `tests/test_e2e_gates.py`, `tests/test_hom_draft.py`, `tests/test_hom_operator.py`, `tests/test_brief_admit.py`, `tests/test_github_pack.py`

## Test plan

- Detector: thanks for N stars / milestone follow / dziękujemy za gwiazdki / podziękowanie za licznik
- Stay: thanks for the issue, thanks for watching, follow the README, star the repo after you try it
- Score / dress / pack / admit all return silence

## Non-goals

- Do not retread #56 (dead star count as changelog) or #134 (ranking dump as artifact)
- Do not treat inbound "+1 / thanks" comments; that is already feedback silence
- Do not start a collector

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
