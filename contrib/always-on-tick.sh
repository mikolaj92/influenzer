#!/bin/sh
# Keep the HoM tick up on an always-on host (Mac mini). Not a laptop LaunchAgent.
# Run this on the box that already has the checkout, uv, and state.db.
# This repository does not SSH or deploy.
set -eu
ROOT=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
cd "$ROOT"
INTERVAL=${INFLUENZER_TICK_INTERVAL:-300}
exec uv run influenzer-tick --interval "$INTERVAL" "$@"
