# influenzer-publish

Inspect policy-gated publish plans and scheduler intent.

## Rules
- Shipped v1 platform adapters are dry-run-only. Live create and live readback are rejected; no live organic publication or live canaries are available.
- `influenzer-tick-all` scores pending HoM briefs into drafts or explicit kills; it ignores CLI `--live` and supplies no due plans, so it does not dispatch plans even with `scheduler.live_enabled=true`.
- In the scheduler Python API, durable live intent + a current hash-bound PolicyActivationGrant can authorize dispatch of explicitly supplied `DueWork`, not platform publication. Shipped adapters reject `dry_run=False` without platform mutation; the scheduler records failed plans/attempts.
- Always-on loop (Mac mini): `influenzer-tick --interval 300` or `influenzer tick-loop`. `--once` is score-only unless `--pass-if-due`. Not a laptop LaunchAgent. No live social from this path.
- One PublishPlan targets one platform account. Fanout means independent plans.
- Never place secrets in config/DB/logs; use `credential_ref` only (`env:` / `keychain:`).

## Example
```bash
influenzer-tick-all --config ~/.hermes/influenzer/config.json
# CLI --live is ignored for tick-all:
influenzer-tick-all --live
```
