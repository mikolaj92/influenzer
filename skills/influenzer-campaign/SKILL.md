# influenzer-campaign

Plan organic and paid campaigns without spend.

## Rules
- Paid campaigns may store budget/currency/disclosures for planning/export only.
- No Ads/Marketing API mutation path exists and must not be invented.
- Campaigns are project-scoped.

## Example
```bash
influenzer campaign create \
  --project-id app-1 --campaign-id launch --name Launch --kind paid \
  --budget-amount 100 --budget-currency USD --disclosure ad
```
