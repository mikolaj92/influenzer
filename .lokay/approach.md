# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=50 -->

Repository: `mikolaj92/influenzer`  
Issue: #50 — Po Show HN siedzimy w wątku, nie robimy drugiego Show

## Goal

Gdy kąt HN jest otwarty albo w stosie 48h, feedback czyta komentarze tego itemu/repo. Score nie wybiera HN drugi raz. Backstory już padł (#32); teraz obóz.

## Files likely touched

- `influenzer/playbook.py` — `hn_camp` latch on a living HN stack
- `influenzer/hom.py` — score kills a second Show
- `influenzer/hom_feedback.py` — camp still reads repo comments, does not admit another story
- `tests/test_e2e_gates.py`, `tests/test_hom_feedback.py`, `tests/test_hom_operator.py`

## Test plan

- `python -m unittest tests.test_e2e_gates tests.test_hom_feedback tests.test_github_feedback` plus the living-stack / camp cases in `tests.test_hom_operator`

## Non-goals

- Fetching HN item comments over the network
- Publishing replies into the thread
- Changing the 48h github costume (workshop may still draft)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: no unbounded collection.
