# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=42 -->

Repository: `mikolaj92/influenzer`  
Issue: #42 — Koniec odcinka nie ogłasza końca

## Goal

YouTube/Shorts: zero „thanks for watching”, like&subscribe, outro-logo. Jedno CTA albo pętla, nie oba. Inaczej cisza na cinema/fair.

## Files likely touched

- `influenzer/playbook.py` — cinema end detector (thanks / like&subscribe / outro-logo)
- `influenzer/hom.py` — YouTube gate uses cinema_end_reason
- `influenzer/hom_draft.py` — cinema dress is silence on an announced end
- `tests/test_e2e_gates.py` — cinema/fair end-of-cut coverage

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
