# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=58 -->

Repository: `mikolaj92/influenzer`  
Issue: #58 — Dwór nie jest kanałem launchu

## Goal

Dwór nie jest kanałem launchu. `claims_ship` / Show-HN energia nie idzie na LinkedIn. Court = insight z roboty (filary), nie „właśnie wypuściliśmy”. Ship → github/hn. LinkedIn bez insightu poza launchu = cisza.

## Files likely touched

- `influenzer/playbook.py` — court is not a launch channel; preferred LinkedIn sits only without `claims_ship`
- `influenzer/hom.py` — score LinkedIn through `court_reason`
- `influenzer/hom_draft.py` — refuse a leaked court/launch draft
- `tests/test_e2e_gates.py` — fail-closed e2e for ship/Show-HN on court vs insight

## Test plan

- `python -m unittest tests.test_e2e_gates tests.test_hom_operator.PlaybookCopyTests tests.test_hom_draft.HomDraftCostumeTests.test_linkedin_fold_is_insight_first_and_under_210 -v`

## Non-goals

- Not #33 (fold without pitch) and not #26 (launch window).
- Do not make LinkedIn a first launch costume. Ship stays on github/hn.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Localize listed only `tests/test_e2e_gates.py`; inspection put the gate in playbook + score + dress.
