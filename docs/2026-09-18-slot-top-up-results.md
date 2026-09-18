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

The first replay pass exposed a second defect: a rounded sell leaves a
sub-minimum residual (for example 0.0000884 XRP) that stays in `Holdings`,
counts as an active slot and can never be sold. The live ledger had two such
residuals, which is why it had placed no new entry since 2026-09-13. The
engine now drops residuals below the market minimum amount (at least 1 USDT)
from the ledger (`TestDustResidualDoesNotOccupySlot`). Both arms below include
that fix; the pre-fix legacy continuous result was −2.79% / −4.47%.

| geometry | fee | legacy + dust fix: mean / worst / max DD / positive | top-up r0.4, halts 25/8 |
|---|---:|---|---|
| continuous | 30 | **+7.60** / — / 9.0 | +13.14 / — / 15.5 |
| continuous | 60 | **+4.25** / — / 9.6 | −0.74 / — / 16.4 |
| 28-day (9) | 30 | +1.12 / −7.3 / 8.2 / 7 | +2.74 / −12.7 / 14.3 / 7 |
| 28-day (9) | 60 | +0.71 / −8.0 / 8.8 / 7 | +1.98 / −13.8 / 15.2 / 6 |
| 56-day (5) | 30 | +2.13 / −5.2 / 9.0 / 3 | +5.99 / −8.4 / 15.5 / 3 |
| 56-day (5) | 60 | +1.42 / −6.4 / 9.6 / 3 | +4.84 / −9.9 / 16.4 / 3 |

Top-up wins five of six mean cells but fails the doubled-cost continuous cell
(−0.74 vs +4.25, 208 vs 132 fills) and loses a positive fold at 28 days /
60 bps: the extra return is churn-sensitive. Under the fixed rule it is not
promoted. Reserve 0.2 (pre-dust-fix arms) was worse still at doubled cost
(continuous −3.31, 28-day worst −20.6, DD 22–24%). The legacy halts never
triggered in the legacy arm, so they stay at 10% / 3%. Fills are modelled at
the fixture's open ±5 bps with 10% of prior turnover as depth, the same
assumptions as the 2026-09-14 cooldown validation.

## Deployment (remote host)

00:52 UTC: the top-up profile was deployed first (binary `fbefa17a…`, source
`c75c6de`, flags `--slot-top-up --cash-reserve 0.4 --halt-peak-dd 0.25
--halt-daily-loss 0.08`); it placed one live top-up, TRX 48.89 USDT at 01:00
UTC, before the dust-fixed replay finished.

02:00 UTC: after the replay failed the rule, the service was restarted on the
dust-fix binary `eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`
(source `1ef4429`) with the original legacy flags. The first cycle dropped the
ETH and XRP residuals; the ledger now tracks TRX and ZEC with cash 387.94 and
one free slot. Snapshots before each stop are in `data/topup_20260918/` on
the host; the pre-change binary is `bin/bitbankpoloniex.before-topup-20260918`.
Paper units share the binary and gain only the dust fix. The top-up flags
remain available, default off, for a future retest once real fill costs are
measured from live fills.
