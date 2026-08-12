# influenzer-content

Create project-scoped immutable content revisions.

## Rules
- Content always belongs to one project_id.
- Revisions are immutable; edit by creating a new revision_id.
- Use the single modern path: `create_revision` / `influenzer content add`. Status is an explicit `ContentStatus` (`draft`, `in_review`, `ready`, `archived`) — never inferred from an import shim.
- Creating a revision does not claim remote publish success; publish confirmation comes only from the publish/reconcile path.

## Example
```bash
influenzer content add \
  --project-id app-1 --content-id c1 --revision-id r1 \
  --body "Shipped dry-run adapters" --kind post --status ready
```
