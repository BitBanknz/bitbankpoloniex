#!/bin/bash
set -uo pipefail
R=$(cd "$(dirname "$0")" && pwd)
export BIN=${BIN:-$R/bin/replay.test} MARKETS=${MARKETS:-$R/in/markets.json} BOOKS=${BOOKS:-$R/in/book_snapshots.json.gz}
while IFS='|' read -r fx out cfg; do
  [ -s "$out/results.jsonl" ] && grep -q '^PASS' "$out/run.log" 2>/dev/null && continue
  printf '%s\0%s\0%s\0' "$fx" "$out" "$cfg"
done < "$1" | xargs -0 -n3 -P "${2:-12}" "$R/run_replay.sh"
