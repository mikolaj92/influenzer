# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=118 -->

Repository: `mikolaj92/influenzer`  
Issue: #118 — Liczba w kącie musi być w briefie

## Goal

Liczba w kącie musi być w briefie. Dress nie dopisuje „10x”, „1M users”, benchmarków. Brak liczby w faktach = brak liczby w body. Zmyślona metryka = cisza.

## Files likely touched

- `influenzer/playbook.py` — fail-closed metric tokens; number in body must already be a fact
- `tests/test_hom_operator.py` — invented 10x / 1M users / benchmark = silence
- `tests/test_hom_draft.py` — dress does not add metrics; sourced number may stay

## Test plan

- `python3 -m pytest tests/test_hom_operator.py tests/test_hom_draft.py -q`

## Non-goals

- Do not kill a brief merely because a fact already contains a number
- Do not invent dress-time metrics such as 10x, 1M users, or benchmarks

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
