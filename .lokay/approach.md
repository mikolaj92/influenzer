# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=158 -->

Repository: `mikolaj92/influenzer`  
Issue: #158 — Nieoznaczona reklama to cisza

## Goal

Nieoznaczona reklama to cisza. Paid, partner, affiliate bez etykiety w kącie = kill. Disclose albo nic.

## Files likely touched

- `commercial_disclosure/__init__.py` (shared fail-closed gate)
- `influenzer/domain.py`, `influenzer/playbook.py`, `influenzer/hom.py`, `influenzer/hom_draft.py`
- `influenzer/policy.py`, `influenzer/scheduler.py`, `influenzer/adapters/base.py`
- `github_pack/pack.py`, `github_feedback/feedback.py`
- `skills/influenzer-reddit/SKILL.md`
- targeted tests under `tests/`

## Test plan

- `python3 -m unittest` for e2e gates, policy, adapters, pack, feedback, operator, product, domain

## Non-goals

- Do not invent a live Ads spend path.
- Do not treat authorship disclosure (`I built`) as a commercial label.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
