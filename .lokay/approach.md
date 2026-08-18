# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=172 -->

Repository: `mikolaj92/influenzer`  
Issue: #172 — Ten sam URL już był na HN = cisza

## Goal

Ten sam URL już był na HN = cisza. Nie resubmitujemy. Seminarium nie znosi powtórki linku.

## Files likely touched

- `influenzer/hom.py` — canonical HN URL identity and fail-closed repeat gate
- `influenzer/storage.py` — machine-wide history of URLs previously dressed for HN
- `influenzer/scheduler.py` — drop a repeated HN URL before persisting a draft
- `influenzer/brief_admit.py` — scan admission stays silent when HN already used the URL
- `influenzer/playbook.py`, `skills/influenzer-hn/SKILL.md` — encode the no-resubmit rule
- `tests/test_e2e_gates.py` — old HN URL stays silent after the 48h camp expires

## Test plan

- Targeted HN URL key and tick tests
- Full `tests.test_e2e_gates` plus focused operator/admit suites

## Non-goals

- No HN network collector or submission-history scrape
- Do not infer that every GitHub brief was posted to HN; history comes from stored HN drafts
- Do not change the existing 48h in-thread camp or same-release/body gates

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
