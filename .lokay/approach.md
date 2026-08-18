# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=154 -->

Repository: `mikolaj92/influenzer`  
Issue: #154 — Martwy TLS nie jest tryable

## Goal

A recorded cert error, mixed content, or HTTPS the browser rejects is not
tryable. Silence on Show HN and ship claims. Do not click the warning.
This is recorded TLS evidence, not a 404 (#92) and not the https scheme (#77).

## Files likely touched

- `influenzer/playbook.py` — fail-closed `DEAD_TLS_RE` / `looks_like_dead_tls`
- `influenzer/hom.py` — ship/social kill, otherwise changelog
- `influenzer/hom_draft.py` — undress even if a score says draft
- `tests/test_hom_operator.py`
- `tests/test_hom_draft.py`
- `tests/test_e2e_gates.py`

## Test plan

- `python -m pytest tests/test_hom_operator.py::PlaybookCopyTests::test_dead_tls_is_not_tryable tests/test_hom_operator.py::ScoreBriefTests::test_dead_tls_ship_claim_is_killed tests/test_hom_operator.py::ScoreBriefTests::test_dead_tls_without_ship_claim_is_changelog_only tests/test_hom_operator.py::ScoreBriefTests::test_product_copy_without_dead_tls_can_still_draft tests/test_hom_draft.py::HomDraftCostumeTests::test_dead_tls_is_undressable_even_when_score_says_draft tests/test_hom_draft.py::HomDraftCostumeTests::test_product_copy_without_dead_tls_can_still_dress tests/test_e2e_gates.py::OrderedLiveGateTests::test_dead_tls_is_silence_not_tryable -q`

## Non-goals

- Live TLS handshake or browser probe of artifact URLs (HOM stays rule-only)
- Dead 404/410 links (#92) and https-only scheme (#77)
- Login wall 401/403 (#126) and listed release-asset 404 (#171)
- github_survey / github_pack collectors

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Same shape as dead-link / login-wall: text evidence in the brief, not a
  network check. Bare `certificate error` / `mixed content` / `martwy TLS`
  is this gate. A working handshake stays.
- Do not call “click through the warning”.
- Collector boundary: no unbounded collection.
