# influenzer-publish

Inspect policy-gated publish plans and scheduler intent.

## Rules
- Dry-run by default. Live organic publish requires durable live intent + hash-bound PolicyActivationGrant.
- `influenzer-tick-all` ignores CLI `--live`; only `scheduler.live_enabled=true` authorizes live mutation.
- One PublishPlan targets one platform account. Fanout means independent plans.
- Never place secrets in config/DB/logs; use `credential_ref` only (`env:` / `keychain:`).

## Example
```bash
influenzer-tick-all --config ~/.hermes/influenzer/config.json
# CLI --live is ignored for tick-all:
influenzer-tick-all --live
```
