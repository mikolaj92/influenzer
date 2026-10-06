# Influenzer

Local multi-project social operator for organic posting and campaign planning.

Influenzer runs on your machine as a **local 24/7 Head of Marketing operator**. Every app has its own Project + BrandProfile. The builder is also a first-class Project (`kind=builder`) with a separate profile and accounts.

On each `influenzer-tick-all` (or an always-on `influenzer-tick` loop on a Mac mini), pending **briefs** (many facts) are scored: **kill**, **changelog-only**, or **one-angle draft** in **one primary arena**. Scoring is fail-closed: borderline briefs do not leak a social draft. Not every commit/event becomes a post. Drafts are local; they are not auto-published. The shipped v1 platform adapters are dry-run-only: durable live intent plus a hash-bound policy grant can pass the scheduler gate, but cannot enable platform publication. Paid campaigns are planning/export only — no spend APIs.

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
  --fact "Local tick scores briefs and emits a draft" \
  --fact "Dry-run still default" --arena hn
uv run influenzer-tick-all --config /tmp/influenzer/config.json
# same one-shot via the local loop CLI:
uv run influenzer-tick --config /tmp/influenzer/config.json --once
uv run influenzer --config /tmp/influenzer/config.json brief show \
  --project-id app-1 --brief-id b-ship
uv run influenzer --config /tmp/influenzer/config.json angle
```

`brief scan --project-id ID --repo owner/name` reads public GitHub signals through a `gh` subprocess (merged PRs, releases, tags) and stores **at most one** pending brief (`source=github-scan`), or stays silent. Commit-noise, waitlists, missing `gh`/auth, an empty survey, an empty repo or a repo without a README, a private repo (even when the owner is ours), or an already-pending story are silence — not a crash. Watch on private is fail-closed, not a 404 loop. Workshop is a public README. README/comments/JSON over the hard byte limit is an empty look, not a feast. 50MB in `state.db` is silence. The loop lives. Scan does not publish, does not enable live social, and does not score; `tick-all` still scores pending briefs. Look does not run the project. Launching on watch is silence. Tryable is a README+URL heuristic. Code in look is untrusted.

`influenzer feedback --project-id ID --repo owner/name` (or the declared watch) reads public issue/PR comments through the same `gh` subprocess and stores **at most one** pending brief (`source=github-feedback`), or stays silent. Bots, LGTM, and empty thanks fail closed. A real question, bug, or pushback becomes facts. Oversized README/comments/JSON is an empty look; nothing near 50MB is stored. Feedback does not publish, does not auto-post replies, and does not choose a social angle; `tick-all` still scores pending briefs.

`brief scan-due` (or `brief scan --if-due`) is the same compose **only when due**: a pending brief or unprocessed social draft is silence; a new GitHub look starts only on Monday (Europe/Warsaw) if no look has completed for that Monday. An interrupted look can resume on a later day, even after Monday. Otherwise it is `not due` and does not call `gh`; the legacy `--window-days` flag is accepted but ignored. `influenzer pass --project-id ID --repo owner/name` is **one CMO look**: listen (0 or 1 github-feedback brief), that scan-due, then score pending briefs, then at most one wearable angle. Verdict stays the gate. Declare the look with `influenzer watch set --project-id ID --repo owner/name`. The interval loop still scores every time; when that watch exists and scan-due would consider it due, it runs `hom_pass` once. `--once` stays score-only unless `--pass-if-due`.

`tick-all` scores pending briefs every run (draft or explicit kill/changelog-only). It selects no due plans from `state.db` and does not dispatch or publish plans, even with `scheduler.live_enabled=true`. `influenzer-tick-all --live` is ignored. The scheduler's Python API can dispatch explicitly supplied `DueWork` items with durable live intent and a current grant; the CLI always supplies `due=()`. Shipped adapters reject that `dry_run=False` dispatch without platform mutation, and the scheduler records failed plans/attempts. `scheduler.live_enabled=true` does not unlock live organic publication.

## External observations (read-only)

Read many configured sources through datasource-kit's `run_ingest`. RSS/Atom
uses feedparser; Hacker News uses its public Firebase API. One provider can
serve multiple source IDs. These reads do not create briefs or publish posts.

```bash
uv run influenzer source read --profile docs/sources/rss.json
uv run influenzer source read --profile docs/sources/hn.json
uv run influenzer source history --id hn-top
uv run influenzer source reports --id hn-top
```

Profiles specify `source_id`, `provider`, `target`, and optional `limit` (1–500).
HN targets: `topstories`, `newstories`, `beststories`. RSS targets: HTTP(S) URLs.

X reads use the hosted [x-md](https://github.com/pc-style/x-md) versioned JSON API,
not a local scraper, and require no X credentials:

```bash
uv run influenzer source read --profile docs/sources/x-paulg.json
uv run influenzer source read --profile docs/sources/x-local-ai.json
```

`x_profile` targets a public handle without `@`; `x_search` targets a public
search query (`feed=latest`). Limit: at most 100. Each read fetches **one page**
and reports `next_cursor`, `upstream_source` and `upstream_cache`; it does not
walk pagination or claim full search coverage. Cached observations are not
necessarily fresh upstream measurements. Responses with warnings or Firecrawl
web-index fallback are recorded as failed bounded reads, not genuine empty
feeds. HTTP failures (including 429/503) are reported without automatic retries.
Hosted search has shared quotas (documented as 10 live requests/IP/15 minutes),
so avoid frequent polling. Only public handles/queries: the hosted service sees
them. x-md is read-only and does not implement our optional Publisher.
History lives in `observations.db` beside `state.db`, with content-addressed raw
responses in `source-artifacts/`. Each run appends snapshots, including changed
metrics, rather than overwriting earlier observations. Missing metrics are
unknown, not zero. Reports and snapshots are committed together.

Reports describe a **bounded feed**, not complete platform coverage: available
feed entries, truncation, warnings, run ID and observation time. Empty feeds
and failed reads are distinct. A failed read returns exit code 1 and preserves
previous history; one read attempt by default. HN item failure makes that bounded
read fail rather than persisting a misleading partial sample. Feed polling
re-observes current items intentionally; it is not a historical backfill or
checkpointed stream. The kit owns ingest mechanics; source identity, records
and interpretation stay in Influenzer. Trend inference and automatic scheduling
of these reads are not implemented yet.

## Local AI radar

Enable the bounded evidence digest in the existing workspace:

```bash
cp docs/sources/radar-local-ai.json ~/.hermes/influenzer/radar.json
uv run influenzer radar
# Existing tick also collects due radar sources:
uv run influenzer-tick --interval 300
```

`radar.json` owns source configuration, a minimum 900-second read interval
(default six hours), and an explicit project target. `project.id` here is a
report target, not automatic creation of a domain Project. `topics` describes
the source interests; it does not filter records or decide actions by keyword
overlap. The old `need_terms` keyword gate is not part of the review profile.
The last successful or failed attempt prevents immediate repeat requests.
`radar-latest.json` stores coverage, deduplicated evidence and raw references.
Failed/stale latest reads are excluded. **The radar neither classifies needs
nor proposes an action:** `decision=null`, `decision_status=not_evaluated`.

Interpretation and decisions belong exclusively to `review`. The legacy lexical
heuristic exists only in `review evaluate` as a comparison baseline; it is never
a model fallback. No independent-author verification or trend claim. The digest
does not create briefs, drafts or publications. No second scheduler, no automatic
retries. CLI calls must not overlap a running tick's radar read.

## LLM interpretation → GB10 decision (manual, no execution)

Add a `models` object to workspace `radar.json` (shape:
[`docs/sources/review-models.json`](docs/sources/review-models.json)).
`base_url`/`interpretation_model` configure the generative LLM through an
OpenAI-compatible provider. **`decision` configures GB10 separately:** explicit
`https://decisions.example.com/v1/decisions` placeholder URL (replace for your deployment), returned model identity
`GLM-5.3-Flash-EXL3`, timeout and `min_confidence` (default 0.5).
The old Plumb `/v1/systemone` and `decision_model` chat-completion configurations
are rejected. There is no Plumb, generative or heuristic decision fallback.

The request uses `model`, JSON-string `input`, one `questions` entry with
`id/type/question/options`, `prompt_format_version=1` and
`chat_template_kwargs={"enable_thinking":false}`. The response must identify
`object=decisions`, the requested model, protocol version and question. Runtime
transport is one fixed `/usr/bin/curl` call (no retries, redirects or proxy),
with a 1MB response bound. httpx is injectable only for protocol tests,
not a runtime transport fallback.

A key is read only from `api_key_env`; never stored. `json_mode=false` is an
explicit interpretation-provider compatibility setting. Plain JSON or a single
explicit JSON fence is accepted; both are strictly validated.

```bash
uv run influenzer radar
uv run influenzer review run --project-id EXISTING_PROJECT_ID
# Explicit separate app scope, using the same collected evidence:
uv run influenzer review run --project-id EXISTING_APP_ID --profile app-profile.json
uv run influenzer review list --project-id EXISTING_PROJECT_ID
uv run influenzer review verdict --project-id EXISTING_PROJECT_ID \
  --id PROPOSAL_ID --value useful --reason "Worth checking" --actor YOUR_NAME
```

### TencentDB application records — separate from personal memory

The existing deployment is **TencentDB Agent Memory v2**, not a newly provisioned
SQL database. `influenzer/tencent_records.py` uses its actual
`/v3/conversation/add` and `/v3/conversation/query` L0 APIs for exact JSON records:
content-addressed sessions, bounded chunks, SHA-256 verification and readback.
It does not use semantic search as an exact read, `/capture`, atomic-note
extraction, or the knowledge API (which registers external services).

Configure `radar.json.records` using
[`docs/sources/tencent-records.example.json`](docs/sources/tencent-records.example.json).
The **separately provisioned private app agent** owns these records; the
credential's authenticated owner ID must still match the user key. Sources are
untrusted application data, not claims about that owner. Assistant-only L0
messages do not trigger user-round extraction in the inspected v2 handler.
They may still be indexed by the backend: agent scope, not message role or
base64 encoding, is the isolation boundary. Keep credentials in the existing
`TDAI_MEMORY_USER_KEY`/`TDAI_MEMORY_API_KEY` environment, never JSON or Git.
The namespace must be provisioned explicitly; a missing scope (404) is an error,
not permission to silently create or write into personal memory.

**Boundary:** TencentDB retains full review/research/approval/verdict packages.
The existing local journal still provides transactional execution claims and
old history; immutable source artifacts remain in its SHA-256 store.
This is **not** a migration of all `state.db`/`observations.db`, nor a distributed
claim service. The L0 API assigns message IDs and lacks caller-keyed CAS;
read-before-write suppresses identical sequential writes but is not distributed
idempotency. No automatic HTTP retries or redirects. A storage failure retains
the local result, reports `record.status=unconfirmed`, and makes CLI exit 1;
it does not turn a successful model result into a skip or call models again.

### Explicitly approved research → cited result → separate verdict

`useful` is not execution permission. `research authorize` requires a specific
successful **case** whose action is `research`, a concrete question, retained
source records, actor and reason. Sources have `evidence_id/content/url/raw_ref`;
`raw_ref` is a SHA-256 artifact registered in the existing workspace. Code
verifies source content against the immutable artifact at authorization and
again before execution. It never fetches model-selected URLs or executes
instructions found in a source.

```bash
uv run influenzer research authorize --project-id EXISTING_PROJECT_ID \
  --proposal-id CASE_PROPOSAL_ID --question "What exactly needs checking?" \
  --sources retained-sources.json --actor YOUR_NAME --reason "Explicit research permission"
uv run influenzer research run --project-id EXISTING_PROJECT_ID --id AUTHORIZATION_ID
uv run influenzer research list --project-id EXISTING_PROJECT_ID
uv run influenzer research verdict --project-id EXISTING_PROJECT_ID \
  --id RESULT_ID --value useful --actor YOUR_NAME --reason "Why this answers the question"
# Agent assessment is labelled, not attributed to the owner:
# ... --actor Alfred --provisional
```

Research is **one LLM call → one JSON**, not an autonomous browsing/agent loop.
Each finding selects source fragment IDs; code reconstructs exact citations,
URLs and raw references. Empty findings require a named uncertainty and return
`insufficient_evidence`, not empty success. Invalid references/model errors fail
closed. Atomic claims preserve completed, failed and interrupted snapshots;
identical replay makes zero additional model calls. Configuration changes create
a new snapshot, not a silent retry. Source correctness, claim entailment and
semantic usefulness still need operator assessment. Result verdicts have their
own IDs and optional `provisional=true`; they never authorize publishing.

The collecting tick invokes **neither research nor models**. No research path
creates briefs, drafts, schedules, publication plans or posts. Live operator
measurements are intentionally not included in this public repository.

### Explicit project scope

Review requires a profile bound to an existing Project's **ID and kind**:
`id`, `kind`, `audience`, `problem`, `capabilities`, `not_offered`, optional
`topics`. Missing scope is rejected before model calls; an empty capabilities
list explicitly means no documented solution capability, not a guess that the
project can solve it. Builder and app are separate Projects/profiles. The builder
example covers local inference, hardware, performance, privacy and workflows;
it does not pretend to be an offline-PDF app. The app example is
[`docs/sources/project-documents.example.json`](docs/sources/project-documents.example.json);
it is not a registered or deployed application.

A capability entry is `{"claim":"...","artifact_digest":"SHA256","quote":"..."}`.
The immutable artifact must exist in the workspace's existing artifact store,
have correct SHA-256 bytes and contain the exact quote. This is provenance,
**not proof the claim is true or applicable to a need**. No automatic scraping,
capability inference or second registry. `material/reply/product` without any
documented capability is a named contract failure, never rewritten to research;
`product` also requires an app Project.

### One need case = one decision

The LLM classifies all selected records: question/problem/request,
advertisement, success, joke or other. Its single JSON has `items` and `cases`.
Each case describes **one concrete need** and its `evidence_ids`. Only statements
about the same problem may merge, not just similar keywords. The host validates
that cases partition all need items exactly once, with no non-need, duplicate or
unknown references. No needs means `no_needs`, zero cases and **zero GB10 calls**;
this is not a model's intentional skip.

Code owns lossless source spans (up to 800 characters, without semantic filtering).
The interpreter selects a short `fragment_id`, **never rewrites quote text**.
Each span also carries its full SHA-256, content hash, source ID and offsets;
short-ID collisions fail closed. IDs are stable for unchanged source content,
independent of feed order. Unknown/foreign IDs, duplicate items and retyped quote
fields are rejected. Code restores the exact source bytes, preserving `You`
and `&amp;` without whitespace/fuzzy repair. This validates provenance,
**not semantic classification or grouping correctness**.

GB10 receives one case, only its interpretations/source records, the bound
project scope and coverage. One `choice` question per case selects
`skip/research/product/material/reply`; it generates **zero text tokens**.
`evidence_scope=validated_case_not_model_selected` means the host binds exact
case citations, not that GB10 generated them. `reason_source=protocol_receipt`
identifies host receipt text, not a model-generated explanation. No third LLM
call for an invented rationale. A review has `decision=null` and `cases` with
individual decisions, statuses, snapshots and proposal IDs; no batch-wide action.

The host validates exact model/question identity, option vocabulary, finite
probabilities, total mass, argmax, `label_mass` and `usage.completion_tokens=0`.
Confidence is derived from the selected probability; `label_mass` is retained
as full-vocabulary label probability, not used as a calibrated acceptance gate.
Below `min_confidence`, or on a tied argmax, the case is `abstained` with
`decision=null` (`decision_uncertain`). These scores are not independently
calibrated probabilities of correctness. Transport/contract errors are `failed`
with `decision=null`, named stage/cause and no fallback. One failed case does
not erase another completed decision. Review counters are
`cases/proposed/failed/abstained/incomplete`. Any failed/incomplete case makes the
review `partial` (CLI exit 1); otherwise any abstention means exit 2, successful
proposals or no needs exit 0. Abstention/failure is **not skip**.

Atomic claims and the operational history remain in `state.db`'s existing domain
journal; no schema migration. When `radar.json.records` is configured, full review
snapshots (including case proposals/evidence/audits) are also retained and exactly
read-verified in the existing TencentDB service. See the persistence boundary below. Input snapshots, prompt version/text,
requested and returned model IDs, GB10's complete request/response,
probabilities, outputs, tokens and latency are retained. `review run` updates
`review-latest.json` on success, failure or abstention, not just success.
`review list` returns individual case proposals (plus legacy proposals, with
original snapshots), not the review wrapper. `review verdict --id` addresses
one case's proposal ID; it cannot approve the whole batch. `useful` assesses a
recommendation, not permission to execute. `executed` is an operator report
about external work, not a command. No briefs/drafts/publications are created.

A review makes **one LLM batch + one GB10 question per concrete case**
(at most 30 posts/30 cases and 100KB source evidence). HTTP retries are disabled.
Atomic claims protect the review and each case; identical failed, interrupted,
abstained or completed snapshots do not call models again. Failures need explicit
investigation before changing inputs/configuration. A changed snapshot is a new
review. Case IDs are content-derived from project/need/evidence, not a semantic
cross-read deduplication system: stable need tracking and re-evaluation policy
remain separate future work. No embedding or fuzzy grouping fallback. Newest published records
are selected when the sample exceeds 30 (observation time for undated records);
selection/truncation counts are retained. No keyword or punctuation filtering.
This bounded sample is not representative. The collecting tick does **not**
automatically call models. The interpretation provider receives public posts;
the configured GB10 decision endpoint receives interpretations and project profile/scope.
Historical proposals made by older protocols remain in the journal with their
original snapshots; historical Plumb decisions are not re-labelled as GB10 results.

Compare a saved proposal with reviewer-labelled cases without model requests:

```bash
uv run influenzer review evaluate \
  --proposal ~/.hermes/influenzer/review-evaluation-proposal.json \
  --labels /path/to/your-review-labels.json
```

Supply your own reviewer-labelled cases; private operator labels and live
measurements are excluded from publication. Counts are TP/FP/FN/TN for concrete
needs; monetary cost stays unknown unless pricing is available. Need detection
is not project relevance or decision usefulness, and protocol tests do not
validate semantic quality. The existing legacy brief/draft path remains separate;
this change does not replace its downstream angle/form decisions or add an
approval-to-execution bridge.

**Failure privacy:** review interpretation, per-case decision and research
failures retain only the exception type in `failure_class`/`failure_message`,
never the exception text, which may contain private endpoints, credentials or
provider response details. This applies to returned results, local journal
records and TencentDB retention. Input snapshots and deliberate model/protocol
audits remain retained application data; this is not general payload redaction.
Existing historical records are not rewritten by this change.

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

Fala (`mikolaj92/Fala`) may conduct the score-only one-shot as a **subprocess** organ (`uv run influenzer-tick-all` in [`fala-package.toml`](fala-package.toml)), the GitHub scan as `github_survey` → `github_pack` → `influenzer.brief_admit`, inbound replies as `github_feedback` → `influenzer.hom_feedback`, the Monday-started, resumable look as `uv run python -m influenzer.scan_due` (not on the 5-minute Fala tick), and one CMO cycle as `uv run python -m influenzer.hom_pass`. Watch set is host CLI only — no Fala organ. `influenzer brief scan` is always-run host compose; `influenzer brief scan-due` starts a new look on Monday (Europe/Warsaw), if none has completed that Monday; an interrupted look can resume on a later day; `influenzer pass` is listen → scan-due → tick → one angle; `influenzer feedback` is replies → 0 or 1 brief. Domain state stays in `state.db`. Do **not** install a LaunchAgent on a laptop.

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

Secrets never go in config. Register an existing platform account with `influenzer account add --credential-ref`; platform accounts store `credential_ref` only (`env:NAME` or `keychain:SERVICE/ACCOUNT`). For example, after creating `app-1`:

```bash
uv run influenzer account add --project-id app-1 --account-id x-1 \
  --platform x --handle @myapp --credential-ref env:X_TOKEN
uv run influenzer account list --project-id app-1
uv run influenzer policy create --project-id app-1 --policy-version-id pol-1 \
  --account-id x-1
uv run influenzer grant activate --project-id app-1 --grant-id g-1 \
  --policy-version-id pol-1 --account-id x-1 --actor you
```

Use `--config PATH` before the command when using a non-default workspace. Accounts default to `disconnected`; registering an account does not connect it or verify credentials. Mastodon accounts also require `--host INSTANCE_HOSTNAME`. The policy and grant above record local authorization only; they do not enable live publication through the shipped adapters.

## Stack

- **SQLite** `state.db` is the host-owned domain (projects, briefs, drafts). `runtime.db` is reserved for the Fala journal; effectors do not open it.
- **Fala** (`mikolaj92/Fala`) is the correlator. This repo ships [`fala-package.toml`](fala-package.toml) for score-only `operator_tick` (`influenzer-tick-all`; no plan selection or dispatch), `github_scan` (`github_survey` → `github_pack` → `influenzer.brief_admit`), inbound `github_feedback` (`github_feedback` → `influenzer.hom_feedback`), Monday-started, resumable `github_scan_due` (`influenzer.scan_due`), draft-only `hom_draft`, read-only `hom_outbox`, gate `hom_verdict`, and one-shot `hom_pass`. Survey and pack are separate blocks; the host admits into `state.db`. Tick scores then asks `hom_draft` for wearable copy. `influenzer angle` leaves at most one draft. `influenzer pass` composes listen → scan-due → tick → angle once. Effectors never open `runtime.db`. The engine stays Mojo; Influenzer does not embed a second host.
- **github_survey** — public GitHub → JSON. Does not know briefs, drafts, `state.db`, scoring, publishing, or arenas. See [`github_survey/README.md`](github_survey/README.md).
- **github_pack** — survey JSON → facts + ship/tryable, or silence. Tryable is a README+URL heuristic, not a live run. Does not call `gh`, write SQLite, or tick. See [`github_pack/README.md`](github_pack/README.md).
- **github_feedback** — public issue/PR comments → facts, or silence. Bots, LGTM, and empty thanks fail closed. Does not write SQLite, post replies, survey releases/PRs, or load Influenzer. See [`github_feedback/README.md`](github_feedback/README.md).
- **hom_feedback** — host compose: collect replies and admit at most one pending brief (`source=github-feedback`), or silence when a story is already open. Does not score, dress, publish, enable live, or auto-post. Host compose is `influenzer feedback`. Fala may run `uv run python -m github_feedback` then `uv run python -m influenzer.hom_feedback`.
- **hom_draft** — scored brief → costume-native one-arena `body`, or silence. Does not score, pick the arena, survey GitHub, write `state.db`, or publish. Host compose is `apply_brief` / tick. Fala may run `uv run python -m influenzer.hom_draft`.
- **hom_outbox** — `state.db` → at most one wearable draft packet, or silence. Newest wearable by `created_at`, then `draft_id`. Does not score, dress, survey GitHub, call `gh`, publish, enable live, send mail, or write SQLite. Host compose is `influenzer angle`. Fala may run `uv run python -m influenzer.hom_outbox`.
- **hom_verdict** — hold or pass the current wearable angle. Hold archives that draft so the one-story lock releases and scan-due may run again. Pass records fit and does not post, enable live, or call adapters. Host compose is `influenzer verdict hold` / `influenzer verdict pass`. Fala may run `uv run python -m influenzer.hom_verdict`.
- **hom_pass** — one CMO look: `hom_feedback` → `scan_due` → tick (score pending briefs) → `hom_outbox` (at most one angle). Reuses those functions; does not copy github_feedback/survey/pack/admit/score/dress/outbox. Does not verdict, publish, enable live, call `gh`, know Heimdall, or run every tick interval. Host compose is `influenzer pass --project-id ID --repo owner/name`. The interval loop may invoke this once when a declared watch is due. Fala may run `uv run python -m influenzer.hom_pass`.
- **hom_watch** — declare one project → one repo (`influenzer watch set` / `watch show`). Persisted in `state.db`. The interval tick reuses `scan_due_reason` and runs existing `hom_pass` when due; otherwise it only scores. Look does not run the project. Launching on watch is silence. `--once` does not scan unless `--pass-if-due`. No Fala organ.
- **scan_due** — a new scan starts only on Monday (Europe/Warsaw) before a look has completed for that Monday; an interrupted look can resume on a later day. Otherwise silence. Reuses `scan_github`; does not call `gh`, score, dress, publish, enable live, or run every tick interval. Host compose is `influenzer brief scan-due`. Fala may run `uv run python -m influenzer.scan_due`.
- **uv** is the Python env/tooling. Mojo is not used here — the HoM copy is fail-closed rules/data in Python.
- Local only. No hosted service, no Ads spend, no live social in this path. 24/7 tick is an always-on host process, not a laptop LaunchAgent.

## Commands

| Command | Purpose |
| --- | --- |
| `influenzer init` | Create workspace home, config, state.db |
| `influenzer project create/show` | App or builder projects with BrandProfile |
| `influenzer content add` | Immutable project-scoped content revision |
| `influenzer brief ingest/show/scan` | HoM brief in; GitHub scan writes 0 or 1 pending brief; tick scores to draft or kill |
| `influenzer brief scan-due` | Starts a new scan only on Monday (Europe/Warsaw) before a look has completed for that Monday; an interrupted look can resume on a later day. Does not score. |
| `influenzer feedback` | Public GitHub replies → 0 or 1 pending brief (`source=github-feedback`). Never publishes. |
| `influenzer pass` | One CMO look: listen, scan-due, score pending briefs, at most one angle. Does not publish. Verdict stays the gate. |
| `influenzer watch set/show` | Declare the one project+repo the interval tick may look at. Explicit CLI only. |
| `influenzer angle` | One wearable draft from `state.db`, or silence. Does not publish. |
| `influenzer verdict` | Hold or pass the current angle. Hold releases the one-story lock. Pass does not post. |
| `influenzer campaign create` | Organic/paid plan (no spend) |
| `influenzer account add/list` | Register existing project-scoped platform accounts using credential refs only; list accounts without secrets |
| `influenzer policy create` | Create an immutable autopublish policy version with account/action scope and limits |
| `influenzer grant activate` | Record a hash-bound activation grant for a policy version; does not enable live adapters |
| `influenzer publish handoff/confirm` | Open an existing approved X plan for manual posting; confirm the manually published status URL with `--url`. No automatic posting. |
| `influenzer-tick-all` | Score pending briefs; does not select, dispatch, or publish plans |
| `influenzer-tick` / `influenzer tick-loop` | Always-on interval loop on a Mac mini. Scores every time; may `hom_pass` when a declared watch is due. `--once` is score-only unless `--pass-if-due`. |

## Platforms (v1 dry-run/contract)

Separate handlers: X, Bluesky, Mastodon, LinkedIn, Instagram, Facebook Pages.

Each dry-run create returns planned envelope fields for capabilities, official API selection note, media limits, rate/idempotency metadata, access/host requirements, and a simulated readback/reconcile shape. These are contract metadata, not implemented network capabilities. All six shipped handlers reject live create and live readback; no live canaries are available in v1. Scheduler success tests using injected fake handlers exercise state transitions, not real platform publication.

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

The canonical local gate is `uv run python -m unittest discover -s tests`.

## Safety

- No Ads spend path.
- No plaintext secrets in config/DB/logs/receipts. Use `influenzer account add --credential-ref env:NAME` (or `keychain:SERVICE/ACCOUNT`), never a raw token.
- Scheduler authorization requires durable live intent (`scheduler.live_enabled=true`) and a current hash-bound grant: create the policy with `influenzer policy create`, then record the grant with `influenzer grant activate`. Neither enables live publication through v1 adapters; CLI ticks do not dispatch plans.
- `influenzer publish handoff --project-id ID --plan-id ID` opens an existing approved X plan for a human to post. Only `influenzer publish confirm --project-id ID --plan-id ID --url https://x.com/HANDLE/status/STATUS_ID` records manual publication; opening the handoff alone does not claim publication.
- No blind retry after ambiguous create — use `unknown` + reconcile.
- Cross-project references are denied.
- SSRF guard: HTTPS-only, host binding, private IP denial, redirect revalidation, size/type bounds.
