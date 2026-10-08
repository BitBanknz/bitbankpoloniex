# Sim/live fidelity: measured fee, archived-book depth, exit follow-through — 2026-10-09

Source: fleet drift report (`~/code/dashboard-finance/docs/2026-10-09-sim-live-drift.md`, commit 0909c0e):
Poloniex 14 d, decision agreement 26 %, gap −307 bps/month. Research and code only; prod untouched
(deploy plan at the end, not executed).

## (a) Findings confirmed from the synced live ledger (`data/liveparity_20261008/prod/live/state.json`)

- **Thin-book stop.** 2026-09-24 10:38Z the ZEC 10 % stop sold 0.000782 ZEC = **1.14 USDT** of a ~81 USDT
  holding. Order quantity == filled quantity, so it was not a partial IOC: `BuildOrder` sized it at 10 % of
  the depth within 0.1 % of the bid. The stop key is once per symbol per hour and is not latched, ZEC
  bounced, and the rest left via 49-USDT-capped rotation exits on 09-25, 09-27 and 09-28. Same pattern on
  2026-10-07: the SUI stop took 5 clips over 3.5 h (48.9, 6.4, 5.6, 3.1, 28.0 USDT).
- **Fee.** 52 live fills since 09-10: median **14.0 bps**, notional-weighted 15.1 bps (TRX fees at
  0.335 USDT), against 30 bps in sim, paper and the `Validate` floor.
- **Book depth** (archived recorder books, 27,867 5-level snapshots for 8 pairs, 09-24..09-27, extracted by
  `book_snapshots.py`). Depth within 0.1 % of the touch ÷ prior-hour turnover has a median of
  **≈0.002 bid / 0.0015 ask**. The proxy assumes 0.1, about 50× more. Median spreads are 31/32/4/52/109/13/17/58 bps
  for BNB/ETC/ETH/PEPE/SUI/TRX/XRP/ZEC, against the proxy's 10 bps. Only 11–48 % of minutes pass the
  30 bps spread gate for SUI/PEPE/ZEC/BNB/ETC, which explains the late live entries.

## (b) Cost fix

- `DefaultConfig().FeeRate` = `MeasuredFeeRate` 0.0014, `Validate` floor 0.003 → 0.0005, new
  `--fee-rate` flag. The standard paper ledger (same binary) now charges 14 bps. Paper fills
  price at the visible touch, so they pay the real spread.
- Paper fills are capped at the visible in-band depth (IOC semantics); the cap survives crash recovery
  (`Pending.Fillable`). The cap is inert under legacy sizing (≤10 % of depth).
- The research harness uses the measured fee and draws real book shapes (below), so the spread comes from
  the book and is no longer a flat 5 bps.
- Fallback-model `RoundTripCost` (0.006) is a model-acceptance gate, not the simulator, and is unchanged.

## (c) Depth model and live safeguard

**Sim.** `research/fidelity20261009/replay_test.go.txt` adds `Book: "archive"`. For each (minute, symbol, seed)
it deterministically draws a real archived 5-level book shape, scales the level USDT by the mean hourly
turnover of the prior 24 h, and centres it on the hour open. It runs 60 cycles in the 01:00 window like
live, plus minute cycles in any hour where a holding is at or below its stop or latched. Live also runs
every minute, so legacy stops retry too. Fold-end liquidation uses the median archived bid offset.
Parity: `Book: "proxy"` reproduces the 10-08 knob-grid incumbent `curves.csv` byte-for-byte.

**Live** (default off; enabled in the live unit):
- `--min-exit-usdt 24.5`: every sell is raised to at least 24.5 USDT, or the whole holding if smaller.
  It is still a LIMIT IOC at the in-band price, so it only takes what is there and never sells below the band.
- `--exit-ramp-minutes 20`: a triggered stop latches (`Exiting: "stop"`, `ExitSince`) and is re-sent once
  per minute (key `|protect-<minute>`, no order-count suffix) until flat, even if the bid recovers. Over
  20 min the limit band widens from 0.1 % to 1 % below the bid and participation from 10 % to 100 % of
  in-band depth. The spread gate widens with the band. Up to 12 protective orders beyond `MaxOrdersDay` are
  allowed. A latched holding is never topped up. Switching the flag off clears the latch. Never a market order.

## (d) Corrected 42-fold baseline (e2306 folds, 3 book seeds, `results.md`)

| profile | 8 pairs mean %/fold | ex-ZEC | worst (8p) | goodness 8p / xZEC | cal DD |
|---|---|---|---|---|---|
| old proxy book, 19 bps (10-08) | +2.60 | +0.52 | −10.06 | −15.31 / −21.40 | 13.4 |
| **deployed, archive books, 14 bps (honest baseline)** | **+1.62** | **+0.39** | −12.45 | −19.26 / −21.99 | 13.1 |
| deployed + safeguard | +2.05 | +0.17 | −11.76 | −18.78 / −21.92 | 12.7 |

At 2× cost (33 bps) the deployed profile drops to +0.90 / −0.27 (safeguard +1.37 / −0.42). The safeguard
gains +0.43 pp/fold on 8 pairs (t 1.4) and loses 0.23 ex-ZEC (t −0.9). It improves the worst fold, goodness
and DD in both universes. It is a safety fix (stops that actually exit), not an alpha claim.

Neighbours (safeguard on, paired vs deployed): none beats the deployed point in both universes. On 8 pairs
the deployed point has the highest mean. Ex-ZEC, every neighbour is slightly ahead (cooldown 72: +0.46,
t 2.3, the known near miss from 09-30/10-08). Lower-exposure cells (cooldown 168, reserve 0.5, no top-up)
win goodness by holding less and lose mean, as on 10-08. **The deployed knobs stand.**

Limitations: 60 hours of archived books, reused for 2023–2026 and scaled by turnover; prices are static
within each hour; synthetic liquidity refreshes each minute; the folds were already examined on 10-07/10-08.
Keep the recorder running to widen the book sample.

## Reproduce

```
R=research/fidelity20261009; W=/vfast/data/trading_research_20261009/fidelity
python3 -I $R/book_snapshots.py $W /vfast/data/code/bitbankpoloniex/data/longkfold20261007/panel.npz
python3 -I $R/prepare_go.py --out $W/gobuild
python3 -I $R/grid.py $W/rp > $W/jobs.txt && BIN=$W/gobuild/replay.test GOMAXPROCS=1 $R/queue.sh $W/jobs.txt 12
python3 -I $R/evaluate.py $W/rp --md $R/results.md
```

## Prod deploy plan (not executed; run on the IP-allowed host)

```
# local: build from the pushed commit
git -C /vfast/data/wt/bbpx-fidelity rev-parse HEAD
cd /vfast/data/wt/bbpx-fidelity && CGO_ENABLED=0 go build -trimpath -o bin/bitbankpoloniex-fidelity ./cmd/bitbankpoloniex && sha256sum bin/bitbankpoloniex-fidelity
scp bin/bitbankpoloniex-fidelity deploy/remote/bitbankpoloniex-live.service administrator@93.127.141.100:/nvme0n1-disk/code/bitbank-poloniex/data/release-fidelity-20261009/
# remote
cd /nvme0n1-disk/code/bitbank-poloniex && R=data/release-fidelity-20261009
sha256sum $R/bitbankpoloniex-fidelity bin/bitbankpoloniex /etc/systemd/system/bitbankpoloniex-live.service   # binary must match local; old = 4cc91224...
$R/bitbankpoloniex-fidelity --command status --mode live --state data/live --budget 495 --max-order 49 --enable-live-orders | jq '.Pending'   # must be null
$R/bitbankpoloniex-fidelity --command doctor --mode live --state data/live --budget 495 --max-order 49 --enable-live-orders --env .env       # no open orders
sudo systemctl stop bitbankpoloniex-live.service && systemctl is-active bitbankpoloniex-live.service   # inactive
$R/bitbankpoloniex-fidelity --command status --mode live --state data/live --budget 495 --max-order 49 --enable-live-orders | jq '.Pending'   # re-check null
cp -a data/live $R/live.before && cp -a bin/bitbankpoloniex $R/bitbankpoloniex.before && sudo cp -a /etc/systemd/system/bitbankpoloniex-live.service $R/unit.before
install -m 0755 $R/bitbankpoloniex-fidelity bin/.bitbankpoloniex.new && mv -f bin/.bitbankpoloniex.new bin/bitbankpoloniex
sudo install -m 0644 $R/bitbankpoloniex-live.service /etc/systemd/system/bitbankpoloniex-live.service && sudo systemctl daemon-reload
cmp data/live/state.json $R/live.before/state.json && sudo systemctl start bitbankpoloniex-live.service
sudo journalctl -u bitbankpoloniex-live.service -n 30 -f    # >= 2 'cycle complete'/'cycle paused' lines, no errors
tr '\0' ' ' < /proc/$(systemctl show -p MainPID --value bitbankpoloniex-live.service)/cmdline   # shows --fee-rate 0.0014 --min-exit-usdt 24.5 --exit-ramp-minutes 20
# standard paper (same binary) picks up 14 bps on restart: sudo systemctl restart bitbankpoloniex-paper.service
# rollback: stop; check Pending null; install $R/bitbankpoloniex.before and $R/unit.before; daemon-reload; start (keep the current data/live, never restore the old ledger)
```

## Deployed 2026-10-08 14:50Z (prod leaf-gpu-dedicated-server)
Binary sha256 6b10fdb6... (CGO_ENABLED=0 -trimpath build of f3aa665) replaced 4cc91224; unit adds
`--fee-rate 0.0014 --min-exit-usdt 24.5 --exit-ramp-minutes 20`. Pre-checks: Pending null before and after stop,
no resting orders (IOC-only); state.json unchanged by the swap. Backups in
data/release-fidelity-20261009/{live.before,bitbankpoloniex.before,unit.before}.
