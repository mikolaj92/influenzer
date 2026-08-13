# Influenzer

Local multi-project social operator for organic posting and campaign planning.

Influenzer runs on your machine as a **local 24/7 Head of Marketing operator**. Every app has its own Project + BrandProfile. The builder is also a first-class Project (`kind=builder`) with a separate profile and accounts.

On each `influenzer-tick-all` (or an always-on `influenzer-tick` loop on a Mac mini), pending **briefs** (many facts) are scored: **kill**, **changelog-only**, or **one-angle draft** in **one primary arena**. Scoring is fail-closed: borderline briefs do not leak a social draft. Not every commit/event becomes a post. Drafts are local; they are not auto-published. Dry-run is default; live organic publish needs durable live intent plus a hash-bound policy grant. Paid campaigns are planning/export only — no spend APIs.

Playbook canon (first person): https://github.com/mikolaj92/influenzer-playbook — encoded as rules/data in `influenzer/playbook.py`.

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
python -m influenzer.cli --config /tmp/influenzer/config.json brief ingest \
  --project-id app-1 --brief-id b-patch --story-kind patch \
  --fact "typo in README"
python -m influenzer.cli --config /tmp/influenzer/config.json brief ingest \
  --project-id app-1 --brief-id b-ship --story-kind major --claim-ship --tryable \
  --artifact-url https://github.com/mikolaj92/influenzer/pull/1 \
  --fact "Local tick scores briefs and emits a draft" --arena hn
python -m influenzer.tick_all --config /tmp/influenzer/config.json
# same one-shot via the local loop CLI:
python -m influenzer.tick --config /tmp/influenzer/config.json --once
python -m influenzer.cli --config /tmp/influenzer/config.json brief show \
  --project-id app-1 --brief-id b-ship
```

`tick-all` scores pending briefs every run (draft or explicit kill/changelog-only). It still does not auto-publish. `influenzer-tick-all --live` is ignored. Only `scheduler.live_enabled=true` in config can authorize live mutation, and only with a current grant.

## Always-on tick (Mac mini)

The 24/7 operator stays up on an **always-on host** (a Mac mini or similar), not a laptop LaunchAgent. There is no plist in this repo. This repo does not SSH or deploy; a human starts the process on the box that already has `state.db`.

```bash
# on the mini — interval loop against local SQLite state.db
# (fails closed if this machine is a battery laptop)
uv run influenzer-tick --interval 300
# same keep-up:
contrib/always-on-tick.sh
# or: influenzer tick-loop --interval 300

# one shot (same mutator as influenzer-tick-all; allowed on any machine)
uv run influenzer-tick --once
```

Fala (`mikolaj92/Fala`) may conduct the same one-shot as a **subprocess** organ (`python3 -m influenzer.tick_all` in [`fala-package.toml`](fala-package.toml)). Domain state stays in `state.db`. Do **not** install a LaunchAgent on a laptop.

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

## Stack

- **SQLite** `state.db` is the host-owned domain (projects, briefs, drafts). `runtime.db` is reserved for the Fala journal; effectors do not open it.
- **Fala** (`mikolaj92/Fala`) is the correlator. This repo ships [`fala-package.toml`](fala-package.toml) for the `operator_tick` path (subprocess `influenzer-tick-all`). The engine stays Mojo; Influenzer does not embed a second host.
- **uv** is the Python env/tooling. Mojo is not used here — the HoM copy is fail-closed rules/data in Python.
- Local only. No hosted service, no Ads spend, no live social in this path. 24/7 tick is an always-on host process, not a laptop LaunchAgent.

## Commands

| Command | Purpose |
| --- | --- |
| `influenzer init` | Create workspace home, config, state.db |
| `influenzer project create/show` | App or builder projects with BrandProfile |
| `influenzer content add` | Immutable project-scoped content revision |
| `influenzer brief ingest/show` | HoM brief in; tick scores to draft or kill |
| `influenzer campaign create` | Organic/paid plan (no spend) |
| `influenzer-tick-all` | Score pending briefs; due-plan mutator (dry-run default) |
| `influenzer-tick` / `influenzer tick-loop` | Always-on interval loop on a Mac mini (not a laptop LaunchAgent) |

## Platforms (v1 dry-run/contract)

Separate handlers: X, Bluesky, Mastodon, LinkedIn, Instagram, Facebook Pages.

Each dry-run create returns planned envelope fields for capabilities, official API selection note, media limits, rate/idempotency metadata, access/host requirements, and read-only readback/reconcile shape. Live canaries are ordered: Bluesky+Mastodon → X → LinkedIn → Meta.

## Skills

- `influenzer-profile`
- `influenzer-content`
- `influenzer-campaign`
- `influenzer-publish`
- `influenzer-hom` — HoM operator: brief → score → one arena draft or kill. Canon: https://github.com/mikolaj92/influenzer-playbook
- `influenzer-x` / `influenzer-linkedin` / `influenzer-youtube` / `influenzer-shorts`
- `influenzer-github` / `influenzer-hn` / `influenzer-reddit`
- `influenzer-newsletter` / `influenzer-discord` / `influenzer-bluesky`

## Tests

```bash
uv run python -m unittest discover -s tests
uv run python tools/hygiene_check.py .
```

`python3 -m unittest discover -s tests` also works.

## Safety

- No Ads spend path.
- No plaintext secrets in config/DB/logs/receipts.
- No blind retry after ambiguous create — use `unknown` + reconcile.
- Cross-project references are denied.
- SSRF guard: HTTPS-only, host binding, private IP denial, redirect revalidation, size/type bounds.
