# Slot top-up sizing and wider risk halts — 18 September 2026

Owner decision 2026-09-18: 30–40% drawdown is acceptable fleet-wide; push
validated PnL. The live ledger was ~12% invested by construction: each BUY is
one order of at most `min(max-order, 10% of budget)` and a held symbol is never
bought again, so three slots could hold at most 147 of 495 USDT, and with the
40% reserve the book sat at ~61 USDT invested with 437 USDT cash.

## Change

`--slot-top-up` adds further capped orders to a held, non-imported rotation
target until its marked notional reaches `budget × (1 − reserve) / slots`
(decision keys `|topup-N`, still under the 12-orders/day cap, per-order cap and
10% visible-depth cap). `--cash-reserve` makes the 40% reserve explicit.
`--halt-peak-dd` / `--halt-daily-loss` make the latched risk halts
configurable (legacy 10% / 3%). With the legacy halts a ~60%-invested book
tripped the daily halt on 2026-01-31 in replay and then sat in cash for seven
months, so the top-up profile runs 25% / 8%. Unit tests: `internal/bot/topup_test.go`.

## Frozen replay (actual Engine, loopback fixture `data/frontier_20260912/ledger`, 2026-01-14 → 09-07, 12 cycles inside the 01:00 hour for both arms)

Rule fixed before running: top-up must beat the legacy arm's mean at 30 and
60 bps per side on continuous, 28-day and 56-day geometries without fewer
positive folds. Legacy = deployed flags (budget 495, order 49, 3 slots, 120 h
cooldown, 40% reserve, 10%/3% halts).

| geometry | fee | legacy mean / worst / max DD / positive | top-up r0.4 halts 25/8 | top-up r0.2 halts 25/8 |
|---|---:|---|---|---|
| continuous | 30 | −2.79 / — / 9.0 | **+6.65** / — / 15.5 | +18.51 / — / 22.6 |
| continuous | 60 | −4.47 / — / 9.6 | **+4.19** / — / 16.4 | −3.31 / — / 23.9 |
| 28-day (9) | 30 | +0.99 / −7.3 / 8.2 / 7 | **+2.15** / −12.7 / 14.3 / 7 | +3.36 / −19.1 / 20.9 / 6 |
| 28-day (9) | 60 | +0.64 / −8.0 / 8.8 / 7 | **+2.33** / −13.8 / 15.2 / 7 | +2.34 / −20.6 / 22.2 / 6 |
| 56-day (5) | 30 | +0.93 / −5.2 / 9.0 / 3 | **+5.18** / −8.4 / 15.5 / 3 | pending |
| 56-day (5) | 60 | +0.38 / −6.4 / 9.6 / 3 | **+5.40** / −9.9 / 16.4 / 3 | pending |

Reserve 0.4 passes every cell; reserve 0.2 fails the doubled-cost continuous
cell (churn: 308 fills vs 214) and loses a positive fold, so it is not
promoted. Fills are modelled at the fixture's open ±5 bps with 10% of prior
turnover as depth; these are the same assumptions as the 2026-09-14 cooldown
validation and remain optimistic about real IOC fills.

## Deployment (remote host, 2026-09-18 00:52 UTC)

Static binary `fbefa17a4e333586594bc4fb63f6e5d4668a2ee7f817e0e20d28151517548513`
(source `c75c6de`) replaced `2c2c81c4…` (retained as
`bin/bitbankpoloniex.before-topup-20260915`-style backup
`bin/bitbankpoloniex.before-topup-20260918`). Unit flags added:
`--slot-top-up --cash-reserve 0.4 --halt-peak-dd 0.25 --halt-daily-loss 0.08`.
Ledger snapshots before stop and at stop are in `data/topup_20260918/` on the
host; cash 436.83, 4 holdings, 16 fills, no halt, no pending intent. Paper
units share the binary and keep default (legacy) behaviour. Rollback: stop,
restore the backup binary and the previous unit, start.
