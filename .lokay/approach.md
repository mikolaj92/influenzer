# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=155 -->

Repository: `mikolaj92/influenzer`  
Issue: #155 — Dysk w chmurze nie jest witryną

## Goal

Drive / Dropbox / WeTransfer as an artifact is silence. A file share is not a product.

Fail closed at score, dress, pack, and admit — same shape as #151 (deck) and #153 (linktree). Neighbor of #76 (trusted host).

## Files likely touched

- `influenzer/playbook.py` — detector, hosts, reason, unquotable
- `influenzer/hom.py` — score kill + URL-only gate
- `influenzer/hom_draft.py` — dress silence
- `influenzer/brief_admit.py` — admit silence
- `github_pack/classify.py` / `github_pack/pack.py` — pack silence
- `skills/influenzer-hn/SKILL.md` — seminar wave
- tests: `test_e2e_gates.py`, `test_hom_operator.py`, `test_hom_draft.py`, `test_brief_admit.py`, `test_github_pack.py`

## Test plan

- Run the smallest useful tests for files touched

## Non-goals

- Do not treat a repo next to a drive as silence unless the copy is the file share
- Do not confuse Google Slides (deck) with Drive / Docs (file)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Reason: `cloud_drive_not_a_site`.
