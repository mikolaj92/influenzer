# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=76 -->

Repository: `mikolaj92/influenzer`  
Issue: #76 — URL artefaktu tylko z zaufanego hosta

## Goal

URL artefaktu tylko z zaufanego hosta (github.com i to co sami allowlistujemy). Inny host nie jest tryable i nie jest Show HN. Żadnych skracaczy, UTM-farm, „kliknij tu”.

## Files likely touched

- `github_pack/classify.py` — tryable README+URL must be https on github.com (or an explicit allowlist). Shortener / UTM-farm / “kliknij tu” is silence.
- `github_pack/pack.py` — pack stays silent when the README/homepage URL is off-allowlist.
- `influenzer/playbook.py` — score-side host/UTM/shortener/click-here predicates.
- `influenzer/hom.py` / `influenzer/hom_draft.py` — not tryable, not Show HN.
- `tests/test_github_pack.py`, `tests/test_hom_operator.py`

## Test plan

- `python -m unittest tests.test_github_pack tests.test_hom_operator`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
