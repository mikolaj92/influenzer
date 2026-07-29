# influenzer-content

Create project-scoped immutable content revisions.

## Rules
- Content always belongs to one project_id.
- Revisions are immutable; edit by creating a new revision_id.
- Legacy build-card imports become `legacy_unverified` and never claim remote publish success.
- Prefer `influenzer content add`.

## Example
```bash
influenzer content add \
  --project-id app-1 --content-id c1 --revision-id r1 \
  --body "Shipped dry-run adapters" --kind post --status ready
```
