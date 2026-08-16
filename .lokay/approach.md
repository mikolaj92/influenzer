# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=55 -->

Repository: `mikolaj92/influenzer`  
Issue: #55 — Bluesky bez feedu to pół gry

## Goal

Draft na bsky milczy, jeśli fakty nie wskazują packa/custom feedu — sam artifact (#35) nie wystarczy do retencji. Kostium: pack onboarduje, feed trzyma. Bez packa/feedu nie publikować na Bluesky.

## Files likely touched

- `influenzer/playbook.py` — cafe pack+feed detectors and sit preferred Bluesky
- `influenzer/hom.py` — fail-closed Bluesky gate
- `influenzer/hom_draft.py` — undress artifact-only cafe
- `tests/test_e2e_gates.py`
- `tests/test_hom_draft.py`

## Test plan

- `python -m pytest tests/test_e2e_gates.py tests/test_hom_draft.py tests/test_hom_operator.py -k "bluesky or cafe or pack_without_feed or every_arena_dresser or every_arena_has_a_fail" -q`

## Non-goals

- Do not sit on YouTube/X/shorts (other issues).
- Do not change github_pack (GitHub survey pack, not a Bluesky starter pack).
- Do not enable live publish.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
