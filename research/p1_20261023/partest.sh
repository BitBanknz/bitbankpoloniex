#!/bin/bash
# usage: partest.sh <BIN> <fixture> <refdir> <outdir> [TestName]   runs config from refdir, compares results/curves/run.log fee lines
set -uo pipefail
BIN=$1 FX=$2 REF=$3 OUT=$4 TN=${5:-TestSpikeKFoldReplay}
mkdir -p $OUT; export TMPDIR=$(mktemp -d -p /dev/shm p1par.XXXXXX)
CFG=$(cat $REF/config.json)
/usr/bin/time -f "%e wall %U user %S sys %M KB" -o $OUT/time.txt env GOMAXPROCS=${GOMAXPROCS:-1} GOGC=${GOGC:-400} LK_FIXTURE=$FX LK_MARKETS=${MARKETS:-/vfast/data/code/bitbankpoloniex/data/frontier_20260912/ledger/markets.json} LK_BOOKS=${BOOKS:-/vfast/data/trading_research_20261009/fidelity/book_snapshots.json.gz} LK_CONFIG="$CFG" LK_OUT=$OUT/results.jsonl LK_CURVES=$OUT/curves.csv $BIN -test.run $TN -test.count=1 -test.timeout 8h -test.v 2>&1 | grep -E '^(fee=|---|ok|FAIL|panic|PASS)' > $OUT/run.log
rm -rf $TMPDIR
r=PARITY_OK; for f in results.jsonl curves.csv; do cmp -s $OUT/$f $REF/$f || r=PARITY_FAIL; done
cmp -s <(grep ^fee= $OUT/run.log) <(grep ^fee= $REF/run.log) || r="$r runlog_diff"
echo "$OUT $r $(cat $OUT/time.txt)"
