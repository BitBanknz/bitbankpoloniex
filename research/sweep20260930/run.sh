#!/bin/bash
# usage: run.sh <out-dir> <slots> <cooldown> <reserve> <halt-peak> <halt-daily>
set -euo pipefail
cd "$(dirname "$0")/../.."
export CC=gcc GOMAXPROCS=2
OUT=$1
python3 research/sweep20260930/prepare.py --out "$OUT" --slots "$2" --cooldown "$3" --reserve "$4" --halt-peak "$5" --halt-daily "$6" --geometries 0 28 56
POLONIEX_LEDGER_FIXTURE=$PWD/data/frontier_20260912/ledger/fixture.json POLONIEX_LEDGER_MARKETS=$PWD/data/frontier_20260912/ledger/markets.json POLONIEX_LEDGER_OUT=$OUT/results.jsonl \
  go test -overlay "$OUT/overlay.json" -run TestFrozenLedgerReplay -count=1 -timeout 3h ./internal/bot/ -v 2>&1 | grep -E '^(days=|---|ok|FAIL|panic)' > "$OUT/run.log"
