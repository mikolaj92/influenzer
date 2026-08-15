# Influenzer

Local multi-project social operator for organic posting and campaign planning.

Influenzer runs on your machine as a **local 24/7 Head of Marketing operator**. Every app has its own Project + BrandProfile. The builder is also a first-class Project (`kind=builder`) with a separate profile and accounts.

On each `influenzer-tick-all` (or an always-on `influenzer-tick` loop on a Mac mini), pending **briefs** (many facts) are scored: **kill**, **changelog-only**, or **one-angle draft** in **one primary arena**. Scoring is fail-closed: borderline briefs do not leak a social draft. Not every commit/event becomes a post. Drafts are local; they are not auto-published. Dry-run is default; live organic publish needs durable live intent plus a hash-bound policy grant. Paid campaigns are planning/export only — no spend APIs.

Playbook canon (first person): https://github.com/mikolaj92/influenzer-playbook — encoded as rules/data in `influenzer/playbook.py`.

## Install

Requires [uv](https://docs.astral.sh/uv/). From a checkout of this repo:

```bash
git clone https://github.com/mikolaj92/influenzer
cd influenzer
uv sync
```

Then run `uv run influenzer …` (see the 3-minute demo below).

To put the CLI on PATH without keeping a checkout:

```bash
uv tool install git+https://github.com/mikolaj92/influenzer
```

One-shot from git (same package):

```bash
uvx --from git+https://github.com/mikolaj92/influenzer influenzer --help
```

Influenzer is a local CLI, not a hosted service. Runtime state, scheduling, policies, and credentials remain on the user's machine.

After install, see [`after-install.md`](after-install.md).

## 3-minute local demo

```bash
uv run influenzer --config /tmp/influenzer/config.json init --home /tmp/influenzer
uv run influenzer --config /tmp/influenzer/config.json project create \
  --id app-1 --slug my-app --name "My App" --display-name "My App" \
  --voice product --audience customers --maintainer you --kind app
uv run influenzer --config /tmp/influenzer/config.json project create \
  --id builder-1 --slug me --name Me --display-name Me \
  --voice builder --audience builders --maintainer you --kind builder
uv run influenzer --config /tmp/influenzer/config.json content add \
  --project-id app-1 --content-id c1 --revision-id r1 \
  --body "Shipped dry-run adapters" --status ready
uv run influenzer --config /tmp/influenzer/config.json brief ingest \
  --project-id app-1 --brief-id b-patch --story-kind patch \
  --fact "typo in README"
uv run influenzer --config /tmp/influenzer/config.json brief ingest \
  --project-id app-1 --brief-id b-ship --story-kind major --claim-ship --tryable \
  --artifact-url https://github.com/mikolaj92/influenzer \
  --fact "Local tick scores briefs and emits a draft" --arena hn
uv run influenzer-tick-all --config /tmp/influenzer/config.json
# same one-shot via the local loop CLI:
uv run influenzer-tick --config /tmp/influenzer/config.json --once
uv run influenzer --config /tmp/influenzer/config.json brief show \
  --project-id app-1 --brief-id b-ship
uv run influenzer --config /tmp/influenzer/config.json angle
```

`brief scan --project-id ID --repo owner/name` reads public GitHub signals through a `gh` subprocess (merged PRs, releases, tags) and stores **at most one** pending brief (`source=github-scan`), or stays silent. Commit-noise, waitlists, missing `gh`/auth, an empty survey, an empty repo or a repo without a README, or an already-pending story are silence — not a crash. README/comments/JSON over the hard byte limit is an empty look, not a feast. 50MB in `state.db` is silence. The loop lives. Scan does not publish, does not enable live social, and does not score; `tick-all` still scores pending briefs. Look does not run the project. Launching on watch is silence. Tryable is a README+URL heuristic. Code in look is untrusted.

`influenzer feedback --project-id ID --repo owner/name` (or the declared watch) reads public issue/PR comments through the same `gh` subprocess and stores **at most one** pending brief (`source=github-feedback`), or stays silent. Bots, LGTM, and empty thanks fail closed. A real question, bug, or pushback becomes facts. Oversized README/comments/JSON is an empty look; nothing near 50MB is stored. Feedback does not publish, does not auto-post replies, and does not choose a social angle; `tick-all` still scores pending briefs.

`brief scan-due` (or `brief scan --if-due`) is the same compose **only when due**: a pending brief or unprocessed social draft is silence; a successful look (or github-scan brief) newer than 7 days (overridable) is `not due` and does not call `gh`. `influenzer pass --project-id ID --repo owner/name` is **one CMO look**: that scan-due, then score pending briefs, then at most one wearable angle. Verdict stays the gate. Declare the look with `influenzer watch set --project-id ID --repo owner/name`. The interval loop still scores every time; when that watch exists and scan-due would consider it due, it runs `hom_pass` once. `--once` stays score-only unless `--pass-if-due`.

`tick-all` scores pending briefs every run (draft or explicit kill/changelog-only). It still does not auto-publish. `influenzer-tick-all --live` is ignored. Only `scheduler.live_enabled=true` in config can authorize live mutation, and only with a current grant.

## Always-on tick (Mac mini)

The 24/7 operator stays up on an **always-on host** (a Mac mini or similar), not a laptop LaunchAgent. There is no plist in this repo. This repo does not SSH or deploy; a human starts the process on the box that already has `state.db`. On **mini-m4-0**, hop on and start the existing dry-run tick: [`docs/mini-m4-0.md`](docs/mini-m4-0.md).

```bash
# on the mini — declare the one watch, then keep the interval loop up
uv run influenzer --config ~/.hermes/influenzer/config.json watch set \
  --project-id app-1 --repo owner/name
# interval loop against local SQLite state.db
# (fails closed if this machine is a battery laptop)
uv run influenzer-tick --interval 300
# same keep-up:
contrib/always-on-tick.sh
# or: influenzer tick-loop --interval 300

# one shot (score-only like influenzer-tick-all; does not scan; allowed on any machine)
uv run influenzer-tick --once
# one shot that may hom_pass if the declared watch is due:
uv run influenzer-tick --once --pass-if-due
```

Fala (`mikolaj92/Fala`) may conduct the score-only one-shot as a **subprocess** organ (`python3 -m influenzer.tick_all` in [`fala-package.toml`](fala-package.toml)), the GitHub scan as `github_survey` → `github_pack` → `influenzer.brief_admit`, inbound replies as `github_feedback` → `influenzer.hom_feedback`, the coarse look as `python3 -m influenzer.scan_due` (not on the 5-minute Fala tick), and one CMO cycle as `python3 -m influenzer.hom_pass`. Watch set is host CLI only — no Fala organ. `influenzer brief scan` is always-run host compose; `influenzer brief scan-due` is the weekly-ish look; `influenzer pass` is scan-due → tick → one angle; `influenzer feedback` is replies → 0 or 1 brief. Domain state stays in `state.db`. Do **not** install a LaunchAgent on a laptop.

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
- **Fala** (`mikolaj92/Fala`) is the correlator. This repo ships [`fala-package.toml`](fala-package.toml) for `operator_tick` (`influenzer-tick-all`), `github_scan` (`github_survey` → `github_pack` → `influenzer.brief_admit`), inbound `github_feedback` (`github_feedback` → `influenzer.hom_feedback`), coarse `github_scan_due` (`influenzer.scan_due`), draft-only `hom_draft`, read-only `hom_outbox`, gate `hom_verdict`, and one-shot `hom_pass`. Survey and pack are separate blocks; the host admits into `state.db`. Tick scores then asks `hom_draft` for wearable copy. `influenzer angle` leaves at most one draft. `influenzer pass` composes scan-due → tick → angle once. Effectors never open `runtime.db`. The engine stays Mojo; Influenzer does not embed a second host.
- **github_survey** — public GitHub → JSON. Does not know briefs, drafts, `state.db`, scoring, publishing, or arenas. See [`github_survey/README.md`](github_survey/README.md).
- **github_pack** — survey JSON → facts + ship/tryable, or silence. Tryable is a README+URL heuristic, not a live run. Does not call `gh`, write SQLite, or tick. See [`github_pack/README.md`](github_pack/README.md).
- **github_feedback** — public issue/PR comments → facts, or silence. Bots, LGTM, and empty thanks fail closed. Does not write SQLite, post replies, survey releases/PRs, or load Influenzer. See [`github_feedback/README.md`](github_feedback/README.md).
- **hom_feedback** — host compose: collect replies and admit at most one pending brief (`source=github-feedback`), or silence when a story is already open. Does not score, dress, publish, enable live, or auto-post. Host compose is `influenzer feedback`. Fala may run `python3 -m github_feedback` then `python3 -m influenzer.hom_feedback`.
- **hom_draft** — scored brief → costume-native one-arena `body`, or silence. Does not score, pick the arena, survey GitHub, write `state.db`, or publish. Host compose is `apply_brief` / tick. Fala may run `python3 -m influenzer.hom_draft`.
- **hom_outbox** — `state.db` → at most one wearable draft packet, or silence. Newest wearable by `created_at`, then `draft_id`. Does not score, dress, survey GitHub, call `gh`, publish, enable live, send mail, or write SQLite. Host compose is `influenzer angle`. Fala may run `python3 -m influenzer.hom_outbox`.
- **hom_verdict** — hold or pass the current wearable angle. Hold archives that draft so the one-story lock releases and scan-due may run again. Pass records fit and does not post, enable live, or call adapters. Host compose is `influenzer verdict hold` / `influenzer verdict pass`. Fala may run `python3 -m influenzer.hom_verdict`.
- **hom_pass** — one CMO look: `scan_due` → tick (score pending briefs) → `hom_outbox` (at most one angle). Reuses those functions; does not copy survey/pack/admit/score/dress/outbox. Does not verdict, publish, enable live, call `gh`, know Heimdall, or run every tick interval. Host compose is `influenzer pass --project-id ID --repo owner/name`. The interval loop may invoke this once when a declared watch is due. Fala may run `python3 -m influenzer.hom_pass`.
- **hom_watch** — declare one project → one repo (`influenzer watch set` / `watch show`). Persisted in `state.db`. The interval tick reuses `scan_due_reason` and runs existing `hom_pass` when due; otherwise it only scores. Look does not run the project. Launching on watch is silence. `--once` does not scan unless `--pass-if-due`. No Fala organ.
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
| `influenzer feedback` | Public GitHub replies → 0 or 1 pending brief (`source=github-feedback`). Never publishes. |
| `influenzer pass` | One CMO look: scan-due, score pending briefs, at most one angle. Does not publish. Verdict stays the gate. |
| `influenzer watch set/show` | Declare the one project+repo the interval tick may look at. Explicit CLI only. |
| `influenzer angle` | One wearable draft from `state.db`, or silence. Does not publish. |
| `influenzer verdict` | Hold or pass the current angle. Hold releases the one-story lock. Pass does not post. |
| `influenzer campaign create` | Organic/paid plan (no spend) |
| `influenzer-tick-all` | Score pending briefs; due-plan mutator (dry-run default) |
| `influenzer-tick` / `influenzer tick-loop` | Always-on interval loop on a Mac mini. Scores every time; may `hom_pass` when a declared watch is due. `--once` is score-only unless `--pass-if-due`. |

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
