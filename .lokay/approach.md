# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=89 -->

Repository: `mikolaj92/influenzer`  
Issue: #89 — Puste repo nie ma witryny

## Goal

Puste repo nie ma witryny. Brak drzewa albo brak README → look milczy. To nie „README bez GIF-a” (#48) — tu nie ma nawet kartki.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_empty_repo` + wave copy
- `influenzer/brief_scan.py` — `repo_is_empty` / missing README is silence
- `influenzer/brief_admit.py` — packed empty-repo facts stay silent
- `influenzer/hom.py` / `influenzer/hom_draft.py` / `influenzer/hom_feedback.py` — score, dress, inbound
- tests for the gate, distinct from README-without-demo

## Test plan

- `uv run python -m unittest` on brief admit, operator, draft, feedback

## Non-goals

- Do not treat a present README without a GIF as this gate (#48).
- Do not clone, make a worktree, or run the project.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Same fail-closed shape as #90 (fork is not a website).
