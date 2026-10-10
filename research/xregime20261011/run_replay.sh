#!/bin/bash
set -euo pipefail
mkdir -p "$2"; echo "$3" > "$2/config.json"
export TMPDIR=$(mktemp -d -p /dev/shm xr1011.XXXXXX); trap 'rm -rf "$TMPDIR"' EXIT
GOMAXPROCS=${GOMAXPROCS:-1} GOGC=${GOGC:-400} LK_FIXTURE="$1" LK_MARKETS="$MARKETS" LK_BOOKS="$BOOKS" LK_CONFIG="$3" LK_OUT="$2/results.jsonl" LK_CURVES="$2/curves.csv" \
  "$BIN" -test.run TestXRegimeReplay -test.count=1 -test.timeout 8h -test.v 2>&1 | grep -E '^(fee=|---|ok|FAIL|panic|PASS)' > "$2/run.log"
