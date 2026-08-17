# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=36 -->

Repository: `mikolaj92/influenzer`  
Issue: #36 — Shorts bez haczyka 1–3s = cisza

## Goal

Shorts to swipe, nie VOD. Bez haczyka 1–3s (obraz+głos+tekst razem) — cisza na fair. `has_fair_hook` fail-closed. Ten sam cut co YouTube nie przechodzi (inne kostiumy, nie wklejka).

## Files likely touched

- `influenzer/playbook.py` — tighten `FAIR_HOOK_RE`, add `fair_hook_reason`
- `influenzer/hom.py` — score fail-closed on missing hook (ignore `kind=hook` label)
- `influenzer/hom_draft.py` — dress only a real 1–3s hook, never a cinema one-liner
- `skills/influenzer-shorts/SKILL.md`
- `skills/influenzer-youtube/SKILL.md`
- `tests/test_e2e_gates.py`

## Test plan

- `python -m pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_shorts_without_hook_or_youtube_cut_is_silence tests/test_e2e_gates.py::OrderedLiveGateTests::test_shorts_without_loop_or_with_cta_and_loop_is_silence tests/test_hom_operator.py::HomOperatorTests::test_shorts_without_hook_is_killed tests/test_hom_draft.py::HomDraftTests::test_shorts_loop_without_cta_can_still_dress -q`

## Non-goals

- Do not change the Shorts loop / CTA pair from #59.
- Do not publish live. One story. Small score/dress block only.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Pair of #59 (loop). A cinema 0.5s title+thumb is not a fair hook.
