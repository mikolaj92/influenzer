# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=146 -->

Repository: `mikolaj92/influenzer`  
Issue: #146 — Dziennik założyciela nie jest kątem

## Goal

Dziennik założyciela nie jest kątem. Desk setup, „tools I use”, day in the life, morning routine = cisza. To nie ship.

Fail closed at score, dress, pack, and admit. Neighbor of #130 (hire/fundraise) and #138 (event is not a ship). Here it is lifestyle, not a product. `setup.py` and `this morning we shipped` stay.

## Files likely touched

- `influenzer/playbook.py`
- `influenzer/hom.py`
- `influenzer/hom_draft.py`
- `influenzer/brief_admit.py`
- `github_pack/classify.py`
- `github_pack/pack.py`
- `tests/test_e2e_gates.py`
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`
- `tests/test_brief_admit.py`
- `tests/test_github_pack.py`

## Test plan

- `python3 -m unittest tests.TestE2EGates.test_founder_journal_is_silence_not_an_angle tests.TestHomOperator.test_founder_journal_is_desk_setup_not_a_product tests.TestHomOperator.test_founder_journal_is_killed tests.TestHomDraft.test_founder_journal_is_undressable_even_when_score_says_draft tests.TestBriefAdmit.test_founder_journal_pack_is_silence_not_a_ship tests.TestGithubPack.test_desk_setup_release_is_silence`

## Non-goals

- Do not treat a real ship (`this morning we shipped`, `setup.py`) as lifestyle.

## Notes

- Deterministic localize matched `tools/` from the phrase “tools I use”. That is a token false-positive; the gate lives with the other fail-closed angles.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
