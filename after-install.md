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
4. Ingest **briefs** (many facts). `influenzer-tick-all` (or `influenzer-tick --once`) scores them: kill, changelog-only, or one-arena draft. Borderline briefs stay silent. Drafts are not published.
5. Keep the tick local: `uv run influenzer-tick --interval 300` or a shell loop around `influenzer-tick-all`. No LaunchAgent. No Mac mini.
6. Keep `scheduler.live_enabled` false until grants and dry-run adapters are verified.
7. Platform credentials stay in env/keychain refs, never in config.
8. HoM canon: https://github.com/mikolaj92/influenzer-playbook
