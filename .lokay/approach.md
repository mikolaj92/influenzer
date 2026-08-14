# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=128 -->

Repository: `mikolaj92/influenzer`  
Issue: #128 — Source-available to nie OSS

## Goal

Source-available to nie OSS. BUSL / Commons Clause / „fair code” / SSPL — nie wołamy open source. Można powiedzieć source-available. Kłamstwo licencyjne = cisza.

## Files likely touched

- `influenzer/playbook.py` — detect BUSL / Commons Clause / fair code / SSPL / source-available plus an OSS sticker
- `influenzer/hom.py` — kill `source_available_not_oss`
- `influenzer/hom_draft.py` — refuse to dress a license lie even if score says draft
- `tests/test_hom_operator.py`, `tests/test_hom_draft.py` — fail-closed cases; source-available alone may speak

## Test plan

- `python -m unittest tests.test_hom_operator tests.test_hom_draft`

## Non-goals

- Do not change `LICENSE` itself (that is #127: file on disk).
- Do not require a LICENSE file here; this issue is license *kind*, not the file.
- Honest "source-available" / "not open source" may still draft.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
