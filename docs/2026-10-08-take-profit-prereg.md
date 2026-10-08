# Take-profit and armed trail — pre-registration, 2026-10-08

Written and committed before any grid cell is run. Research only; nothing deployed, prod host untouched.

## Hypothesis (imported from binancego)

binancego `docs/2026-10-08-dd-feasible-frontier.md` (main f770d09, deployed there 2026-10-08): a fixed
take-profit at entry × (1 + 3500 bps) raised its 24-fold mean 3.48 → 5.64 on 10/10 seeds and cut worst
monthly DD 51 → 30.8 by selling parabolic pumps before the give-back; 3000/4000 neighbours passed, 2000 and
6000+ were worse, an armed trail (arm 20 %, trail 10 %) was runner-up. The Poloniex book is dominated by one
such pump (ZEC 2025-09-24 fold, +40.6 %), so a take-profit could either bank give-backs or cut the jackpot.

Not repeated: plain trailing-stop widths 0.85/0.93/0.95 and min-hold (10-02), rank hysteresis (10-08),
the 10-08 knob grid. The deployed 10 % peak stop stays in every arm.

## Engine, data, costs (identical to `2026-10-08-knob-grid-measured-cost-prereg.md`)

- Engine: deployed release source, research build `research/tp20261008/prepare_go.py` = the knob-grid build
  plus main's new `internal/bot/exits.go` copied verbatim and wired at the same points as main. Parity: the
  deployed config (TP and arm off) at fees 0.0014/0.0033 must reproduce the knob grid's
  `s3_h72_c120_r0.4` (and `_xzec`) `results.jsonl` and `curves.csv` byte-for-byte.
- 42 e2306 refit folds 2023-08-02 → 2026-10-06, 8 pairs and ex-ZEC, fees 0.0014 (19 bps/side, measured) and
  0.0033 (38 bps, 2×). Goodness = fleet `goodness.py`, `--dd-limit 35`.

## Mechanism (main `internal/bot/exits.go`, flags `--take-profit`, `--trail-arm`, `--trail-arm-stop`, default off)

- **Take-profit x:** each hourly cycle, a holding whose bid ≥ (1 + x) × its average entry price is sold as a
  protective exit (inside the 72 h minimum hold, priority over rotation, no top-up while exiting). The exit
  latches until flat, as a filled resting order would; sells use the existing 49 USDT order cap (≈ 3 hourly
  orders per slot). The post-sale 120 h cooldown applies as after any sale. Fill = hourly-open proxy bid as
  a taker, i.e. no wick fills (conservative vs binancego's maker limit).
- **Armed trail a/s:** once the peak bid ≥ (1 + a) × entry, the stop level is max(0.9 × peak, (1 − s) × peak).
- Entry prices are recorded only while one of these is configured, so the state file and every decision are
  unchanged when off.

## Grid (11 configs × 2 universes × 2 costs)

| arm | values |
|---|---|
| D | deployed (both off) |
| take-profit | 1000, 1500, 2000, 3000, 3500, 4000, 5000 bps |
| armed trail | arm 1000, 2000, 3000 bps, stop 500 bps |

Scaling: binancego's ladder {2000..5000} is kept in full; 1000 and 1500 are added below because these are
unlevered spot positions in 8 mostly large-cap pairs, whose 72 h+ moves are smaller than binancego's levered
alts. binancego's arm 20 %/trail 10 % equals the always-on 10 % stop here, so the trail variant tightens to
5 % once armed, with arm neighbours 10 %/30 %.

## Pass rule (the knob-grid rule, unchanged; primary cost 19 bps)

1. Mean %/fold (8 pairs) > D. 2. Ex-ZEC mean > D. 3. Goodness > D in both universes.
4. Max calendar-month DD ≤ 35 and goodness PASS in all four cells.
5. Paired fold wins ≥ 21/42 in both universes and worst fold ≥ D's worst − 2 pp (8 pairs).
6. 2× cost: mean, ex-ZEC mean and goodness (8 pairs) > D at 38 bps.
7. Plateau: every tested one-step neighbour on the same ladder (D excluded) beats D on rules 1 and 2;
   the ladder ends have one neighbour.
8. Older (2023-08 → 2025-02) and newer (2025-03 → 2026-09) 21-fold paired mean differences > 0 in both universes.

Pick (if several pass): largest minimum paired mean difference across {8 pairs, ex-ZEC} × {19, 38 bps}.
If none passes, the deployed profile stays. Promotion would still need a forward check (folds already
examined 10-07/10-08; 10 configs compared).
