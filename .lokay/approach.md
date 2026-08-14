# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=111 -->

Repository: `mikolaj92/influenzer`  
Issue: #111 — Zły JSON albo nie-UTF8 z gh to cisza, nie wyjątek

## Goal

Zły JSON albo nie-UTF8 z gh to cisza, nie wyjątek. Pętla żyje. Decode/parse fail-closed.

## Files likely touched

- `github_survey/gh.py` — decode `gh` stdout/stderr as UTF-8; bad JSON / non-UTF8 is empty look
- `influenzer/brief_scan.py`, `influenzer/scan_due.py`, `influenzer/hom_feedback.py` — decode/parse exceptions stay silence so the loop lives
- `tests/test_github_survey.py`, `tests/test_github_feedback.py`, `tests/test_scan_due.py`, `tests/test_hom_watch.py`

## Test plan

- `python -m pytest tests/test_github_survey.py tests/test_github_feedback.py tests/test_scan_due.py tests/test_hom_watch.py tests/test_scan_path.py tests/test_tick_loop.py -q`

## Non-goals

- (none stated)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Collector boundary: if implementation introduces unbounded collection, ship only a bounded collector patch that starts durably in the background after merge. The coding agent and mill must not populate data or wait for collection to finish.
- No explicit file paths in issue; infer from repo inspection.
