#!/bin/bash
# usage: run_replay.sh <fixture.json> <out-dir> [config-json]   (deployed profile by default)
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
CFG=${3:-'{"Slots":3,"Cooldown":120,"WindowCycles":12,"Reserve":0.4,"HaltPeak":0.25,"HaltDaily":0.08,"TopUp":true,"Budget":"495","MaxOrder":"49","Fees":[0.003,0.004]}'}
mkdir -p "$2"; echo "$CFG" > "$2/config.json"
export TMPDIR=$(mktemp -d -p /dev/shm lkreplay.XXXXXX); trap 'rm -rf "$TMPDIR"' EXIT  # engine fsyncs state every cycle
BIN=${BIN:-$ROOT/data/longkfold20261007/gobuild/replay.test}
MARKETS=${MARKETS:-$ROOT/data/frontier_20260912/ledger/markets.json}
GOMAXPROCS=${GOMAXPROCS:-2} LK_FIXTURE="$1" LK_MARKETS="$MARKETS" LK_CONFIG="$CFG" LK_OUT="$2/results.jsonl" LK_CURVES="$2/curves.csv" \
  "$BIN" -test.run TestLongKFoldReplay -test.count=1 -test.timeout 6h -test.v 2>&1 | grep -E '^(fee=|---|ok|FAIL|panic|PASS)' > "$2/run.log"
