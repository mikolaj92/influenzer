# Hop onto mini-m4-0

I hop onto **mini-m4-0**, the always-on Mac mini, and start the existing dry-run tick from the checkout that already has `uv` and `state.db`. This repo does not SSH or deploy.

The laptop sleeps. The tick belongs on mini-m4-0.

## Keep the tick up

From that checkout:

```bash
contrib/always-on-tick.sh
# or:
uv run influenzer-tick --interval 300
```

`--once` is fine anywhere (including a laptop). The interval loop fails closed on a battery laptop.

## Leave mill alone

Lokay's mill already heartbeats on this box: LaunchAgent label `ai.mikolaj.lokay-mill` → `scripts/lokay-mill-daemon.sh` (in [mikolaj92/lokay](https://github.com/mikolaj92/lokay)). I leave that LaunchAgent as-is. I do **not** install an Influenzer LaunchAgent on the mini or the laptop. There is no plist in this repo.

## Live social stays off

Dry-run is default. Keep `scheduler.live_enabled` false. CLI `--live` is ignored on this path; only the durable config flag can authorize live mutation, and we are not flipping it.
