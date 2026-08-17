# Approach plan

<!-- lokay-approach source=deterministic repo=mikolaj92/influenzer issue=47 -->

Repository: `mikolaj92/influenzer`  
Issue: #47 — Sekret nie wychodzi w kącie społecznym

## Goal

Jeśli fakt albo body wygląda na token, hasło albo klucz (wzorce: env, bearer, sk-, ghp, keychain) — dress/outbox milczy, brief pada na kill. Żadnego „prawie zredagowane”.

## Files likely touched

- `influenzer/playbook.py` — mały klocek `looks_like_secret` / `SECRET_RE`
- `influenzer/hom.py` — score kill
- `influenzer/hom_draft.py` — dress milczy
- `influenzer/hom_outbox.py` — wearable = cisza
- `influenzer/brief_admit.py` — scan/admit nie zapisuje briefu
- `tests/test_brief_admit.py`
- `tests/test_brief_scan_cli.py`
- `tests/test_e2e_gates.py`
- `tests/test_envelope.py`
- `tests/test_hom_outbox.py`

## Test plan

- Run the smallest useful tests for files touched:
  `tests/test_brief_admit.py tests/test_brief_scan_cli.py tests/test_e2e_gates.py tests/test_envelope.py tests/test_hom_outbox.py`

## Non-goals

- Redakcja „prawie zredagowane”
- Worek na wszystkie vaulty — tylko wzorce z issue (env, bearer, sk-, ghp, keychain)

## Notes

- Trust intentional issue; this plan is evidence for later review, not a human gate.
- Coding agent may refine details but should stay on the stated goal and non-goals.
- Fail-closed: sekret nie publikować, nie live.
