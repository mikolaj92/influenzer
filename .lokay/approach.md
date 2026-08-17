# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=138 -->

Repository: `mikolaj92/influenzer`  
Issue: #138 — Wydarzenie nie jest shipem

## Goal

Wydarzenie nie jest shipem. Webinar, meetup, calendar, „join us Thursday” = cisza. Kalendarz nie jest artefaktem.

## Files likely touched

- `influenzer/domain.py` — event detector (`looks_like_event`, `EVENT_NOT_A_SHIP`)
- `influenzer/scheduler.py` — operator tick + live plan deny
- `influenzer/storage.py` — persist_operator_decision fail-closed
- `influenzer/content.py` — revision create/persist refuse event body
- `influenzer/adapters/base.py` — adapter refuse event body
- `tests/test_e2e_gates.py` — fail-closed cases

## Test plan

- `python -m pytest tests/test_e2e_gates.py tests/test_operator.py tests/test_adapter_contract.py -q`

## Non-goals

- Do not retune HOM/playbook in this patch; those files are outside localize scope.
- A calendar invite is not a ship artifact even with a GitHub URL.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
