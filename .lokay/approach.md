# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=49 -->

Repository: `mikolaj92/influenzer`  
Issue: #49 — Reddit bez ujawnienia to spam

## Goal

Draft na village: native self-post, disclose że to nasze, repo na dole albo w pierwszym komentarzu. Bez tego — cisza, nawet gdy sub jest nazwany (#31).

## Files likely touched

- `influenzer/playbook.py` — sit preferred Reddit; `reddit_reason` requires named room + disclose + repo
- `influenzer/hom.py` — village gate uses `reddit_reason`
- `influenzer/hom_draft.py` — dress Reddit is silence without disclosure
- `tests/test_e2e_gates.py` — one village story: no disclose = kill; disclose+repo = draft
- `tests/test_hom_draft.py` — leaked Reddit score still undressable without ujawnienie

## Test plan

- `pytest tests/test_e2e_gates.py tests/test_hom_draft.py` plus the existing named-room score test

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
