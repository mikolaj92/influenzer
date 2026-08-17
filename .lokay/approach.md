# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=33 -->

Repository: `mikolaj92/influenzer`  
Issue: #33 — LinkedIn to dwór, nie stoisko

## Goal

LinkedIn fold (~210 chars) is insight, not pitch, CTA, or URL. A draft that starts with CTA, a URL, or “we’re launching” is silence on court (other arena or kill). Does not publish. Does not go live. One story.

## Files likely touched

- `influenzer/hom_draft.py` — court dresser: skip stall lines; fail-closed if fold is pitch/CTA/URL
- `skills/influenzer-linkedin/SKILL.md` — fold is insight or silence
- `tests/test_hom_draft.py` — leaked-score silence + insight-first fold
- `tests/test_e2e_gates.py` — compose_draft refuses a stall fold

## Test plan

- `python -m pytest tests/test_hom_draft.py::HomDraftCostumeTests tests/test_e2e_gates.py::OrderedLiveGateTests::test_court_is_not_a_launch_channel tests/test_e2e_gates.py::OrderedLiveGateTests::test_linkedin_fold_is_insight_not_pitch_cta_or_url -q`

## Non-goals

- No playbook/scoring rewrite outside the LinkedIn dress path
- No publish / live / multi-story changes

## Notes

- Leak before the patch: `_PITCH_LINE_RE` missed `we're launching` / `we are launching` / `Learn more` / `Comment if`, so those lines dressed as the fold.
- Court already had launch-energy kill via `court_reason`; this issue is the dress fold, not the launch-channel gate.
- Collector boundary: no collector.
