# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=166 -->

Repository: `mikolaj92/influenzer`  
Issue: #166 — Przeprosiny bez shipu to cisza

## Goal

Przeprosiny bez shipu to cisza. „We hear you”, crisis post, sorry bez nowego artefaktu = nie kąt. Changelog albo nic.

## Files likely touched

- `github_pack/classify.py` — pack-side apology detector
- `github_pack/pack.py` — survey silence unless a separate release/merge exists
- `influenzer/playbook.py` — shared detector and shipped-fix check
- `influenzer/hom.py` — social kill / changelog-only score
- `influenzer/hom_draft.py` — independent leaked-draft guard
- `influenzer/brief_admit.py` — fail closed for apology-only packs
- `tests/test_e2e_gates.py`
- `tests/test_github_pack.py`
- `tests/test_hom_draft.py`
- `tests/test_brief_admit.py`

## Test plan

- Run targeted apology tests across pack, score, draft, and admission
- Compile changed Python modules and run `git diff --check`

## Non-goals

- Generating apology copy or probing external artifacts
- Silencing an apology paired with a separately shipped fix
- Changing unrelated waitlist, event, or maintenance gates

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
