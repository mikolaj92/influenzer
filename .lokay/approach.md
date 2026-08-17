# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=143 -->

Repository: `mikolaj92/influenzer`  
Issue: #143 — Kalendarz nie pisze za nas

## Goal

Holiday / repo birthday / happy Friday copy is silence, not a product.
Neighbor of #138 (event is not a ship: meetup/webinar) and #131 (world
commentary). This is the date as a greeting, not a tryable drop.

## Files likely touched

- `influenzer/playbook.py` — `looks_like_calendar_filler`, reason, regex
- `influenzer/hom.py` — score kills calendar filler
- `influenzer/hom_draft.py` — dress refuses calendar filler
- `github_pack/classify.py` / `github_pack/pack.py` — pack silences it
- `influenzer/brief_admit.py` — admit silences it
- tests: operator, draft, e2e, pack, admit

## Test plan

- Detector matches holiday / repo birthday / happy Friday / Polish święta
- Detector misses product copy, "shipped Friday", "calendar year", "happy path"
- Score kills; leaked draft still dresses to None
- Pack and admit stay silent

## Non-goals

- Do not widen #138 meetup/webinar event gate
- Do not invent holiday-calendar posts
- Do not treat a Friday ship as filler
