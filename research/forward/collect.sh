#!/bin/bash
# Append the production forecast state and trailing hourly history (read-only ssh) so the replay fixture can be
# extended with genuinely unseen days. usage: collect.sh [outdir]
set -euo pipefail
OUT=${1:-$(dirname "$0")/../../data/forward}; mkdir -p "$OUT"
R=administrator@93.127.141.100; D=/nvme0n1-disk/code/bitbankgo/data/rotation/state
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=20 $R "cat $D/forecast.json" > "$OUT/forecast_$STAMP.json"
python3 - "$OUT" "$STAMP" <<'PY'
import json, sys
out, stamp = sys.argv[1:]
f = json.load(open(f'{out}/forecast_{stamp}.json'))
row = dict(issued_hour=f['issued_hour'], pairs=f['pairs'], raw_scores=f['raw_scores'], smoothed_scores=f['smoothed_scores'], observations=f['observations'], collected=stamp)
with open(f'{out}/scores.jsonl', 'a') as fh: fh.write(json.dumps(row) + '\n')
PY
rm "$OUT/forecast_$STAMP.json"
ssh -o BatchMode=yes -o StrictHostKeyChecking=no -o ConnectTimeout=20 $R "cat $D/history.json" | gzip -9 > "$OUT/history_$STAMP.json.gz"
