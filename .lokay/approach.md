# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=112 -->

Repository: `mikolaj92/influenzer`  
Issue: #112 — Draft nie pinguje ludzi

## Goal

Draft nie pinguje ludzi. Żadnego znaku at plus login w body. Nie zaciągamy kogoś do wątku. Strip albo cisza.

## Files likely touched

- `influenzer/playbook.py` — detect `@login`, strip it, fail-closed on operator summons
- `influenzer/hom_draft.py` — strip mentions from wearable copy; silence leftover summons
- `tests/test_hom_draft.py`
- `tests/test_hom_operator.py`

## Test plan

- `python -m pytest tests/test_hom_draft.py tests/test_hom_operator.py tests/test_hom_pass.py tests/test_hom_feedback.py tests/test_hom_outbox.py`

## Non-goals

- Do not change github_feedback ingest (`@login:` stays as source attribution).
- Do not treat emails or URL paths (`medium.com/@someone`) as pings.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Fail-closed: operator `@login` in a signal = kill / undressable. Feedback `@login:` prefix is stripped from the dressed body.
