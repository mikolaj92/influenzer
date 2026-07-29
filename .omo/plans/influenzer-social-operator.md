# Influenzer Local Social Operator

## TL;DR
> Summary:      Replace the draft-only `build-in-public` plugin with Influenzer: a local, multi-project operator built on Fala/Lokay microprocesses, with versioned policy-based autopublishing, per-platform subprocesses, durable reconciliation, and campaign planning that cannot spend money.
> Deliverables: Influenzer identity/CLI/plugin; multi-project SQLite domain; Fala microprocess runtime; policy and credential gates; X, Bluesky, Mastodon, LinkedIn, Instagram, and Facebook Pages organic adapters; legacy importer; campaign plan/export; metrics; tests/docs/CI.
> Effort:       XL
> Risk:         High - the current product forbids network publishing; the new contract performs irreversible third-party mutations across APIs with different auth, idempotency, review, and readback behavior.

## Scope
### Must have
- Clean cutover from `build-in-public` to `influenzer` in Hermes plugin identity, CLI, config/env names, paths, skills, docs, tests, and package metadata.
- One local workspace containing multiple strictly isolated Projects, each with BrandProfile, Audience, immutable content revisions, campaigns, accounts, policies, plans, attempts, receipts, and metrics.
- Every Project owns its own BrandProfile (voice, audience, maintainer, tone, disclosures). Each app/product is a Project with an isolated profile — never a shared global voice. The builder/operator is also a first-class Project (`kind=builder` or `personal`) with its own BrandProfile and accounts; builder posts do not reuse an app profile and app posts do not leak into the builder project.
- Fala durable runtime plus the minimum Lokay operator shell: result envelope, allowlisted catalog, subprocess boundary, declarative paths, diagnostic ticks, and exactly one scheduled mutator (`influenzer-tick-all`).
- Implementation order note: host-owned domain, SQLite state.db, envelope/catalog/effector, policy, and credential/fetch guards land first (Wave 1). Fala durable runtime (`runtime.db`, process conduction) remains required and is wired after the host-owned shell is green — not descoped. Do not invent a fake Fala host; integrate the real Fala package when T9/T17 need it.
- Dry-run by default. Live organic publication requires both an auditable live intent and a current, immutable, hash-bound PolicyActivationGrant for the project/account/action. Live intent is either CLI `--live` for one-shot operator commands, or the durable audited workspace setting `scheduler.live_enabled` for `influenzer-tick-all` only (default false). For tick-all, CLI `--live` alone is never sufficient and is ignored; only `scheduler.live_enabled=true` plus grant can mutate. Grant alone never mutates; live intent alone never mutates.
- Policy-based autopublish after activation. Manual homeostats remain for initial live activation, policy exceptions, reauthentication, revocation, and ambiguous-outcome resolution.
- One target per PublishPlan. Fanout means independent plans/attempts, never a multi-platform transaction.
- Five platform packages/process boundaries: X, Bluesky, Mastodon, LinkedIn, and Meta. Meta has independently enabled Instagram and Facebook Pages handlers because permissions/payloads/failures differ.
- Organic text and supported still-image publishing with readback. Live multi-part threads are out of v1 because partial chains require a separate state model.
- Campaign planning/export for organic and paid campaigns. Paid plans may carry target budget/currency/cap, but no executable path may mutate Ads/Marketing campaigns or spend.
- Tests-first using existing `unittest`; official APIs only.

### Must NOT have (guardrails, anti-slop, scope boundaries)
- No Ads API create/update/activate, billing, bidding, auto-boost, or spend mutation.
- No Postiz/Mixpost/n8n/service stack, Crosspost MCP exposure, or one Crosspost fanout process.
- No tokens/app passwords/refresh tokens/client secrets/raw secret-bearing responses in config, SQLite, Fala conduction, argv, stdout, logs, receipts, metrics, or evidence.
- No blind retry after timeout or ambiguous create; use `unknown` and read-only reconciliation.
- No legacy `published-manual` mapped to verified remote success.
- No subprocess writes to domain or Fala SQLite; no shared mutable state between platform processes.
- No team/RBAC/cloud sync, hosted runtime or UI, inbox/CRM, moderation, AI media generation, transcoding, attribution, or inferred audiences. Influenzer is installed and executed as a local Hermes plugin.
- No old CLI/config compatibility aliases after cutover; legacy support is an explicit read-only importer.
- No scheduler per platform/lane; only `influenzer-tick-all` is schedulable.
- No remote delete as automatic rollback. If a platform declares delete support, it is a new separately authorized operation; unsupported compensation records the partial success and asks for manual resolution.

## Architecture decisions
### Storage ownership and transaction boundary
- `~/.hermes/influenzer/state.db`: host-owned materialized domain tables and append-only domain events/receipts. One repository transaction writes state transition plus event.
- `~/.hermes/influenzer/runtime.db`: Fala-owned commands/events/processes/runs only. Effectors never open it.
- `~/.hermes/influenzer/artifacts/sha256/<digest>`: immutable content/media/raw-safe artifacts; DB stores digest/type/size/URI.
- No cross-database atomicity claim. Reserve a domain PublicationAttempt before external invocation; deterministic operation keys reconcile Fala completion and domain receipt after crashes.

### Domain states and invariants
- ContentRevision is immutable and addressed by `(revision_id, content_hash)`.
- Campaign: `draft -> awaiting_approval -> approved -> active -> paused|completed|cancelled`; paid remains planning/export only.
- PlatformAccount: `disconnected -> connected -> reauth_required|disabled`; credential presence never means connected.
- PublishPlan: `proposed -> awaiting_policy -> approved -> scheduled -> executing -> succeeded|failed|unknown`; unknown resolves to `reconciled_succeeded|reconciled_absent` before a new attempt.
- PublicationAttempt: `pending -> running -> succeeded|failed|unknown|cancelled`; unique operation key; at most one `pending|running|unknown` attempt per plan.
- MetricSnapshot is append-only and never authorizes publishing or changes policy.
- Every owned row and every Fala manifest/conduction payload carries `project_id`; account, plan, artifact URI, and operation key are validated against it at each boundary.

### Policy-based autopublish authorization
- Immutable hashed PolicyVersion: project/account/action allowlists, content kinds, UTC/local schedule windows, maximum posts per rolling window, asset types, disclosures, prohibited claims/topics, redaction, and capability requirements.
- PolicyActivationGrant binds project, optional account, policy version/hash, actor, creation/expiry, and actions. Creation is an explicit live CLI action backed by a homeostat; never inferred from legacy config.
- Publish decision rereads revision hash, account/capability, current grant, schedule, rate window, assets, campaign boundary, prior attempts, and current policy immediately before reservation and again after retry wait. Scheduler path also rereads `scheduler.live_enabled`; if false, due plans stay dry-run/noop even when grants exist and even if a CLI process was started with `--live`.
- Revocation blocks unstarted attempts. Running/unknown attempts reconcile; they are never repeated automatically.

### Platform subprocess protocol
- One JSON manifest in and exactly one JSON result out; diagnostics only on stderr. Manifest: schema version, project/account identity, platform/handler, operation, operation key, credential-ref names (not values), payload digest, content/media refs, API version, dry-run, deadline.
- Result: schema version, status, `ok`, `mutated`, provider ID/URI, canonical URL, request ID, safe error code, failure class, retry safety, retry-after, rate snapshot, readback digest.
- Failure taxonomy: `pre_send_retryable`, `rate_limited`, `auth`, `access_review`, `validation`, `permanent`, `ambiguous_unknown`. Only pre-send/rate cases retry after policy re-evaluation; ambiguous requires reconciliation.
- Operations: `capabilities`, `probe_account`, `prepare_media`, `publish`, `readback`, `metrics`; optional `delete` is separate and authorization-gated.

### Network and media fetch safety
- All outbound adapter HTTP is HTTPS-only. Arbitrary Mastodon instance hosts and Bluesky PDS hosts must match the connected PlatformAccount host binding before any request.
- Instagram/public media URLs and any adapter-side media fetch revalidate after redirects: no private/link-local/loopback/metadata IPs, no file/gopher schemes, no cross-scheme downgrade, bounded size/time, and content-type allowlist.
- Fail closed on DNS rebinding (resolve then connect to same allowlisted address family/result), redirect chains beyond a fixed limit, or host mismatch vs account binding.
- Tests cover blocked private IPs, redirect-to-internal, oversized bodies, and wrong-host PDS/instance.

### Adapter reuse decision rule
Each candidate gets at most one implementation day. Versions below are the 2026-07-29 research baseline, not a frozen lock: at spike time re-check latest official release/tag, license, and changelog; pin the re-verified version (or reject the candidate) and record both baseline and chosen pin in spike evidence. Score: security boundary pass/fail; license/official-API pass/fail; create+media+readback (3); stable machine output (2); no persistent cleartext secret state (2); dependency/maintenance burden (1); wrapper under 200 non-test lines (1). Security/license failure rejects it; highest score wins; ties prefer official standalone CLI, then fewer dependencies.
- X: official `xurl` v1.3.1 vs Tweepy 4.17.0. `xurl` requires isolated HOME, redaction, stable JSON, and readback.
- Bluesky: official `goat` v0.2.3 vs `atproto` 0.0.69. `goat` requires safe output normalization and ephemeral HOME replacing cleartext persistent state.
- Mastodon: pin PyPI `Mastodon.py==2.2.1` from canonical upstream `https://github.com/halcy/Mastodon.py` (MIT) with provider Idempotency-Key/readback. Do not use the `InformationX/mastodon.py` path from the OpenSocialTools snapshot without re-verification; treat that as a mis-tagged research cite.
- LinkedIn: project-owned standard-library HTTPS against current REST/media APIs; no stale/proprietary/private SDK.
- Meta: project-owned Graph HTTPS. Business SDK only after recorded license approval; default is direct HTTP.
- Crosspost 1.0.4 is reference/substrate only; never owns fanout, policy, scheduling, retries, or readback.

## Verification strategy
> Zero human intervention - all verification is agent-executed. CI uses deterministic local provider fakes; real provider access is a runtime preflight gate.
- Test decision: **TDD** with Python `unittest`; local fake HTTP servers and subprocess fixtures.
- QA policy: every todo includes happy and failure scenarios; mutations prove dry-run, policy, idempotency, and unknown/reconcile.
- Evidence: `.omo/evidence/task-<N>-<slug>.<ext>` with command, exit code, assertion summary, no secrets.
- Baseline: `python -m unittest discover -s tests -v`; `python tools/hygiene_check.py`.

## Execution strategy
### Parallel execution waves
- Wave 1: T1 identity, T2 domain, T3 persistence, T4 envelope/catalog, T5 policy, T6 secrets.
- Wave 2: T7 importer/content, T8 campaigns/assets/metrics, T9 Fala/scheduler, T10 adapter harness, T11 CLI/plugin.
- Wave 3 (dry-run/contract only, parallel): T12 X, T13 Bluesky, T14 Mastodon, T15 LinkedIn, T16 Meta. Each adapter ships behind fakes/conformance only; no live account enablement in this wave.
- Wave 4: T17 end-to-end operator against fakes plus staged live-enablement gates in locked order Bluesky+Mastodon → X → LinkedIn/Meta; T18 Hermes plugin docs/CI/release validation only after dry-run e2e green (live canary evidence may remain handler-local).
- Critical path: T1 -> T2-T6 -> T9/T10 -> parallel dry-run adapters -> T17 (fake e2e then sequential live gates) -> T18 -> final verification.
- Live enablement rule: adapter implementation and fake conformance may run in parallel; first real/live canary for a handler is ordered Bsky+Mastodon first (either order between them after both dry-run green), then X, then LinkedIn, then Meta Instagram/Facebook Pages (IG and FB independently gated but both after LinkedIn). A later handler may not receive its first live canary before earlier stages have a verified receipt or an explicit recorded access-blocked waiver.

### Dependency matrix
| Todo | Depends on | Blocks | Can parallelize with |
|---|---|---|---|
| T1 | - | T7,T9-T11,T18 | T2-T6 |
| T2 | - | T3,T5,T7-T9,T17 | T1,T4,T6 |
| T3 | T2 | T7-T11,T17 | T4-T6 |
| T4 | - | T9,T10,T17 | T1-T3,T5,T6 |
| T5 | T2 | T9,T11,T17 | T3,T4,T6 |
| T6 | - | T10,T12-T17 | T1-T5 |
| T7 | T1-T3 | T17 | T8-T11 |
| T8 | T2,T3 | T17 | T7,T9-T11 |
| T9 | T1-T5 | T17 | T7,T8,T10,T11 |
| T10 | T1,T3,T4,T6 | T12-T17 | T7-T9,T11 |
| T11 | T1,T3,T5 | T17,T18 | T7-T10 |
| T12-T16 | T6,T10 | T17 (dry-run e2e) | each other for dry-run/contract only |
| T17 | T7-T16 | T18 | live canaries sequential per Live enablement rule |
| T18 | T11,T17 | F1-F4 | - |

## Todos
> Implementation + Test = ONE todo. Write failing contract tests first inside each todo.

- [ ] 1. Cut over identity and create the package skeleton
  What to do: Add `pyproject.toml`, `influenzer/`, console entrypoints `influenzer`, `influenzer-tick-all`, diagnostic tick. Change the Hermes manifest/root registration to `influenzer`; define `HERMES_INFLUENZER_CONFIG` and `~/.hermes/influenzer/`; remove no-op Kanban hook/fake sources. No old alias.
  Parallelization: Y | Wave 1 | Blocks T7,T9-T11,T18
  References: `plugin.yaml:1-9`; `__init__.py:1-30`; `commands.py:1-198`; `config.py:1-188`; `/Users/mini-m4-main/Developer/lokay/pyproject.toml`; `lokay/src/lokay/tick_common.py`.
  Acceptance: tests assert only `influenzer` registers; `python -m influenzer --help` passes; no operational old namespace outside importer fixtures.
  QA: `python -m unittest tests.test_identity -v` (new identity; old env/CLI rejection) -> `.omo/evidence/task-1-identity.txt`.
  Commit: Y | `feat(identity): cut over plugin to influenzer` | package/manifest/registration/tests

- [ ] 2. Define immutable domain records and state transitions
  What to do: Typed records/enums and pure transitions for all entities above. Canonical sorted UTF-8 JSON hashing. Enforce project identity, immutable revisions, one-target plans, append-only approvals/metrics, and unknown reconciliation. Keep Fala Process state out. Model BrandProfile as required per Project; support at least two concurrent projects (one `app`, one `builder`/`personal`) with strict isolation of profile, content, accounts, plans, and metrics.
  Parallelization: Y | Wave 1 | Blocks T3,T5,T7-T9,T17
  References: `card.py:13-169`; `schemas/build-card.schema.json`; `agent://DomainModel`; `Fala/docs/EVENT_STREAM_CORE.md:32-147`.
  Acceptance: table tests reject every illegal transition, stale hash, cross-project ref; new revision invalidates authorization without rewriting history.
  QA: `python -m unittest tests.test_domain -v` -> `.omo/evidence/task-2-domain.txt`.
  Commit: Y | `feat(domain): define influenzer state machines` | domain/tests

- [ ] 3. Implement host-owned SQLite, events, migrations, artifacts
  What to do: Versioned `state.db`; separate Fala `runtime.db`; atomic state+event transactions; composite project checks; unique operation key; one active attempt; immutable SHA-256 artifacts; WAL; future versions fail loudly.
  Parallelization: Y | Wave 1 | Blocked by T2 | Blocks T7-T11,T17
  References: `storage.py:12-73`; `Fala/docs/EVENT_STREAM_CORE.md`; `Fala/docs/MIGRATIONS.md`.
  Acceptance: empty/v1 migration, reopen, event preservation, future-version rejection, concurrency constraints, corruption detection.
  QA: `python -m unittest tests.test_persistence -v` -> `.omo/evidence/task-3-persistence.txt`.
  Commit: Y | `feat(storage): add durable local domain state` | storage/migrations/tests

- [ ] 4. Implement envelopes, catalog, and effector boundary
  What to do: Port only Lokay pattern: `ok/planned/noop/fail`, accessors, dry-run default, terminal-upstream, allowlisted catalog, strict Fala subprocess normalization/redaction. Reject undeclared handlers and false mutation claims.
  Parallelization: Y | Wave 1 | Blocks T9,T10,T17
  References: `lokay/src/lokay/envelope.py`; `catalog.py`; `effector.py`; `Fala/python/fala/sdk.py`; `Fala/docs/ADAPTER_CONTRACTS.md`.
  Acceptance: status/conduction/redaction/malformed/unknown-handler/dry-run violation tests.
  QA: `python -m unittest tests.test_envelope tests.test_effector -v` -> `.omo/evidence/task-4-effectors.txt`.
  Commit: Y | `feat(runtime): add envelope catalog and boundary` | runtime/tests

- [ ] 5. Build versioned autopublish policy and activation grants
  What to do: Canonical policy hashing/evaluation for core live gates in v1 Wave 1: grant+live intent (CLI one-shot vs scheduler.live_enabled), policy/grant/content hash binding, project/account isolation, expiry/revocation, action/content-kind allowlists, max_posts_per_day, disclosures. `zoneinfo` schedule windows (nonexistent local advances; ambiguous fold=1; persist UTC) plus prohibited claims/topics and asset-type gates are deferred to Wave 2 scheduler task (T9) — PolicyVersion fields for windows/topics/assets land with that task, not T5.
  Parallelization: Y | Wave 1 | Blocked by T2 | Blocks T9,T11,T17
  References: `skills/maintainer-narrative-policy/SKILL.md`; `redaction.py:6-20`; `agent://DomainModel`.
  Acceptance: allow and every core denial, expiry/revocation/hash change/rate/disclosure deterministically tested with injected aware clock. Schedule-window/DST/topics/assets coverage is T9 acceptance, not T5.
  QA: `python -m unittest tests.test_policy -v` -> `.omo/evidence/task-5-policy.txt`.
  Commit: Y | `feat(policy): add hash-bound autopublish grants` | policy/tests

- [ ] 6. Define credential-provider and subprocess isolation
  What to do: Only `env:NAME` and `keychain:SERVICE/ACCOUNT`; resolve to allowlisted child env. Never manifest/argv. Redact output/errors; limit size/deadline. CLI state uses `0700` temp HOME, minimum hydration, provider-backed token rotation, deletion on all exits. Reject plaintext file refs. Implement shared HTTPS fetch guard used by adapters: host binding to PlatformAccount, private/link-local/loopback/metadata IP denial, redirect revalidation, size/time bounds, content-type allowlist.
  Parallelization: Y | Wave 1 | Blocks T10,T12-T17
  References: `config.py:66-115`; `redaction.py`; `tools/hygiene_check.py`; `agent://OpenSocialTools`.
  Acceptance: sentinel absent from manifest/argv/DB/artifacts/logs/errors/evidence; platform env isolation and temp cleanup proven; SSRF suite blocks private IP, redirect-to-internal, host mismatch, oversized body.
  QA: `python -m unittest tests.test_credentials tests.test_subprocess_security tests.test_fetch_guard -v`; hygiene -> `.omo/evidence/task-6-secrets.txt`.
  Commit: Y | `feat(security): isolate credentials and outbound fetches` | credentials/process/fetch-guard/tests

- [ ] 7. Replace BuildCard ingestion and add explicit legacy importer
  What to do: Preserve provenance/narrative/redaction as ContentRevision. `import-build-cards --dry-run|--commit`; deterministic project/audience dedupe; collision report. Map draft->draft, reviewed->in_review unless proof, published-manual->legacy_unverified. No account/plan/attempt; old config only explicit importer input.
  Parallelization: Y | Wave 2 | Blocked by T1-T3 | Blocks T17
  References: `collector.py`; `card.py`; `renderer.py`; `schemas/build-card.schema.json`; `agent://CurrentGapMap`; `agent://DomainModel`.
  Acceptance: golden deterministic/idempotent import, dry-run no write, collisions/redaction, no fake success.
  QA: `python -m unittest tests.test_content tests.test_legacy_import -v` -> `.omo/evidence/task-7-import.txt`.
  Commit: Y | `feat(content): migrate build cards into revisions` | content/import/tests

- [ ] 8. Implement no-spend campaigns, assets, exports, metrics
  What to do: Organic/paid planning; budget/currency/cap validation; disclosures/audiences; assets; deterministic JSON/Markdown export; append-only metrics. No adapter mutation imports; exports never authorize publishing; metrics never auto-change policy.
  Parallelization: Y | Wave 2 | Blocked by T2,T3 | Blocks T17
  References: `renderer.py`; `storage.py`; `agent://DomainModel`; `agent://PlatformResearch`.
  Acceptance: paid metadata exports only; reachability/import test proves no Ads/Marketing mutation; metrics project-isolated/append-only.
  QA: `python -m unittest tests.test_campaigns tests.test_assets tests.test_metrics -v` -> `.omo/evidence/task-8-campaigns.txt`.
  Commit: Y | `feat(campaigns): add no-spend planning and exports` | campaigns/assets/metrics/tests

- [ ] 9. Compose Fala paths and single leased scheduler
  What to do: `fala-package.toml` paths for ingest/render/plan-policy/probe/publish/reconcile/metrics plus `auto_worker`; all handlers catalog-resolved. Tick-all gets atomic renewable 60s workspace lease, due-plan claim, operation key, active-attempt constraint. Live organic mutation through tick-all requires durable `scheduler.live_enabled=true` plus current grant; default false means dry-run/noop even with grants. Enabling/disabling that setting is an explicit audited CLI/homeostat action (not inferred from grant creation). Diagnostics cannot use `--live` and ignore scheduler live config for mutations.
  Parallelization: Y | Wave 2 | Blocked by T1-T5 | Blocks T17
  References: `lokay/fala-package.toml`; `lokay/src/lokay/flows/runtime.py`; `tick_all.py`; `Fala/python/fala/host.py`; `agent://LokayPattern`.
  Acceptance: topology/conduction/identity tests; two concurrent ticks dispatch once; lease recovery; replay no duplicate; grant-only does not live-publish; live config false forces dry-run; only tick-all/live CLI can mutate when both live intent and grant exist.
  QA: `python -m unittest tests.test_paths tests.test_scheduler -v` -> `.omo/evidence/task-9-scheduler.txt`.
  Commit: Y | `feat(orchestration): compose worker paths` | package/flows/ticks/tests

- [x] 10. Implement adapter contract and fake-provider harness
  What to do: Versioned protocol/error taxonomy/deadlines/output limits/payload digest/unknown reconciliation. Local fake HTTP provider and unchanged conformance suite. Account capability/access can be unavailable without blocking install.
  Parallelization: Y | Wave 2 | Blocked by T1,T3,T4,T6 | Blocks T12-T17
  References: `Fala/docs/ADAPTER_CONTRACTS.md`; `Fala/mojo/fala/adapters.mojo`; `agent://PlatformResearch`; SDK research artifacts.
  Acceptance: fake adapter passes create/media/readback/rate/auth/permanent/pre-send/ambiguous cases; malformed/oversized/secret/multi-result fails. Delivered via loopback `FakeHTTPServer` + `run_adapter_subprocess` child worker (exactly-one JSON stdout, stderr separated, timeout kill, output size bounds). In-process FakeProvider remains for unit taxonomy; T10 closed on subprocess/HTTP path.
  QA: `python -m unittest tests.test_adapter_contract tests.test_fake_provider -v` -> `.omo/evidence/task-10-adapter-contract.txt`.
  Commit: Y | `feat(adapters): define isolated provider protocol` | adapter base/schemas/fakes/tests

- [ ] 11. Build CLI and Hermes plugin/skill surface
  What to do: Commands for project/brand/audience/content/campaign/asset/account/policy/plan/approve-resolve/publish/run-inspect/metrics/import/export. Remote mutations dry-run by default; flag+grant required. Probe and activate/revoke homeostats. Qualified `influenzer:*` skills only; skills cannot grant live authority.
  Parallelization: Y | Wave 2 | Blocked by T1,T3,T5 | Blocks T17,T18
  References: `commands.py`; `__init__.py`; `after-install.md`; `skills/**`; `lokay/src/lokay/tick_common.py`.
  Acceptance: parser/subprocess tests for all commands; flag-only/grant-only denied; inspect read-only; stable secret-free JSON.
  QA: `python -m unittest tests.test_cli tests.test_plugin -v`; help smoke -> `.omo/evidence/task-11-cli.txt`.
  Commit: Y | `feat(cli): expose local operator workflows` | CLI/plugin/skills/tests

- [ ] 12. Implement and select X backend (dry-run/contract)
  What to do: Score baseline candidates xurl 1.3.1 vs Tweepy 4.17.0 after re-verifying current releases/tags/licenses at spike time. Implement winning isolated adapter: OAuth probe, text/image upload, create, GET readback, cost/access capability, rate/request metadata, reconciliation. No private APIs. Ship dry-run/fake conformance only; first live canary waits for Wave-4 ordered enablement after Bluesky+Mastodon.
  Parallelization: Y | Wave 3 dry-run | Blocked by T6,T10 | Blocks T17
  References: `agent://OpenSocialTools`; `agent://PythonPlatformSDKs`; `https://docs.x.com/x-api/posts/manage-tweets/integrate`; pricing docs.
  Acceptance: conformance; scored decision with re-verified pins (baseline vs chosen); dry-run zero HTTP; timeout reconcile; media before create; ID readback. No live canary required to close this todo.
  QA: `python -m unittest tests.adapters.test_x -v` -> `.omo/evidence/task-12-x.txt`, spike JSON including pin re-verification.
  Commit: Y | `feat(adapters): add X publishing process` | X adapter/dependency metadata/tests
- Status: dry-run/contract + subprocess HTTP harness green; **pins not re-verified** (`spike_scores.json` pin_status=baseline_research_not_reverified). Leave open until live-spike re-verify.

- [ ] 13. Implement and select Bluesky backend (dry-run/contract)
  What to do: Score baseline goat 0.2.3 vs atproto 0.0.69 after re-verifying current releases/tags/licenses at spike time. Implement account/session, blob, createRecord, URI/CID readback, refresh rotation, operation-key reconciliation, arbitrary PDS. Goat must pass T6 ephemeral state. Dry-run/fake conformance only in this todo; Bluesky is stage-1 for later live canary with Mastodon.
  Parallelization: Y | Wave 3 dry-run | Blocked by T6,T10 | Blocks T17
  References: tooling research; `https://docs.bsky.app/docs/get-started`; rate limits.
  Acceptance: conformance; credential-provider-only rotated session; no duplicate on timeout; URI/CID and non-default PDS verified; spike records re-verified pins. No live canary required to close this todo.
  QA: `python -m unittest tests.adapters.test_bluesky -v` -> `.omo/evidence/task-13-bluesky.txt`, spike JSON including pin re-verification.
  Commit: Y | `feat(adapters): add Bluesky publishing process` | adapter/metadata/tests

- [ ] 14. Implement Mastodon with provider idempotency (dry-run/contract)
  What to do: Re-verify PyPI `Mastodon.py` + upstream `halcy/Mastodon.py` at spike time (baseline 2.2.1); pin the re-verified release. Instance/token probe; media processing; mandatory stable Idempotency-Key; optional native schedule capability; GET readback; instance limits. Local scheduler remains authoritative. Dry-run/fake conformance only; Mastodon is stage-1 for later live canary with Bluesky.
  Parallelization: Y | Wave 3 dry-run | Blocked by T6,T10 | Blocks T17
  References: `agent://PythonPlatformSDKs`; `https://github.com/halcy/Mastodon.py`; `https://docs.joinmastodon.org/methods/statuses/`; rate-limit docs. Re-verify package/repo identity at spike time before lock.
  Acceptance: conformance; same key creates once; media pending/error; private readback scope; instance override; chosen pin recorded against baseline. No live canary required to close this todo.
  QA: `python -m unittest tests.adapters.test_mastodon -v` -> `.omo/evidence/task-14-mastodon.txt` with pin re-verification note.
  Commit: Y | `feat(adapters): add Mastodon publishing process` | adapter/tests

- [ ] 15. Implement current-version LinkedIn REST process (dry-run/contract)
  What to do: Standard-library HTTPS; OAuth code/refresh; member/org probe/roles; configurable supported `Linkedin-Version` and Rest.li 2; image upload; `/rest/posts`; URN capture/readback; access/rate classification. Fail pre-send on sunset version. Dry-run/fake conformance only; first live canary is stage-3 after X.
  Parallelization: Y | Wave 3 dry-run | Blocked by T6,T10 | Blocks T17
  References: `agent://PlatformResearch`; `agent://PythonPlatformSDKs`; LinkedIn Posts/access official docs.
  Acceptance: conformance for member/org/media/version/201+URN; missing review/role and stale version pre-send failure; ambiguous reconcile. No live canary required to close this todo.
  QA: `python -m unittest tests.adapters.test_linkedin -v` -> `.omo/evidence/task-15-linkedin.txt`.
  Commit: Y | `feat(adapters): add LinkedIn publishing process` | adapter/tests

- [ ] 16. Implement independently gated Instagram and Facebook Pages handlers (dry-run/contract)
  What to do: One Meta package, distinct handlers/capabilities/grants. Direct Graph HTTP. Instagram: professional probe, dynamic quota, public-media preflight, container/poll/publish/readback. Facebook Pages: tasks/permissions, feed/photo create/readback. Container timeout differs from publish timeout. No Ads endpoints/scopes. Dry-run/fake conformance only; first live canaries are stage-4 after LinkedIn and independent of each other.
  Parallelization: Y | Wave 3 dry-run | Blocked by T6,T10 | Blocks T17
  References: `agent://PlatformResearch`; Meta official Instagram overview/publishing and Pages getting-started docs.
  Acceptance: both independently conform; grants cannot cross handlers; quota dynamic; ERROR/EXPIRED/timeout reconcile; no Ads symbol/scope. No live canary required to close this todo.
  QA: `python -m unittest tests.adapters.test_instagram tests.adapters.test_facebook_pages -v` -> `.omo/evidence/task-16-meta.txt`.
  Commit: Y | `feat(adapters): add Meta organic processes` | Meta adapter/tests

- [ ] 17. Prove end-to-end autopublish, crash recovery, and ordered live rollout gates
  What to do: Compose all layers with fakes first. Handler live gate checklist: conformance green, secret suite green, dry-run parity, account probe, create/readback, ambiguity recovery, rate limit, revocation; canary max one live operation/account until verified receipt. First-live homeostat creates scoped grant; routine compliant posts auto-run only after grant + live intent. Provider approval absence keeps account unavailable, not installation broken. **Live canary order is mandatory:** stage 1 Bluesky and Mastodon (parallel after both dry-run green), stage 2 X only after stage-1 verified receipt or recorded access-blocked waiver, stage 3 LinkedIn after X, stage 4 Instagram and Facebook Pages independently after LinkedIn. Do not start a later stage's first live canary early.
  Parallelization: N for live stages | Wave 4 | Blocked by T7-T16 | Blocks T18
  References: runtime/domain/platform research; `Fala/docs/EVENTS_AND_REPLAY.md`.
  Acceptance: fake path proves dry-run -> activate -> scheduled auto-publish -> receipt -> metric; second tick noop; crash unknown/reconcile; revoke blocks; cross-project/Meta grants fail. Live evidence files name stage order and either verified receipt or access-blocked waiver per handler; no later-stage live canary precedes earlier stages.
  QA: `python -m unittest tests.test_e2e_operator -v`; concurrent tick smoke; ordered live-canary evidence when accounts exist -> `.omo/evidence/task-17-e2e.txt` plus `.omo/evidence/task-17-live-stage-{1..4}.txt`.
  Commit: Y | `feat(operator): complete policy-gated flow` | integration/tests

- [ ] 18. Finish Hermes plugin docs, skills, CI, and hygiene
  What to do: Rewrite README/after-install/examples for Hermes plugin setup, projects, grants, accounts, unknown reconciliation, prerequisites/cost, no-spend campaigns, and importer. Rewrite qualified skills. CI runs unit/adapter/package/schema/hygiene. Validate the local Hermes plugin manifest and registration. Do not delete legacy user data.
  Parallelization: N | Wave 4 | Blocked by T11,T17 | Blocks F1-F4
  References: `README.md`; `after-install.md`; examples; skills; CI; hygiene tool; `plugin.yaml`; root `__init__.py`.
  Acceptance: docs quickstart works in temp HOME; full suite/hygiene green; Hermes recognizes and enables the `influenzer` plugin; importer warning explicit.
  QA: documented fake-provider quickstart + full suite + hygiene + local Hermes plugin smoke -> `.omo/evidence/task-18-release.txt`.
  Commit: Y | `docs(release): complete Influenzer plugin cutover` | docs/skills/examples/CI/hygiene

## Final verification wave (after ALL todos)
> Run in parallel. ALL must APPROVE. Surface results and wait for explicit user okay before declaring complete.
- [ ] F1. Plan compliance audit — verify every Must/Must NOT and todo evidence; reject missing handler, old namespace, ungranted live path, Ads mutation, or fake legacy success. Evidence `.omo/evidence/final-plan-compliance.md`.
- [ ] F2. Code quality/security review — transitions, transactions, leases, process isolation, redaction, retries, versions, licenses; full tests/hygiene. Evidence `.omo/evidence/final-quality-security.md`.
- [ ] F3. Real local manual QA — clean temp HOME, two projects, legacy import, campaign/content, dry-run, scoped activation, tick, receipt/metric, ambiguity/reconcile, revoke/no further post. Evidence `.omo/evidence/final-manual-qa.txt`.
- [ ] F4. Scope fidelity/identity — confirm no browser/private API/service/Ads/thread mutation/cloud/alias/secret persistence; six independently gated handlers; Hermes plugin identity is `influenzer`. Evidence `.omo/evidence/final-scope-fidelity.md`.

## Commit strategy
- Commit each coherent todo only after its tests pass; no standalone failing-test commits.
- Author only `mikolaj92`; no AI/co-author/generated trailers.
- Release only after Hermes plugin checks pass; source hosting and repository naming are outside the product runtime contract.
- No temporary compatibility aliases; remove superseded files with their replacement todo.

## Success criteria
- `influenzer` is the only active Hermes plugin identity; execution and persistent state remain local.
- Two projects (e.g. one app + builder) operate with separate BrandProfiles and without cross-project leakage.
- Dry-run performs no provider mutation.
- Hash-bound grants allow compliant scheduled organic autopublish without per-post approval; policy change/expiry/revocation blocks immediately.
- X, Bluesky, Mastodon, LinkedIn, Instagram, and Facebook Pages run as isolated independently gated handlers and pass one conformance suite.
- Duplicate ticks/crashes do not silently duplicate; ambiguity reconciles before retry.
- Paid campaign metadata plans/exports, but no executable path spends.
- Legacy cards import deterministically and `published-manual` never becomes verified success.
- Secrets are absent from config/persistence/manifests/argv/output/logs/receipts/metrics/evidence.
- Full tests, hygiene, fake-provider smoke, final audits, and identity checks pass with evidence.

## Metis absorption notes
Metis verdict on the draft was `incorrect` (confidence 0.99): decision-complete plan needed, not more product direction. Absorbed into this plan:

1. Persistence ownership / transactions — Architecture `state.db` vs `runtime.db`, atomic domain+event write, operation-key reconciliation, T3.
2. Versioned policy + live authorization — grant/hash/re-eval before reserve and after retry wait, T5/T9/T17.
3. Meta IG vs FB isolation — five packages, six independently gated handlers, T16/T17.
4. Catalog / path dispatch — allowlisted catalog + declarative Fala paths, T4/T9.
5. Scheduler leases / active-attempt concurrency — 60s lease, unique active attempt, T9/T3.
6. Credential-provider / subprocess secret contract — env/keychain refs only, T6.
7. Exact legacy migration — importer status map and no remote-success inference, T7.
8. No-spend campaign/export boundary — T8 reachability/import tests.
9. Adapter outcome / capability contract — failure taxonomy, unknown/reconcile, T10.
10. Staged rollout acceptance gates — canary + e2e, T17/F*.
11. Hermes manifest/registration — T1/T11 pin name, bare-skill removal, hook migration.
12. Failure/retry taxonomy + policy re-eval — protocol section and T5/T10.
13. Project/account identity through conduction/manifests/artifact URIs — domain invariants + T9/T10.
14. Delete/rollback compensation — Must NOT automatic delete; optional capability-gated delete only; unsupported partial success needs manual resolution.
15. Scheduler live intent — durable audited `scheduler.live_enabled` (default false) required for tick-all autopublish; grant alone insufficient; T9/T5/T17.
16. Outbound fetch/SSRF controls — HTTPS-only, account host binding, private IP/redirect revalidation, bounded fetch; T6 + adapter harness.
17. Live enablement order vs Wave 3 — dry-run/contract adapters remain parallel; first live canaries ordered Bsky+Mastodon → X → LinkedIn → Meta; T12-T16 close without live; T17 owns staged canaries.

Research inputs: CurrentGapMap, LokayPattern, DomainModel, PlatformResearch, PythonPlatformSDKs, NonPythonPlatformCLIs, OpenSocialTools.
No product code until explicit `$start-work` (or equivalent).
