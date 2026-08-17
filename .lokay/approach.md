# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=30 -->

Repository: `mikolaj92/influenzer`  
Issue: #30 — List tylko gdy człowiek coś może zrobić

## Goal

List tylko gdy człowiek coś może zrobić. Patch, typo, wewnętrzne — newsletter nie jest areną. Score bierze letter wyłącznie przy ship+tryable (zmiana dla obcego). Inaczej cisza na tym kanale, changelog może iść na GitHub.

## Files likely touched

- `influenzer/hom.py` — score takes letter only on ship+tryable; otherwise changelog
- `influenzer/hom_draft.py` — leaked newsletter draft without ship+tryable stays undressable
- `influenzer/playbook.py` — letter wave names the ship+tryable bar
- `skills/influenzer-newsletter/SKILL.md` — same bar in the costume skill
- `tests/test_e2e_gates.py` — fail-closed cases (tryable-no-ship, artifact-only, feedback-only)

## Test plan

- `python -m pytest tests/test_e2e_gates.py::OrderedLiveGateTests::test_letter_only_when_a_stranger_can_try_it tests/test_e2e_gates.py::OrderedLiveGateTests::test_letter_without_a_gift_is_silence tests/test_e2e_gates.py::OrderedLiveGateTests::test_letter_without_a_surname_is_silence -q`
- Plus a focused operator/draft smoke if those stay green

## Non-goals

- Do not publish, do not go live, do not open a second story.
- Changelog on GitHub may still exist; the letter channel stays silent without ship+tryable.

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
