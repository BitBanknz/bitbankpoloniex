# Hourly-native cost-aware rotation and wider universe: fails the registered gate (near miss) — 2026-10-14

Pre-registration: `docs/2026-10-14-hourly-native-prereg.md` (a0b0801, committed before results). Research only, nothing deployed.

## Verdict

- **Best arm `hn_xs_m24`:**
  - Recipe:
    - ridge on the 38 hourly causal features, target = 24h excess return vs the same-hour cross-section;
    - hourly origins, production 28-day refits;
    - enter when the predicted excess is ≥ 50 bp, exit below −50 bp after 24h;
    - 3 slots, otherwise the live profile.
  - 28-day folds: it beats the daily incumbent on mean and worst fold in every cell, with lower DD and fewer fills.
  - It fails G1's ≥55% paired-win requirement, at 51-54%.
  - The gain comes from avoiding bad folds, not from winning typical folds: its median fold is lower.
- **Wider universe does not help.**
  - The registered rule picks 16 extra pairs (U+ = 24 pairs; `results/universe.txt`).
  - The same ridge recipe on U+ screens at +0.7 (8p) / +0.4 (ex-ZEC) %/fold, below the incumbent's +1.45 / +0.16.
  - Only 3/96 U+ configs pass the screen rule, and none rank in the top 3. The U8 effect does not generalise.
  - Spreads for the new pairs come from a recorder run on 10-13 only.
- **GBDT and the absolute-net-of-cost target** are weaker than ridge with the excess target. `hn_abs_m72` loses on 8 pairs.
- **2024-26 checked separately (W4's caution):** the effect holds from 2024-01, at +0.38..+0.67 pp on 8 pairs and
  +1.24..+1.85 ex-ZEC (t up to 2.5). Paired wins stay at 54-56%.

## Go fidelity harness

- 42 folds, archive books, 1h delay, 12 cycles/hour, book seeds 1-3. Paired t is over 126 fold-seeds.
- gobuild3 hooks: `Thresh`/`EntryMin`/`ExitBelow`. With hooks off it reproduces the incumbent byte-for-byte.

| arm | 8p @14 mean / worst | Δ (t) wins | 8p @33 Δ | xZEC @14 mean / worst | Δ (t) wins | xZEC @33 Δ | max cal-month DD |
|---|---|---|---|---|---|---|---|
| incumbent | +2.05 / −11.76 | – | – | +0.17 / −13.31 | – | – | 12.7 / 12.8 |
| **hn_xs_m24** | +2.23 / **−8.39** | +0.17 (0.2) 65/126 | +0.44 (0.6) 67/126 | +1.11 / **−8.37** | +0.94 (1.6) 65/126 | +1.18 (2.0) 68/126 | 10.2 / 9.6 |
| hn_xs_m72 (exit < 0, 72h) | +2.02 / −7.34 | −0.03 63/126 | +0.21 63/126 | +1.27 / −6.52 | +1.10 (1.7) 65/126 | +1.31 (2.1) 66/126 | 10.2 / 9.3 |
| hn_abs_m72 (abs target) | +1.39 / −11.58 | −0.66 (−0.9) | −0.48 | +1.06 / −11.38 | +0.89 (1.6) | +1.02 | 11.7 / 10.5 |

84-day folds (`results/hn84.md`), hn_xs_m24 vs incumbent: +2.2..+2.9 pp/84d in all 4 cells, worst fold −11.5 vs −25.8 % (8p),
calendar-month DD 9.5 vs 15.3 %. Paired wins are 19-21/42 and the median fold is lower. The 84-day result keeps the same
pattern: better tails, typical folds not won.

The fast simulator (`hn_sim.py`) over-estimated these arms by about 1 pp/fold against Go. It matches the incumbent within
0.6 pp, and the round-1 hourly arms within 1 pp.

## Caveats

- 288 screened configs on the same folds give selection bias. The Go stage then uses the same folds, so no fold is held out.
- Book shapes are drawn independently of volatility. Threshold entries happen in volatile hours, so real spreads and depth
  are likely worse than modelled.
- The ridge mostly loads on vol24 (+), market24 (−) and ret24 (+), i.e. it chases high-vol relative movers.

## If pursued (owner decision; not done)

A forward paper A/B of `hn_xs_m24` would need three things:
- a bitbankgo hourly ridge refit plus an endpoint publishing the predicted excess;
- Go/Mojo consumer flags `--entry-min/--exit-below`, ported from the research hooks;
- a paper unit on the hourly sidecar pattern.

It does not qualify for live under the registered gate.

Reproduce: `research/hourly20261013/{build_wide_panel,book_recorder,hn_scores,hn_sim,hn_screen,hn_select,hn_baseline}.py`, `grid.py hn1`,
gobuild3 via `prepare_go.py`. Data: `/vfast/data/trading_research_20261013/{hourly,books}`.
