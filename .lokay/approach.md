# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=169 -->

Repository: `mikolaj92/influenzer`  
Issue: #169 — Drugi kąt na to samo wydanie to cisza

## Goal

Drugi kąt na to samo wydanie to cisza. Ten sam tag/release już miał historię — nie odgrzewamy shipu co poniedziałek.

## Files likely touched

- `influenzer/hom.py` — identity of a release/tag story and drop of a second angle
- `influenzer/storage.py` — machine-wide release history from admitted briefs
- `influenzer/scheduler.py` — fail-closed on tick even if ingest bypassed the gate
- `influenzer/brief_admit.py` — Monday look stays silent when the tag/release already had a story
- `tests/test_brief_admit.py`, `tests/test_e2e_gates.py`, `tests/test_hom_operator.py`

## Test plan

- Unit: same repo+tag via `www.github.com` / different copy is one release
- Admit: a later look for a previously told tag/release is `same_release`
- Tick: a new angle on a release that already had history is kill, no draft

## Non-goals

- Do not reuse `#71` (same body hash) or `#64` (Monday without any history)
- Do not silence a genuinely new tag/release

## Notes

- Neighbor of `#65` (look idempotent), `#71` (same text), `#64` (Monday without history). Here the key is the release/tag, not the hash of the copy.
- `already_told` still matches exact artifact URLs. This gate covers the same tag under another URL spelling, or a tag fact later promoted to a release.
- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
