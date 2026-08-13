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
python -m influenzer.cli --config /tmp/influenzer/config.json angle
```

`brief scan --project-id ID --repo owner/name` reads public GitHub signals through a `gh` subprocess (merged PRs, releases, tags) and stores **at most one** pending brief (`source=github-scan`), or stays silent. Commit-noise, waitlists, missing `gh`/auth, an empty survey, or an already-pending story are silence — not a crash. Scan does not publish, does not enable live social, and does not score; `tick-all` still scores pending briefs.

`brief scan-due` (or `brief scan --if-due`) is the same compose **only when due**: a pending brief or unprocessed social draft is silence; a successful look (or github-scan brief) newer than 7 days (overridable) is `not due` and does not call `gh`. `influenzer pass --project-id ID --repo owner/name` is **one CMO look**: that scan-due, then score pending briefs, then at most one wearable angle. Verdict stays the gate. The always-on host can invoke that coarse path on a weekly-ish clock. Tick still does not survey GitHub.

`tick-all` scores pending briefs every run (draft or explicit kill/changelog-only). It still does not auto-publish. `influenzer-tick-all --live` is ignored. Only `scheduler.live_enabled=true` in config can authorize live mutation, and only with a current grant.

## Always-on tick (Mac mini)

The 24/7 operator stays up on an **always-on host** (a Mac mini or similar), not a laptop LaunchAgent. There is no plist in this repo. This repo does not SSH or deploy; a human starts the process on the box that already has `state.db`. On **mini-m4-0**, hop on and start the existing dry-run tick: [`docs/mini-m4-0.md`](docs/mini-m4-0.md).

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

Fala (`mikolaj92/Fala`) may conduct the same one-shot as a **subprocess** organ (`python3 -m influenzer.tick_all` in [`fala-package.toml`](fala-package.toml)), the GitHub scan as `github_survey` → `github_pack` → `influenzer.brief_admit`, the coarse look as `python3 -m influenzer.scan_due` (not on the 5-minute tick), and one CMO cycle as `python3 -m influenzer.hom_pass`. `influenzer brief scan` is always-run host compose; `influenzer brief scan-due` is the weekly-ish look; `influenzer pass` is scan-due → tick → one angle. Domain state stays in `state.db`. Do **not** install a LaunchAgent on a laptop.

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
- **Fala** (`mikolaj92/Fala`) is the correlator. This repo ships [`fala-package.toml`](fala-package.toml) for `operator_tick` (`influenzer-tick-all`), `github_scan` (`github_survey` → `github_pack` → `influenzer.brief_admit`), coarse `github_scan_due` (`influenzer.scan_due`), draft-only `hom_draft`, read-only `hom_outbox`, gate `hom_verdict`, and one-shot `hom_pass`. Survey and pack are separate blocks; the host admits into `state.db`. Tick scores then asks `hom_draft` for wearable copy. `influenzer angle` leaves at most one draft. `influenzer pass` composes scan-due → tick → angle once. Effectors never open `runtime.db`. The engine stays Mojo; Influenzer does not embed a second host.
- **github_survey** — public GitHub → JSON. Does not know briefs, drafts, `state.db`, scoring, publishing, or arenas. See [`github_survey/README.md`](github_survey/README.md).
- **github_pack** — survey JSON → facts + ship/tryable, or silence. Does not call `gh`, write SQLite, or tick. See [`github_pack/README.md`](github_pack/README.md).
- **hom_draft** — scored brief → costume-native one-arena `body`, or silence. Does not score, pick the arena, survey GitHub, write `state.db`, or publish. Host compose is `apply_brief` / tick. Fala may run `python3 -m influenzer.hom_draft`.
- **hom_outbox** — `state.db` → at most one wearable draft packet, or silence. Newest wearable by `created_at`, then `draft_id`. Does not score, dress, survey GitHub, call `gh`, publish, enable live, send mail, or write SQLite. Host compose is `influenzer angle`. Fala may run `python3 -m influenzer.hom_outbox`.
- **hom_verdict** — hold or pass the current wearable angle. Hold archives that draft so the one-story lock releases and scan-due may run again. Pass records fit and does not post, enable live, or call adapters. Host compose is `influenzer verdict hold` / `influenzer verdict pass`. Fala may run `python3 -m influenzer.hom_verdict`.
- **hom_pass** — one CMO look: `scan_due` → tick (score pending briefs) → `hom_outbox` (at most one angle). Reuses those functions; does not copy survey/pack/admit/score/dress/outbox. Does not verdict, publish, enable live, call `gh`, know Heimdall, or run every tick interval. Host compose is `influenzer pass --project-id ID --repo owner/name`. Fala may run `python3 -m influenzer.hom_pass`.
- **scan_due** — same as scan (0 or 1 brief) only when the coarse window elapsed, else silence. Reuses `scan_github`; does not call `gh`, score, dress, publish, enable live, or run every tick interval. Host compose is `influenzer brief scan-due`. Fala may run `python3 -m influenzer.scan_due`.
- **uv** is the Python env/tooling. Mojo is not used here — the HoM copy is fail-closed rules/data in Python.
- Local only. No hosted service, no Ads spend, no live social in this path. 24/7 tick is an always-on host process, not a laptop LaunchAgent.

## Commands

| Command | Purpose |
| --- | --- |
| `influenzer init` | Create workspace home, config, state.db |
| `influenzer project create/show` | App or builder projects with BrandProfile |
| `influenzer content add` | Immutable project-scoped content revision |
| `influenzer brief ingest/show/scan` | HoM brief in; GitHub scan writes 0 or 1 pending brief; tick scores to draft or kill |
| `influenzer brief scan-due` | Same as scan only when the coarse window elapsed; else silence. Does not score. |
| `influenzer pass` | One CMO look: scan-due, score pending briefs, at most one angle. Does not publish. Verdict stays the gate. |
| `influenzer angle` | One wearable draft from `state.db`, or silence. Does not publish. |
| `influenzer verdict` | Hold or pass the current angle. Hold releases the one-story lock. Pass does not post. |
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
