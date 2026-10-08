#!/bin/bash
# usage: queue.sh <jobs.txt> <parallel>   lines: fixture|outdir|config-json ; skips outdirs with a complete run.log
R=$(dirname "$(readlink -f "$0")")
grep -v '^#' "$1" | while IFS='|' read -r fx out cfg; do
  [ -s "$out/run.log" ] && tail -1 "$out/run.log" | grep -q PASS && continue
  printf '%s\0%s\0%s\0' "$fx" "$out" "$cfg"
done | xargs -0 -n3 -P "${2:-8}" nice -n 5 "$R/run_replay.sh"
