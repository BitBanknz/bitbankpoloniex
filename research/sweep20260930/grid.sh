#!/bin/bash
# usage: grid.sh <root> <parallel> ; stage-1 full factorial, halts fixed 0.25/0.08
cd "$(dirname "$0")/../.."
ROOT=$(realpath -m "$1"); P=${2:-8}; mkdir -p "$ROOT"
for s in 3 2 4; do for c in 120 72 168; do for r in 0.4 0.3 0.5; do
  echo "s${s}_c${c}_r${r}_h25_8 $s $c $r 0.25 0.08"
done; done; done | xargs -P "$P" -L1 bash -c 'n=$0; [ -f '"$ROOT"'/$n/run.log ] && grep -q "^ok" '"$ROOT"'/$n/run.log && exit 0; rm -rf '"$ROOT"'/$n; research/sweep20260930/run.sh '"$ROOT"'/$n "$@"'
