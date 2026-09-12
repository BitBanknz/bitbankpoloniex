# Poloniex production migration — 13 September 2026 NZ

The existing operator-enabled live trader was failing locally after repeated
`GET /margin/accountMargin HTTP 401` responses. It now runs as a system service
on `administrator@93.127.141.100`, in
`/nvme0n1-disk/code/bitbank-poloniex`, alongside both existing paper traders.

The user explicitly authorized this host and transfer of the Poloniex `.env`.
It was transferred over SSH, is owned by `administrator` with mode 0600, and is
loaded with the explicit `--env` argument. No credentials are committed here.
The deployment directory is mode 0700. Services run as `administrator`, with
`ProtectSystem=strict` and write access restricted to their data directory.

## Preserved operating configuration

| Unit | Mode and state | Limits / behavior |
|---|---|---|
| `bitbankpoloniex-live` | live; `data/live` | budget argument 495 USDT, maximum order 49 USDT, 3 slots, explicit live-order flag |
| `bitbankpoloniex-paper` | paper; `data/paper` | existing standard paper strategy, 3 slots |
| `bitbankpoloniex-account-paper` | paper; `data/account-paper-v2` | existing experimental fallback, 3 slots; cannot run live |
| `bitbankpoloniex-train.timer` | trains `data/paper` | daily 03:15 UTC plus up to 5 minutes jitter |

The account-backed live ledger retains its original imported budget field,
holdings, cash, high water, fills and processed decisions. The CLI budget did
not reset or recapitalize it. The live ledger had 3 holdings and 10 fills at
migration, with no pending intent or halt. Regular paper had 3 holdings / 5
fills; account paper had 4 holdings / 17 fills.

All local user traders and their training timer were stopped and disabled
before the final copy. All 12 state/model/lock files matched SHA-256 before the
first remote cycle. No ledger was initialized or edited. The remote services
and timer are enabled at boot. Existing unrelated services were preserved.

## Signals and validation

BitBank Go runs on this same host at port 8745. The remote units use
`http://127.0.0.1:8745/api/trading-bot/rotation-signals`, which the client already
permits for loopback access. This removes the external CDN dependency while
retaining every forecast receipt, timestamp and venue check.

Rank inference is scheduled at 00:05 UTC with a 01:05 retry. Entries from those
daily ranks are permitted only in the declared 01:00–02:00 UTC window. HTTP 503
and paused normal entries at 22:xx UTC during deployment were the expected
expired-forecast behavior, not an exchange authentication error. Minute-by-minute
position marking and protective stop checks continue. Stale ranks were not
reused and experimental fallback was not enabled for live trading.

The deployed executable is the previously tested protective-exit release from
source commit `193d466`:
`275563f00a62cbb43c53206b4c83904a1daf07715360da5665ef551ae791a1a2`.
This migration changes service location and signal transport, not its algorithm.
Systemd unit validation passed. Authenticated account, open-order, borrowing and
margin read checks passed remotely, and live/paper ledgers advanced on their
scheduled cycles. No synthetic order was submitted to test permissions; actual
order execution on this host awaits a qualifying strategy decision.

Private deployment evidence and original ledgers are retained under
`data/migration_20260913/` on both machines. To move trading again, stop and
disable the current host's services, copy the **latest** complete ledgers, then
start the destination. The old local snapshot must not replace newer fills or
pending intents. Service templates are in `deploy/remote/`.
