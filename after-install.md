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
4. Keep `scheduler.live_enabled` false until grants and dry-run adapters are verified.
5. Platform credentials stay in env/keychain refs, never in config.
