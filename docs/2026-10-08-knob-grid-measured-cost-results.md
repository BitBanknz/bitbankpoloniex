# Knob grid at measured cost — results, 2026-10-08

Pre-registered in `2026-10-08-knob-grid-measured-cost-prereg.md` (commit bf7ea61, before any cell ran).
Research only; nothing deployed, prod host untouched.

## Verdict

**No config passes; the deployed profile stays** (slots 3, 72 h hold, 120 h cooldown, reserve 0.4, top-up,
halts 25/8). The hypothesis is rejected: at the measured 19 bps/side the optimum has **not** moved toward
more trading. Every "more trading" cell (shorter hold, more slots, shorter cooldown, joint cube) loses the
8-pair mean and fleet goodness, and the cost effect is small: halving cost from 38 to 19 bps narrows a
more-trading cell's deficit by only ~0.1 pp/fold (cooldown 72: −0.48 → −0.39 pp), nowhere near a sign flip.
The deployed point is the best 8-pair goodness among all tradeable-utilization cells except the
lower-exposure ones (reserve 0.5, top-up off), which win goodness by holding less and lose mean.

## Setup

Engine = deployed release source (`research/knobs20261008/prepare_go.py`; adds inert Validate slot cap 5 and
the 69fc1f2 in-process transport to the 10-08 levers build). Parity: deployed config at fees 0.0014/0.003
reproduces `l1008/rp/inc_e2306` `results.jsonl` and `curves.csv` byte-for-byte. 42 e2306 refit folds
2023-08-02 → 2026-10-06, 8 pairs and ex-ZEC, fee 0.0014 (19 bps/side) and 0.0033 (38 bps = 2×). Goodness =
fleet `goodness.py`, dd-limit 35. 21 configs × 2 universes × 2 costs; no halt fired in any cell.

## Grid (`research/knobs20261008/grid_results.md`)

Columns: 19 bps mean %/fold / ex-ZEC mean / goodness / ex-ZEC goodness; worst fold (8 pairs, 19 bps); max
calendar-month DD over the 4 cells; paired fold wins vs D; 38 bps mean / ex-ZEC / goodness; paired mean
diff on older (2023-08..2025-02) / newer (2025-03..2026-09) 21 folds; rules failed.

| config | 19bps mean / xZEC / good / xZEC good | worst | calDD | wins 8p / xZEC | 38bps mean / xZEC / good | d old / new 8p | d old / new xZEC | fills | failed |
|---|---|---|---|---|---|---|---|---|---|
| **s3 h72 c120 r0.4 (D)** | +2.60 / +0.52 / −15.31 / −21.40 | −10.06 | 13.4 | — | +1.98 / −0.07 / −17.08 | — | — | 1497 | — |
| slots 1 | +0.74 / +0.70 / −21.44 / −21.54 | −16.90 | 17.0 | 20 / 27 | +0.25 / +0.23 / −22.77 | −0.09 / −3.64 | −0.32 / +0.69 | 857 | 1,3,5,6,7,8 |
| slots 2 | +0.28 / +0.38 / −21.44 / −20.93 | −15.08 | 16.5 | 17 / 23 | −0.32 / −0.21 / −23.28 | −1.48 / −3.15 | −0.38 / +0.11 | 1260 | all |
| slots 4 | +2.00 / +0.36 / −20.09 / −21.60 | −14.75 | 13.6 | 21 / 22 | +1.34 / −0.31 / −21.12 | +0.98 / −2.17 | +0.22 / −0.53 | 1843 | all |
| slots 5 | +1.12 / −0.04 / −17.60 / −20.70 | −11.80 | 11.5 | 18 / 19 | +0.49 / −0.62 / −19.38 | +0.12 / −3.08 | −0.81 / −0.31 | 1657 | all |
| hold 24 | +1.70 / +0.43 / −17.33 / −21.87 | −11.76 | 13.6 | 18 / 21 | +1.03 / −0.17 / −19.49 | +0.07 / −1.87 | −0.10 / −0.07 | 1556 | all |
| hold 48 | +1.56 / +0.26 / −17.57 / −22.05 | −11.76 | 13.5 | 15 / 21 | +0.89 / −0.34 / −19.71 | +0.21 / −2.30 | −0.44 / −0.07 | 1533 | all |
| hold 96 | +2.48 / +0.71 / −16.56 / −21.65 | −10.48 | 13.6 | 13 / 17 | +1.88 / +0.15 / −18.25 | −0.03 / −0.22 | +0.12 / +0.26 | 1420 | 1,3,5,6,7,8 |
| hold 120 | +2.36 / −0.07 / −16.93 / −22.48 | −10.89 | 13.7 | 14 / 17 | +1.77 / −0.57 / −18.62 | +0.12 / −0.61 | −0.81 / −0.36 | 1410 | all |
| cooldown 24 | +2.37 / +0.97 / −19.17 / −19.91 | −15.80 | 13.7 | 18 / 20 | +1.57 / +0.26 / −21.17 | −0.04 / −0.43 | +0.68 / +0.22 | 1722 | 1,3,5,6,7,8 |
| cooldown 72 | +2.22 / +1.11 / −18.36 / −20.10 | −14.56 | 13.7 | 18 / 20 | +1.49 / +0.45 / −20.13 | +0.54 / −1.31 | +0.98 / +0.21 | 1571 | 1,3,5,6,7,8 |
| cooldown 168 | +1.81 / +0.63 / −16.10 / −18.21 | −10.24 | 10.6 | 17 / 21 | +1.15 / +0.00 / −17.69 | −0.24 / −1.33 | −0.27 / +0.51 | 1413 | 1,3,5,6,7,8 |
| cooldown 240 | +1.18 / +0.08 / −17.67 / −18.66 | −10.25 | 10.8 | 11 / 16 | +0.57 / −0.50 / −19.03 | −0.66 / −2.17 | −0.87 / −0.01 | 1324 | all |
| reserve 0.2 | +2.63 / +0.68 / −21.10 / −26.78 | −14.71 | 17.3 | 21 / 20 | +1.73 / −0.10 / −23.27 | +0.46 / −0.41 | −0.19 / +0.51 | 2023 | 3,5,6,7,8 |
| reserve 0.3 | +2.34 / +0.43 / −20.87 / −24.54 | −16.45 | 15.6 | 19 / 18 | +1.71 / −0.28 / −20.20 | +0.22 / −0.74 | −0.29 / +0.11 | 1951 | 1,2,3,5,6,8 |
| reserve 0.5 | +2.19 / +0.52 / −14.32 / −18.94 | −8.56 | 11.8 | 19 / 22 | +1.58 / −0.05 / −15.88 | +0.31 / −1.13 | −0.22 / +0.23 | 1462 | 1,5,6,7,8 |
| top-up off | +0.82 / +0.05 / −13.14 / −15.42 | −6.09 | 7.5 | 16 / 21 | +0.47 / −0.29 / −14.25 | −0.43 / −3.14 | −1.05 / +0.12 | 780 | 1,2,5,6,8 |
| s3 h48 c72 | +1.95 / +0.89 / −17.81 / −19.89 | −14.33 | 14.0 | 21 / 25 | +1.24 / +0.16 / −19.64 | +0.70 / −1.99 | +0.57 / +0.18 | 1623 | 1,3,5,6,7,8 |
| s4 h48 c72 | +1.86 / +0.43 / −21.33 / −23.26 | −17.81 | 12.8 | 16 / 17 | +1.15 / −0.22 / −23.07 | +1.26 / −2.73 | +0.99 / −1.17 | 2066 | all |
| s4 h48 c120 | +2.19 / +0.54 / −18.84 / −21.41 | −13.14 | 13.6 | 20 / 24 | +1.47 / −0.11 / −20.60 | +1.25 / −2.08 | +0.63 / −0.58 | 1907 | 1,3,5,6,7,8 |
| s4 h72 c72 | +1.87 / +0.38 / −21.16 / −22.29 | −18.14 | 12.8 | 18 / 18 | +1.14 / −0.31 / −22.79 | +1.28 / −2.75 | +0.69 / −0.97 | 1941 | all |

("all" = rules 1,2,3,5,6,7,8; rule 4 — calendar-month DD ≤ 35 — passes everywhere, max 17.3.)

Paired fold diff vs D, mean pp (t), 8 pairs 19/38 bps, ex-ZEC 19/38 bps:

| cell | 8p 19 | 8p 38 | xZEC 19 | xZEC 38 |
|---|---|---|---|---|
| cooldown 72 | −0.39 (−0.9) | −0.48 (−1.1) | +0.60 (+2.3) | +0.52 (+2.1) |
| cooldown 24 | −0.24 (−0.5) | −0.41 (−0.8) | +0.45 (+1.4) | +0.33 (+1.1) |
| s3 h48 c72 | −0.65 (−1.0) | −0.74 (−1.2) | +0.37 (+1.3) | +0.24 (+0.9) |
| hold 96 | −0.12 (−0.4) | −0.10 (−0.4) | +0.19 (+0.8) | +0.23 (+0.9) |
| reserve 0.2 | +0.03 (0.0) | −0.25 (−0.4) | +0.16 (+0.3) | −0.02 (0.0) |
| hold 24 | −0.90 (−1.0) | −0.95 (−1.0) | −0.08 (−0.3) | −0.09 (−0.3) |
| slots 4 | −0.60 (−0.6) | −0.64 (−0.6) | −0.15 (−0.3) | −0.23 (−0.4) |

## Reading

- **Nearest miss: cooldown 72 h.** Ex-ZEC +0.60 pp/fold (t 2.3, both halves positive, holds at 2× cost) but
  −0.39 pp with ZEC, worse goodness in both universes, worst fold −14.6 vs −10.1 and only 18–20/42 wins.
  One t≈2 cell out of 84 comparisons is what chance predicts; it is the 120 h vs 72 h trade already seen on
  09-14/09-30 (shorter cooldown re-buys names that just failed and deepens the bad folds).
- **More slots / shorter hold flip sign across halves.** Slots 4 and the 4-slot cube cells gain +1.0–1.3 pp on the
  2023-08..2025-02 folds and lose −2.1 to −2.8 pp on 2025-03..2026-09: no stable more-data effect, and the
  recent regime (the one live trades in) prefers the concentrated deployed book.
- **Sizing**: reserve 0.2 ties the mean (+0.03) at +4 pp worse calendar DD and −5.4 ex-ZEC goodness; reserve 0.5
  and top-up off improve goodness only by holding less, losing mean. The reserve/top-up choice stands.
- Turnover is not the binding constraint at 19 bps: cost per fill is ~0.4 % of a slot, but the extra fills in
  the more-trading cells buy worse names, not more of the edge (consistent with the 10-08 hysteresis result:
  rank changes carry information in both directions, so the 72 h/top-3 rule sits at the turnover optimum).

## Reproduce

```
W=/vfast/data/wt/bbpx-knobs; R=$W/research/knobs20261008; L=/vfast/data/code/bitbankpoloniex/data/longkfold20261007
python3 $R/prepare_go.py --src $L/release_source --out $W/data/knobs/gobuild
python3 $R/grid.py $L/fx $W/data/knobs/rp > $W/data/knobs/jobs.txt
$R/queue.sh $W/data/knobs/jobs.txt 10        # 42 runs, ~2 min each
python3 $R/evaluate.py $W/data/knobs/rp --md $R/grid_results.md
```

Limitations: same as 10-07/10-08 (hourly-open proxy books, today's contracts, fold-end liquidation, folds already
examined). Minimum hold is hard-coded at 72 h in the deployed engine, so a hold change would have needed a flag.
