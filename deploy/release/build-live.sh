#!/usr/bin/env bash
set -euo pipefail
want=6b10fdb6eea0ab795446668dc47b61b08312b88792b4094161b9cf5ce4913eb2
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${1:-$root/bin/bitbankpoloniex}
cd "$root"
GOTOOLCHAIN=go1.25.0 GOFLAGS= CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 \
  go build -buildvcs=false -trimpath -o "$out" ./cmd/bitbankpoloniex
got=$(sha256sum "$out" | cut -d' ' -f1)
echo "$got $out"
[ "$got" = "$want" ] || { echo "sha mismatch: tree differs from f3aa665 or toolchain differs" >&2; exit 1; }
