#!/bin/bash
# usage: run_exit.sh <out-dir> <stop> <minhold> <regime>  (slots 3, cooldown 120, reserve 0.4, halts 25/8)
set -euo pipefail
cd "$(dirname "$0")/../.."
export CC=gcc GOMAXPROCS=2
OUT=$1
data/ranker/venv/bin/python research/sweep20260930/prepare_exit.py --out "$OUT" --slots 3 --cooldown 120 --reserve 0.4 --halt-peak 0.25 --halt-daily 0.08 --stop "$2" --minhold "$3" --regime "$4" --geometries 0 28 56
POLONIEX_LEDGER_FIXTURE=${FIXTURE:-$PWD/data/frontier_20260912/ledger/fixture.json} POLONIEX_LEDGER_MARKETS=$PWD/data/frontier_20260912/ledger/markets.json POLONIEX_LEDGER_OUT=$OUT/results.jsonl \
  go test -overlay "$OUT/overlay.json" -run TestFrozenLedgerReplay -count=1 -timeout 3h ./internal/bot/ -v 2>&1 | grep -E '^(days=|---|ok|FAIL|panic)' > "$OUT/run.log"
