# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=37 -->

Repository: `mikolaj92/influenzer`  
Issue: #37 — YouTube bez pary tytuł+obietnica = cisza

## Goal

YouTube to opakowanie, nie odcinek. Bez pary tytuł+obietnica (jedna wiadomość w 0,5s) — cisza na cinema. Żadnego „hey guys”, loga, intro. Playbook ma `has_cinema_package` — ma być fail-closed jak sub na Reddicie.

## Files likely touched

- `influenzer/playbook.py`
- `skills/influenzer-youtube/SKILL.md`
- `tests/test_e2e_gates.py`

## Test plan

- `pytest` cinema/YouTube gates in `tests/test_e2e_gates.py`
- existing `test_youtube_without_package_is_killed` / `test_youtube_with_package_drafts_cinema_only`

## Non-goals

- seating Shorts (issue #36 already owns the fair hook; `choose_arena` still does not sit Shorts)
- live publish / a second social costume
- changing `hom.py` / `hom_draft.py` (out of localize scope)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- Cinema pair is title+thumb / tytuł+obietnica in 0.5s. A `kind=package` label, the word title, a poster, or a fair 1–3s hook is not the pair.
- Preferred YouTube now sits so score can kill `cinema_missing_package` instead of leaking a Show HN. No-pref still falls to github/HN.
