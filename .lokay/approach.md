# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=124 -->

Repository: `mikolaj92/influenzer`  
Issue: #124 — Show HN nie jest kartą na agregatorze

## Goal

Show HN nie jest kartą na agregatorze. Product Hunt / BetaList / „launch on PH” jako URL = cisza. Link do rzeczy, nie do tablicy launchy.

## Files likely touched

- `influenzer/playbook.py` — classify Product Hunt / BetaList / "launch on PH" URLs
- `influenzer/hom.py` — seminar kill when the only URL is a launch board
- `influenzer/hom_draft.py` — refuse to dress a launch board as Show HN
- `tests/test_hom_operator.py` — board-only silence; board+repo still drafts
- `tests/test_hom_draft.py` — leaked HN score with a board URL stays undressable

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Blog / shop URL gates (#122/#123)
- Film host gate (#125)
- Cinema / YouTube arena packaging

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Pattern mirrors #125 film-host fail-closed: classify hosts in playbook, kill on HN when only URL is a board, refuse to dress a board URL as Show HN; board next to a repo can still draft with the repo URL.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
