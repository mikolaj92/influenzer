# influenzer-publish

Inspect policy-gated publish plans and scheduler intent.

## Rules
- Dry-run by default. Live organic publish requires durable live intent + hash-bound PolicyActivationGrant.
- `influenzer-tick-all` scores pending HoM briefs into drafts or explicit kills; it ignores CLI `--live` for publish. Only `scheduler.live_enabled=true` authorizes live mutation.
- Always-on loop (Mac mini): `influenzer-tick --interval 300` or `influenzer tick-loop`. `--once` is score-only unless `--pass-if-due`. Not a laptop LaunchAgent. No live social from this path.
- One PublishPlan targets one platform account. Fanout means independent plans.
- Never place secrets in config/DB/logs; use `credential_ref` only (`env:` / `keychain:`).

## Example
```bash
influenzer-tick-all --config ~/.hermes/influenzer/config.json
# CLI --live is ignored for tick-all:
influenzer-tick-all --live
```
