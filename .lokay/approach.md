# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=31 -->

Repository: `mikolaj92/influenzer`  
Issue: #31 — Reddit bez nazwanego suba nie istnieje

## Goal

Reddit bez nazwanego suba nie istnieje. Score nie bierze village, jeśli fakty nie wskazują konkretnego subreddita. Inaczej github/hn albo cisza. Żadnego blastu po r/programming i kuzynach.

## Files likely touched

- `skills/influenzer-reddit/SKILL.md` — village does not exist without a named `r/` room
- `tests/test_e2e_gates.py` — fail-closed `has_named_subreddit` / `reddit_no_room` (preferred Reddit dies; no-pref falls to HN)

Score/dress already kill village without `r/Name` in `influenzer/playbook.py` + `influenzer/hom.py` + `influenzer/hom_draft.py`. This issue pins the costume and the e2e gate; it does not re-open those files.

## Test plan

- `python -m pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_reddit_without_named_sub_is_not_village tests/test_e2e_gates.py::OrderedLiveGateTests::test_reddit_without_disclosure_is_silence -q`

## Non-goals

- Do not publish, do not go live, do not open a second story.
- Do not blast the same story across r/programming and cousins.
- Do not treat a `kind=subreddit` label as a named room.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
