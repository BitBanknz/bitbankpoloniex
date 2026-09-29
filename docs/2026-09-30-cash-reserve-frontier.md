# Cash-reserve frontier for slot top-up: 0.2 and 0.3 not promoted

Single-parameter test on the frozen 2026-09-24 replay (`research/topup20260924/run.sh
<out> <reserve> 0.25 0.08`, identical fixture, halts 25%/8%, budget 495, order cap 49).
Legacy arm reproduces the recorded numbers exactly (+7.60 continuous, +1.12 28-day
mean at 30 bps), so the harness is unchanged. Reserve 0.4 rows are the deployed
profile from `2026-09-24-topup-realistic-cost.md`.

| geometry | fee bps | r0.4 (deployed) mean / worst / DD | r0.3 | r0.2 |
|---|---:|---|---|---|
| continuous | 30 | +13.14 / - / 15.5 | +19.29 / - / 20.5 | +18.51 / - / 22.6 |
| continuous | 40 | +7.25 / - / 15.8 | +6.83 / - / 20.9 | +0.06 / - / 23.0 |
| 28-day (9) | 30 | +2.74 / -12.7 / 14.3 | +2.90 / -17.4 / 19.0 | +3.36 / -19.1 / 20.8 |
| 28-day (9) | 40 | +2.05 / -13.1 / 14.6 | +2.61 / -17.9 / 19.4 | +3.03 / -19.6 / 21.3 |
| 56-day (5) | 30 | +5.99 / -8.4 / 15.5 | +5.88 / -13.2 / 20.5 | +6.76 / -13.4 / 22.6 |
| 56-day (5) | 40 | +4.85 / -10.7 / 15.8 | +5.47 / -13.8 / 20.9 | +6.04 / -15.0 / 23.0 |

All drawdowns are inside the 30-35% budget, but the sizing increase is not a
dominance win: worst 28-day fold falls faster than the mean rises (-12.7 to -19.1
for +0.6 mean at 30 bps), the doubled-cost continuous cell reverses at r0.2
(+0.06 vs +7.25), and positive 28-day folds drop from 7/9 to 6/9. Positions are also
order-cap limited (49 USDT per order, 12 orders/day), so extra reserve release
does not scale linearly. Live remains reserve 0.4; no unit or binary changed.
