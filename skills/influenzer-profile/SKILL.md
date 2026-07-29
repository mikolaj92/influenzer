# influenzer-profile

Manage one Project BrandProfile at a time.

## Rules
- Every app/product is its own Project with an isolated BrandProfile.
- The builder/operator is also a first-class Project (`kind=builder` or `personal`) with its own profile and accounts.
- Never reuse an app voice for builder posts or the reverse.
- Prefer `influenzer project create` / `project show`.

## Example
```bash
influenzer project create \
  --id builder-1 --slug mikolaj --name Mikolaj --display-name Mikolaj \
  --voice "building in public" --audience builders --maintainer mikolaj92 --kind builder
```
