# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=46 -->

Repository: `mikolaj92/influenzer`  
Issue: #46 — Waitlista to nie ship

## Goal

„Coming soon”, „join the list”, „sign up to get access” nie jest tryable i nie jest Show HN. `claims_ship`/`tryable` padają. HN/X/shorts milczą. GitHub changelog wolno.

`looks_like_waitlist` ma być fail-closed: waitlisty nie publikować na HN/X/shorts. Nie live. Jedna historia.

## Files likely touched

- `influenzer/playbook.py` — broaden `WAITLIST_RE` / `looks_like_waitlist`
- `github_pack/classify.py` — keep pack-time waitlist silence on the same phrases
- `tests/test_e2e_gates.py` — HN/X/shorts kill + changelog-only without a ship claim

## Test plan

- `python -m unittest tests.test_e2e_gates.OrderedLiveGateTests.test_waitlist_is_not_a_ship_on_hn_x_or_shorts`
- `python -m unittest tests.test_hom_operator.ScoreBriefTests.test_waitlist_ship_claim_is_killed tests.test_github_pack.PackSilenceTests.test_waitlist_release_is_silence`

## Non-goals

- Do not invent a new arena path named `HN/X/shorts`.
- Do not start a collector or publish live.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Existing score/draft already kill waitlists on social arenas; the leak was the narrow regex.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
