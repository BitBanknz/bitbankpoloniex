# Live shadow comparison: live decisions vs the Go engine behind mock HTTP — 2026-10-11

Read-only. Live units, state, credentials untouched. Prod files were copied to
`/nvme0n1-disk/code/poloniexmojo/shadow/20261011` and locally to `/vfast/data/trading_research_20261011/shadow/inputs`.

## Method

- Engine: the live source `f3aa665` (binary 6b10fdb6) built as a research test binary (`prepare_go.py`: replay clock,
  loopback-only client, skip hook that records every rejected order build). The pre-10-08 release source
  `4cc91224` builds through the same harness (`--variant old`).
- Mock HTTP (`shadow_replay_test.go.txt`): `/markets`, `/markets/ticker24h`, `/prediction`, `/markets/{s}/orderBook`
  served in-process; any write or private endpoint fails the run. Ledger seeded from a real live `state.json`.
- Config = the live unit argv of each period, parsed by `shadow.py argv_config`. Unknown flags fail closed;
  `--enable-live-orders`, `--env`, `--predictions`, `--state` are live-only and not simulated.
- Signals: the forecasts actually served. 09-24..10-03 from the loopback `rotation-signals` responses captured by the
  public recorder, 10-01..10-10 from the daily forecast collector/snapshots; only 09-14..09-23 use the causal s2510 EMA
  reconstruction (max abs error vs served 4.5e-4, identical top-3).
- Arms (clock / book): `hourly_proxy` (one cycle per hour, 60 in 01:00, open ±5 bps, depth 10% prior-hour turnover),
  `hourly_archive` (10-09 fidelity model: archived 5-level shapes, follow cycles), `minute_archive` (a cycle every
  minute at the 1m-candle open), `minute_recorded` (minute clock plus the verbatim `orderBook?limit=5` and
  `ticker24h` responses recorded each minute 09-24 01:56..09-26 20:32 and 09-27..10-03 21:11; archive fallback elsewhere).
  Archive arms use book seeds 1-3. Sim fee 14 bps (measured); the then-configured 30 bps is a sensitivity cell.
- Two comparisons. Full window: one replay from the window-start ledger (path dependent). Daily re-seeded: each UTC day
  starts from the live ledger reconstructed from the start snapshot plus live fills (engine accounting incl. TRX fee
  deductions, cooldowns, dust; peaks from recorded best bids, else 1m open times the median archived bid offset).
  Reconstruction matches the end snapshot exactly for cash and quantities in every window; peaks within 0.4%.
- Agreement unit: (UTC day, symbol, side) groups; agree = both sides traded and notional within 10%.

## Windows and live config

| window | live binaries | argv delta |
|---|---|---|
| w0 09-14 11:00 → 09-23 15:00 | c5d03648, 2c2c81c4 (09-15), fbefa17a top-up profile 09-18 00:52 for ~1 h, eb9a2d10 dust fix (09-18) | cooldown 120, no top-up, legacy halts |
| w2 09-23 16:00 → 10-08 14:00 | eb9a2d10, 4cc91224 (09-30 10:13) | + top-up, reserve 0.4, halts 25/8 |
| w1 10-08 15:00 → 10-10 11:00 | 6b10fdb6 = f3aa665 | + fee 0.0014, min-exit 24.5, exit ramp 20 |

`f3aa665` with legacy flags equals `4cc91224` byte-for-byte on w2 (hourly proxy and minute archive, both fees).

## Results (fee 14 bps)

Daily re-seeded (no cascade):

| window | arm | agreement | live-only / sim-only / size | sum of daily PnL gap, sim − live |
|---|---|---:|---|---:|
| w1 (current) | all arms | 100% (1/1 per seed) | 0 / 0 / 0 | −0.10..+0.07% (2 d) |
| w2 | hourly_proxy | 56.5% (13/23) | 1 / 3 / 6 | −1.75% (−356 bps/mo) |
| w2 | hourly_archive | 47.7% (31/65) | 4 / 5 / 25 | −1.57% [−2.31, −0.81] |
| w2 | minute_archive | 52.3% (34/65) | 4 / 5 / 22 | −1.85% [−2.87, −1.18] |
| w2 | minute_recorded | 59.1% (39/66) | 5 / 6 / 16 | −1.45% [−1.57, −1.25] (−296 bps/mo) |
| w0 | hourly_proxy | 33.3% (2/6) | 1 / 3 / 0 | +0.51% |

Full window from the start snapshot (path dependent): w2 hourly_proxy 26.1% (6/23), gap −1.12% (−229 bps/mo; −1.44% at
30 bps) — reproduces the 10-09 drift report (26.1%) with a different harness. Archive/recorded arms 11–44% by seed,
gap −0.36..−1.96%. w0 25%, w1 100%.

w2 daily PnL gap comes from three days: 09-26 (−0.8%, sim rotated ZEC out at 01:12 before its rally, live kept it),
09-24 (−0.3..−1.0%) and 09-28 (−0.5%). All other days are within ±0.2%.

## Mismatch classification (w2 minute_recorded, daily)

| class | cases |
|---|---|
| sub-minute book / spread gate (recorder and live cycle read the book seconds apart; ZEC/PEPE/SUI spreads 50–110 bps sit on the 30 bps gate) | 09-26 ZEC rotation exit sim-only; 09-28 symbol swap (live ETH passed the gate at 01:04 while BNB failed, sim the reverse at 01:05); 09-28 PEPE exit 22.9 vs 27.7; 10-03 SUI entry 48.3 at 01:14 live vs 5.5 at 01:38 sim (59/60 recorded minutes fail the gate) |
| legacy hourly stop key (pre-ramp binary) on a knife edge | 09-24 ZEC stop: same minute (10:38) and price (1455.12) as live, clip 1.02 vs 1.14; sim re-stops at 11:01 with the bid 0.04% under the stop, live did not |
| book model where no recording exists | 09-24 01:00 window (recorder started 01:56): BNB exit and PEPE entry sizes by archive seed |
| stop trigger timing (peak / bid model) | 09-29 PEPE protective exit 01:53 sim vs 02:20 live; 10-07 SUI stop 15:0x sim vs 11:33 live (no recording) |
| config/binary drift, not simulator | w0: pre-dust-fix binaries let a 0.00000091 ETH residual hold a slot (sim buys BNB 09-16..18, live cannot); 09-18 00:52 one-hour top-up deploy placed the live-only TRX 48.89 top-up |
| fees | live 14.0 bps median paid in TRX (deducted from the TRX holding); sim charges 14 bps in USDT; < 0.05% of equity |
| signal timing / data gaps | none: served ranks equal the fixture every day; 1m and 1h candles complete |

Minute clock alone does not raise agreement (52% vs 57% hourly proxy) because archive book shapes inject spread-gate
noise; real recorded books do (59%). The dominant residual is unobservable sub-minute book state at the live cycle
second. Recommendation: have live record the book it acted on (and the rejected-build reason) per cycle; the harness
already accepts per-minute recorded books.

## Current binary (w1)

One live decision since 10-08 14:50: BNB stop 16:48–16:49 under the ramp, two clips 48.93 + 42.32 USDT, flat. Every
arm reproduces it (48.91 + 42.0..42.6 USDT); trigger minute 16:07..17:00 depending on the bid model. No entries on
10-09/10-10 in live or sim: served top-3 = TRX (held, top-up gap 3.5 < 12.25 USDT), BNB (cooldown to 10-13), SUI
(cooldown to 10-12). About 80% of equity sits in cash by design (cooldown on top-ranked names, no rank-4 fallback).
Live journal shows `cycle complete` in the 00:05–01:59 forecast window and the expected paused message otherwise.

## Live findings (nothing changed)

- Latent wedge (bug-fix candidate, not yet triggered): fees are paid in TRX and booked against the `TRX_USDT`
  rotation holding (`Fill.Fee` = 0). If that holding leaves the ledger (stop, rotation exit or dust drop) while the
  account still pays fees in TRX, reconciliation returns `third-currency fee requires operator accounting` and the
  pending order blocks all new orders, protective exits included. Needs a check of Poloniex fee-asset behaviour at a
  near-zero TRX balance; fix = book an untracked third-currency fee as a USDT cost at the mark, or keep a TRX fee reserve
  outside the rotation slot.
- Reporting: `Fill.Fee` is 0 for TRX-paid fees, so ledger fee totals understate cost (TRX quantity absorbs it).
- No discrepancy between live and the simulator attributable to the f3aa665 safeguard code.

## Mojo port

`poloniexmojo` `pm` fidelity mode (fork A) replays flat-start folds on the hourly clock only; it has no seeded-ledger,
minute-clock or recorded-book input, so these windows were not run through it.

## Reproduce

```
R=research/shadow20261011; export SHADOW_WORK=/vfast/data/trading_research_20261011/shadow
python3 -I $R/prepare_go.py --src . --variant new --out $SHADOW_WORK/build-new
python3 -I $R/prepare_go.py --src /vfast/data/code/bitbankpoloniex/data/longkfold20261007/release_source --variant old --out $SHADOW_WORK/build-old
python3 -I $R/shadow.py fixtures
for w in w0 w2 w1; do for a in hourly_proxy hourly_archive minute_archive; do python3 -I $R/shadow.py run $w $a; done; done
python3 -I $R/shadow.py run w2 minute_recorded
python3 -I $R/shadow.py daily w2 hourly_proxy,hourly_archive,minute_archive,minute_recorded
python3 -I $R/shadow.py compare; python3 -I $R/shadow.py daily-compare
```

Inputs: candles from `research/liveparity20261008/fetch_candles.py` (09-14..10-10); recorded books from
`extract_recorded_books.py` run on prod over `data/public_retention_2026092{4,7}_v1` (books, ticker24h and served
ranks; merged into `recorded_books.json.gz` and `recorded_served_ranks.json`); archived book shapes `/vfast/data/trading_research_20261009/fidelity/book_snapshots.json.gz`.
Results: `$SHADOW_WORK/report.json`, `$SHADOW_WORK/daily_report.json`.
