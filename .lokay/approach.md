# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=64 -->

Repository: `mikolaj92/influenzer`  
Issue: #64 — Poniedziałek bez historii to cisza, nie recap

## Goal

Poniedziałek bez historii to cisza, nie recap. Look bez ship/tryable i bez prawdziwego feedbacku nie produkuje kąta ani „weekly update”. Changelog może zostać w repo. Społecznie — milczenie.

## Files likely touched

- `influenzer/playbook.py` — fail-closed Monday/history detector
- `influenzer/hom.py` — score: no ship/tryable and no real feedback = changelog or social kill
- `influenzer/hom_draft.py` — dress refuses a recap even if score says draft
- `tests/test_hom_operator.py` / `tests/test_hom_draft.py`

## Test plan

- `uv run python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
