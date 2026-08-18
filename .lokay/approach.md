# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=160 -->

Repository: `mikolaj92/influenzer`  
Issue: #160 — Captcha nie jest tryable

## Goal

Captcha nie jest tryable. Challenge, bot wall, „verify you are human” na artefakcie = cisza. Gość nie klika w bramkę.

## Files likely touched

- `influenzer/host.py` — classify CAPTCHA / bot-wall evidence as not tryable
- `influenzer/hom.py` — fail closed at score time
- `influenzer/hom_draft.py` — refuse leaked draft scores
- `influenzer/playbook.py` — record the HN gate
- `tests/test_e2e_gates.py` — detector, score, and leaked-draft coverage

## Test plan

- Run the CAPTCHA e2e gate and the focused e2e/draft suites
- Run existing pack suite to check neighboring gates; record unrelated operator-suite failures if present

## Non-goals

- Do not click, solve, or bypass CAPTCHA challenges
- Do not add network probing or collection
- Do not classify product features that merely mention CAPTCHA as a blocked artifact

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
