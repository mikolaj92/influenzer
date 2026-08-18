# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=153 -->

Repository: `mikolaj92/influenzer`  
Issue: #153 — Linktree nie jest artefaktem

## Goal

Linktree / Carrd / bio site / a list of links instead of a product is
silence. An artifact is a product, not a link board.

## Files likely touched

- `influenzer/playbook.py` — detector, hosts, reason
- `influenzer/hom.py` — score + HN gate
- `influenzer/hom_draft.py` — refuse to dress a leaked draft
- `influenzer/brief_admit.py` — admit silence
- `github_pack/classify.py` / `github_pack/pack.py` — pack silence
- `skills/influenzer-hn/SKILL.md` — seminar copy
- tests next to the deck gate (`#151`)

## Test plan

- Detector: Linktree / Carrd / bio site / lista linków kill; README
  link and product copy stay
- Host-only URL (linktr.ee, carrd.co, bio.site) is not tryable
- Pack / admit / score / dress fail closed
- A link page next to a repo can stay as evidence when copy is product

## Non-goals

- Do not steal `#139` (CTA / link in bio on a looping cut)
- Do not change trusted-host allowlist (`#76`) beyond refusing known
  link-board hosts as the artifact

## Notes

- Same fail-closed shape as `#151` (deck is not an artifact).
- Neighbor of `#139` (CTA in DM / link in bio) and `#76` (trusted host):
  here it is a list page, not a CTA.
