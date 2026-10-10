# Fee-asset / dust deltas never block protective exits (live 6f4efd98, 2026-10-10 14:14Z)

## Poloniex fee behaviour (docs + live fills)

- API docs (`/orders/{id}/trades`) only define `feeCurrency`/`feeAmount`; no charging rule is documented.
- Live account, 54 fills: before any TRX was held, SELL fees were USDT (quote) and BUY fees base. From 09-11 01:13
  (first TRX buy) the account's TRX fee discount charges fees in TRX from the free TRX balance on 61/63 trades, both
  sides, any symbol (~14 bps of notional valued at TRX). Exceptions: two 09-11 XRP buy trades charged XRP.
- Account TRX on 10-10 = ledger `TRX_USDT` exactly (281.066974282201607047): every TRX fee came out of the rotation
  holding. Behaviour at a near-zero TRX balance is undocumented; assumed: TRX when sufficient, else quote/base.

## Failure (reproduced, `feedust_test.go`, mock exchange)

On `f3aa665`, a filled IOC whose accounting failed returned an error from `resolve`, kept `Pending`, and every later
cycle returned before exits: all orders blocked, stops included.

| test | trigger | old result |
|---|---|---|
| `TestUntrackedTRXFeeDoesNotBlockStops` | fee in TRX after TRX left the ledger (exit or dust drop) while TRX remains on the account | `third-currency fee requires operator accounting`, stop never placed |
| `TestTRXExitFeeFromUntrackedRemainder` | selling the full tracked TRX while the fee is drawn from untracked TRX (qty+fee > tracked) | `fill exceeds tracked holdings`, stop never placed |
| `TestFreeBalanceShortfallClampsAndContinues` | free balance a fee short of the ledger | `tracked holdings exceed free exchange balance` aborted the cycle before later stops |

## Fix (`730408a`)

- `resolve` never errors on accounting of a terminal order: third-currency fees drain the tracked holding then record
  the rest as `untracked_fee`; base fee beyond the tracked quantity on a sell is recorded, holding closed; cash below
  zero is clamped. Deltas go to `data/live/reconcile.jsonl` (state.json schema unchanged, so 6b10fdb6 still reads it).
- SELL preflight: free < order qty reconciles the holding to the free balance and sells that; free below dust closes it.
- Material deltas (shortfall > dust notional and > 1%, sell beyond tracked, cash short > 1 USDT) latch
  `accounting delta beyond fee tolerance; protective exits only; operator review required`. Like the risk halt it
  stops entries and keeps stops running; it does not overwrite an existing halt.
- An exit error no longer aborts later exits unless an intent is pending (uncertain submission); entries are skipped
  that cycle. Remaining blocks: transport errors / non-terminal / identity mismatch on a pending IOC (transient).

## Parity

Paper/replay paths unchanged: the 10-09 fidelity harness rebuilt from the patched engine reproduces all 79 stress cases
byte-identically (results + curves), which `pm` (Mojo, `20261011-f3aa665-59b0b1ef`) already matches. Mojo has no live
order/fee-asset path, so no Mojo change; noted in `poloniexmojo/docs/2026-10-11-f3aa665-parity.md`.

## Deploy record

- Source: `release/live-6b10fdb6` + `730408a` = branch `fix/fee-dust-20261011`, tag `live-6f4efd98`.
- `deploy/release/build-live.sh` (go1.25.0, trimpath, no VCS) -> sha256
  `6f4efd98973089fc3b5ef4f84d9e6d503906e1481255ea6e03548ae6718ffc1d`, identical locally, from `git archive`, and on prod
  (`releases/20261011-730408a/`).
- 14:14:12Z: Pending null, outside 01:00-02:00; old binary backed up to `bin/bitbankpoloniex.6b10fdb6-before-730408a`,
  state to `data/live/state.json.pre-730408a`; stop, atomic replace, start. Argv/unit unchanged.
- Verified: new binary `status` reads the live ledger; cycles every minute after restart (LastCycle 14:24Z), holdings
  (TRX 281.066974282201607047), cash 391.37810489427, fills, Halted empty, Pending null all unchanged; no reconcile
  deltas. First trading window with the new binary: 10-11 01:00Z.

## Rollback

```
cd /nvme0n1-disk/code/bitbank-poloniex
python3 -c 'import json;print(json.load(open("data/live/state.json"))["Pending"])'   # must be None
sudo systemctl stop bitbankpoloniex-live
cp -p bin/bitbankpoloniex.6b10fdb6-before-730408a bin/.b && mv -f bin/.b bin/bitbankpoloniex
sha256sum bin/bitbankpoloniex   # 6b10fdb6...
sudo systemctl start bitbankpoloniex-live
```

If the new binary latched the accounting halt, 6b10fdb6 treats it as a hard halt: clear `Halted` after review first.
