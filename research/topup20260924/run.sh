#!/bin/bash
# usage: run.sh <out-dir> <reserve> [halt-peak] [halt-daily]
set -euo pipefail
cd "$(dirname "$0")/../.."
export CC=gcc
OUT=$1; RES=$2; HP=${3:-0}; HD=${4:-0}
python3 research/topup20260924/prepare.py --out "$OUT" --reserve "$RES" --halt-peak "$HP" --halt-daily "$HD" --geometries 0 28 56
POLONIEX_LEDGER_FIXTURE=$PWD/data/frontier_20260912/ledger/fixture.json POLONIEX_LEDGER_MARKETS=$PWD/data/frontier_20260912/ledger/markets.json POLONIEX_LEDGER_OUT=$OUT/results.jsonl \
  go test -overlay "$OUT/overlay.json" -run TestFrozenLedgerReplay -count=1 -timeout 3h ./internal/bot/ -v 2>&1 | grep -E '^(days=|---|ok|FAIL|panic)' | tee "$OUT/run.log"
