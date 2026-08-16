# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=54 -->

Repository: `mikolaj92/influenzer`  
Issue: #54 — List najpierw daje, potem ewentualnie prosi

## Goal

Letter costume: without a concrete gift for the reader, do not publish. Subscribe / our launch alone is silence. Recs are adjacent (sąsiad), not a crush. One story. Not live.

## Files likely touched

- `influenzer/playbook.py` — `letter_reason`, gift/ask/crush detectors, seat preferred newsletter
- `influenzer/hom.py` — fail-closed `_gate_violation` on newsletter
- `influenzer/hom_draft.py` — refuse to dress an ask-only letter
- `tests/test_e2e_gates.py` — ordered live + letter gate

## Test plan

- `python -m unittest tests.test_e2e_gates`
- Targeted dress/score checks if the letter seat changes choose_arena

## Non-goals

- No live publish, no ESP, no collector, no second story.

## Notes

- Same pattern as #55/#57/#58: sit on the preferred costume so emptiness can be silence.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
