#!/bin/bash
# usage: run_replay.sh <fixture.json> <out-dir> <config-json>   (BIN = prepare_go.py build)
set -euo pipefail
mkdir -p "$2"; echo "$3" > "$2/config.json"
export TMPDIR=$(mktemp -d -p /dev/shm vs1010.XXXXXX); trap 'rm -rf "$TMPDIR"' EXIT
MARKETS=${MARKETS:-/vfast/data/code/bitbankpoloniex/data/frontier_20260912/ledger/markets.json}
BOOKS=${BOOKS:-/vfast/data/trading_research_20261009/fidelity/book_snapshots.json.gz}
GOMAXPROCS=${GOMAXPROCS:-2} GOGC=${GOGC:-400} LK_FIXTURE="$1" LK_MARKETS="$MARKETS" LK_BOOKS="$BOOKS" LK_CANDLES="${CANDLES:-/vfast/data/trading_research_20261010/volsize/candles.json.gz}" LK_CONFIG="$3" LK_OUT="$2/results.jsonl" LK_CURVES="$2/curves.csv" \
  "$BIN" -test.run TestFidelityKFoldReplay -test.count=1 -test.timeout 8h -test.v 2>&1 | grep -E '^(fee=|---|ok|FAIL|panic|PASS|stats)' > "$2/run.log"
