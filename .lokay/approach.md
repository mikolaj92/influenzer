# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=28 -->

Repository: `mikolaj92/influenzer`  
Issue: #28 — Żadnego żebrania o gwiazdki, upvote, follow, RT

## Goal

Żadnego żebrania. Jeśli fakty albo draft proszą o gwiazdkę, upvote, follow, RT — score/dress pada na kill albo changelog, nie na kąt. HN i GitHub tym umierają.

## Files likely touched

- `github_pack/pack.py` — fail-closed pack silence on a star / upvote / follow / RT ask in facts, README, or description
- `github_pack/__init__.py` — export the detector
- `influenzer/hom_draft.py` — same ask is undressable even when score says draft (no `github_pack` import)
- `skills/influenzer-hn/SKILL.md` — never solicit stars / follows / RTs either
- `tests/test_github_pack.py`
- `tests/test_hom_draft.py`
- `tests/test_e2e_gates.py`

## Test plan

- `python -m pytest tests/test_github_pack.py tests/test_hom_draft.py tests/test_e2e_gates.py`

## Non-goals

- Do not move the detector into `playbook.py` (out of localize scope).
- Do not treat a dead star *count* as this gate; that remains `dead_star_count`.
- Product copy such as "follow the README" stays.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Small pack/dress klocek: `solicit_gesture`. Dress keeps a local copy because `hom_draft` must not import `github_pack`.
