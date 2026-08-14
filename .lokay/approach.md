# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=136 -->

Repository: `mikolaj92/influenzer`  
Issue: #136 — Wątek 1/n nie jest kątem

## Goal

Wątek 1/n nie jest kątem. Numeracja, „thread”, storm = cisza. Jeden post, nie serial.

## Files likely touched

- `influenzer/playbook.py` — detect 1/n / thread / storm; exempt OS thread-safe / pthread / 24/7
- `influenzer/hom.py` — kill briefs whose facts are a serial
- `influenzer/hom_draft.py` — refuse to dress a leaked serial even if score says draft
- `tests/test_hom_operator.py` — detector + score kill
- `tests/test_hom_draft.py` — undressable even when score says draft

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py tests/test_hom_verdict.py tests/test_hom_pass.py tests/test_policy.py tests/test_hom_feedback.py`

## Non-goals

- Does not change one-story-at-a-time admit (`#44`) or camp-the-HN-thread (`#50`).
- Does not invent a thread publisher. One post, or silence.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
