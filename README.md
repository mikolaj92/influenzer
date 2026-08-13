# Influenzer

Local multi-project social operator for organic posting and campaign planning.

Influenzer runs on your machine. Every app has its own Project + BrandProfile. The builder is also a first-class Project (`kind=builder`) with a separate profile and accounts. Dry-run is default; live organic publish needs durable live intent plus a hash-bound policy grant. Paid campaigns are planning/export only — no spend APIs.

## Install

```bash
hermes plugins install PATH_OR_GIT_SOURCE --enable
```

Influenzer is a locally executed Hermes plugin, not a hosted service. Hermes installs it from a plugin source; runtime state, scheduling, policies, and credentials remain on the user's machine. `plugin.yaml` and `__init__.py` are the plugin entry surface.

After install, Hermes may show [`after-install.md`](after-install.md).

## 3-minute local demo

```bash
python -m influenzer.cli --config /tmp/influenzer/config.json init --home /tmp/influenzer
python -m influenzer.cli --config /tmp/influenzer/config.json project create \
  --id app-1 --slug my-app --name "My App" --display-name "My App" \
  --voice product --audience customers --maintainer you --kind app
python -m influenzer.cli --config /tmp/influenzer/config.json project create \
  --id builder-1 --slug me --name Me --display-name Me \
  --voice builder --audience builders --maintainer you --kind builder
python -m influenzer.cli --config /tmp/influenzer/config.json content add \
  --project-id app-1 --content-id c1 --revision-id r1 \
  --body "Shipped dry-run adapters" --status ready
python -m influenzer.tick_all --config /tmp/influenzer/config.json
```

`influenzer-tick-all --live` is ignored. Only `scheduler.live_enabled=true` in config can authorize live mutation, and only with a current grant.

## Configure

Default config path:

```text
~/.hermes/influenzer/config.json
```

Override with `--config PATH` or `HERMES_INFLUENZER_CONFIG`.

```json
{
  "version": 1,
  "home": "~/.hermes/influenzer",
  "scheduler": { "live_enabled": false }
}
```

Secrets never go in config. Platform accounts store `credential_ref` only (`env:NAME` or `keychain:SERVICE/ACCOUNT`).

## Commands

| Command | Purpose |
| --- | --- |
| `influenzer init` | Create workspace home, config, state.db |
| `influenzer project create/show` | App or builder projects with BrandProfile |
| `influenzer content add` | Immutable project-scoped content revision |
| `influenzer campaign create` | Organic/paid plan (no spend) |
| `influenzer-tick-all` | Single scheduled mutator (dry-run default) |

## Platforms (v1 dry-run/contract)

Separate handlers: X, Bluesky, Mastodon, LinkedIn, Instagram, Facebook Pages.

Each dry-run create returns planned envelope fields for capabilities, official API selection note, media limits, rate/idempotency metadata, access/host requirements, and read-only readback/reconcile shape. Live canaries are ordered: Bluesky+Mastodon → X → LinkedIn → Meta.

## Skills

- `influenzer-profile`
- `influenzer-content`
- `influenzer-campaign`
- `influenzer-publish`
- `influenzer-hom` — first-person HoM notes (angles, arenas, acquisition/retention); canon: https://github.com/mikolaj92/influenzer-playbook

## Tests

```bash
python -m unittest discover -s tests
python tools/hygiene_check.py .
```

## Safety

- No Ads spend path.
- No plaintext secrets in config/DB/logs/receipts.
- No blind retry after ambiguous create — use `unknown` + reconcile.
- Cross-project references are denied.
- SSRF guard: HTTPS-only, host binding, private IP denial, redirect revalidation, size/type bounds.
