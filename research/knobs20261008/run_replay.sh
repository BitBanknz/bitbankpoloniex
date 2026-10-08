#!/bin/bash
# usage: run_replay.sh <fixture.json> <out-dir> <config-json>  (research build data/knobs/gobuild)
set -euo pipefail
ROOT=/vfast/data/wt/bbpx-knobs
mkdir -p "$2"; echo "$3" > "$2/config.json"
export TMPDIR=$(mktemp -d -p /dev/shm knobs.XXXXXX); trap 'rm -rf "$TMPDIR"' EXIT
BIN=${BIN:-$ROOT/data/knobs/gobuild/replay.test}
MARKETS=${MARKETS:-/vfast/data/code/bitbankpoloniex/data/frontier_20260912/ledger/markets.json}
GOMAXPROCS=${GOMAXPROCS:-2} GOGC=${GOGC:-400} LK_FIXTURE="$1" LK_MARKETS="$MARKETS" LK_CONFIG="$3" LK_OUT="$2/results.jsonl" LK_CURVES="$2/curves.csv" \
  "$BIN" -test.run TestLongKFoldReplay -test.count=1 -test.timeout 6h -test.v 2>&1 | grep -E '^(fee=|---|ok|FAIL|panic|PASS)' > "$2/run.log"
