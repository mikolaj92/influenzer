# After install — Influenzer

1. Initialize a workspace:
   ```bash
   python -m influenzer.cli init
   ```
2. Create an **app** project and a **builder** project (separate BrandProfiles):
   ```bash
   python -m influenzer.cli project create --id app-1 --slug my-app --name "My App" \
     --display-name "My App" --voice product --audience customers --maintainer you --kind app
   python -m influenzer.cli project create --id builder-1 --slug me --name Me \
     --display-name Me --voice builder --audience builders --maintainer you --kind builder
   ```
3. Add content under one project only — never share bodies across profiles accidentally.
4. Ingest **briefs** (many facts), or run `influenzer brief scan --project-id app-1 --repo owner/name` to pack public GitHub signals into 0 or 1 pending brief. On a weekly-ish clock, `influenzer pass --project-id app-1 --repo owner/name` is one CMO look: scan-due, score pending briefs, at most one angle. `influenzer brief scan-due` (or `brief scan --if-due`) is the scan-only slice. `influenzer-tick-all` (or `influenzer-tick --once`) scores them: kill, changelog-only, or one-arena draft. `--once` does not scan unless `--pass-if-due`. Borderline briefs stay silent. Drafts are not published. Scan never publishes. Verdict stays the gate.
5. On the always-on host (Mac mini), declare the watch then keep the tick up: `influenzer watch set --project-id app-1 --repo owner/name`, then `uv run influenzer-tick --interval 300` or `contrib/always-on-tick.sh`. The interval loop scores every time and runs the CMO look when scan-due would consider that watch due. Battery laptops fail closed for the interval loop. Do not install a LaunchAgent on a laptop. `--once` is fine anywhere. On **mini-m4-0**, follow [`docs/mini-m4-0.md`](docs/mini-m4-0.md).
6. Keep `scheduler.live_enabled` false until grants and dry-run adapters are verified.
7. Platform credentials stay in env/keychain refs, never in config.
8. HoM canon: https://github.com/mikolaj92/influenzer-playbook
