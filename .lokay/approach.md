# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=138 -->

Repository: `mikolaj92/influenzer`  
Issue: #138 — Wydarzenie nie jest shipem

## Goal

Wydarzenie nie jest shipem. Webinar, meetup, calendar, „join us Thursday” = cisza. Kalendarz nie jest artefaktem.

## Files likely touched

- `influenzer/playbook.py` — `EVENT_RE` / `looks_like_event` / `EVENT_NOT_A_SHIP`
- `influenzer/hom.py` — score kill/changelog
- `influenzer/hom_draft.py` — undress event copy
- `github_pack/classify.py` + `github_pack/pack.py` — inbound event silence
- `influenzer/brief_admit.py` — admit fail-closed
- `tests/test_e2e_gates.py`, `tests/test_hom_operator.py`, `tests/test_github_pack.py`, `tests/test_brief_admit.py`

## Test plan

- `python -m pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_event_is_not_a_ship_on_hn_x_or_shorts tests/test_hom_operator.py::ScoreBriefTests::test_event_is_not_a_ship tests/test_hom_operator.py::ScoreBriefTests::test_event_ship_claim_is_killed tests/test_hom_operator.py::ScoreBriefTests::test_event_without_ship_claim_is_changelog_only tests/test_github_pack.py::PackSilenceTests::test_webinar_release_is_silence tests/test_brief_admit.py::AdmitAndComposeTests::test_event_pack_is_silence_not_a_ship -q`

## Non-goals

- Do not treat a calendar year mention as an invite.
- A calendar invite is not a ship artifact even with a GitHub URL.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
