#!/usr/bin/env bash
set -euo pipefail
want=${WANT:-6f4efd98973089fc3b5ef4f84d9e6d503906e1481255ea6e03548ae6718ffc1d}
root=$(cd "$(dirname "$0")/../.." && pwd)
out=${1:-$root/bin/bitbankpoloniex}
cd "$root"
GOTOOLCHAIN=go1.25.0 GOFLAGS= CGO_ENABLED=0 GOOS=linux GOARCH=amd64 GOAMD64=v1 \
  go build -buildvcs=false -trimpath -o "$out" ./cmd/bitbankpoloniex
got=$(sha256sum "$out" | cut -d' ' -f1)
echo "$got $out"
[ "$got" = "$want" ] || { echo "sha mismatch: tree differs from the pinned release or toolchain differs" >&2; exit 1; }
