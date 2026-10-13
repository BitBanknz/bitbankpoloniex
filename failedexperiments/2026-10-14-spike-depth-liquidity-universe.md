# Round 4: resting spike sells, depth haircut, liquidity floor, universe search — 2026-10-14

Pre-registered: `docs/2026-10-14-spike-depth-liquidity-prereg.md` (7ea15da), on the fidelity 42-fold harness, book seeds 1-3,
8p and ex-ZEC, 14/33 bps. With every hook off the harness reproduces the incumbent byte-for-byte (`parity_inc_b1`).
Results are in `research/spike20261014/results/` and `research/uni20261014/results/`. Nothing is deployed.

## 1. Resting close-side spike sells: rejected

The order is a limit at open·(1+K·sd), re-placed every hour, filled when the hour's high trades through it by 10 bp.
Every K∈{2,3,4,6} × W∈{24,168} loses in every cell.

| arm | 8p @14 | ex-ZEC @14 |
|---|---|---|
| K=2 | −3.5 pp (t −4.9) | −1.9 pp |
| K=6, W=168 (best) | −0.73 (t −2.1) | −0.66 |

- Worst folds improve for small K (less exposure), but mean, median and paired wins all fall.
- The same mechanism as the 10-08 take-profit study: selling into spikes cuts the right tail that pays for the rotation,
  and the 120h cooldown then blocks re-entry.
- No 1m check was needed, because the arm already fails on the optimistic hourly rule.

## 2. Depth haircut re-score: a measurement, which changes the ZEC reading

**Notional fill ratio of the incumbent in sim:**
- 0.95 on the archive book;
- 0.93 at ×0.25, 0.90 at ×0.1, 0.86 at ×0.03;
- 0.91 with ZEC ×0.02.

Live was 0.51 over 10-10..10-13, but that is a handful of orders, dominated by the ZEC 01:00 order that filled 1 of
49 USDT. No global haircut reproduces it, so the ZEC-only `z02` is the targeted calibration.

**Incumbent (8p @14):**
- +2.05 on the default book;
- `d25` +1.81, `d10` +1.25, `d03` lower again, `z02` +1.00 (−1.06 pp, t −2.1);
- ex-ZEC is unchanged (+0.17 → +0.17..+0.27).

About half of the incumbent's 8-pair edge over ex-ZEC depends on ZEC fills that live books may not provide.

**Paper arms against the incumbent on the same haircut book** (Δ mean pp/fold, paired wins of 126):

| book | hema 8p @14 / @33 | hema ex-ZEC | ridge 8p @14 / @33 | ridge ex-ZEC @14 / @33 |
|---|---|---|---|---|
| default | −0.55 / −0.54 | +0.72 | +0.17 / +0.44 | +0.94 / +1.18 |
| d25 | −0.62 / −0.63 | +0.51 | +0.32 / +0.59 | +0.90 / +1.17 |
| d10 | −0.62 / −0.63 | +0.21 | +0.65 / +0.85 | +1.12 / +1.37 (t 2.6) |
| z02 | +0.12 / +0.09 | +0.72 / +0.76 | +0.91 / +1.11 (t 2.1) | +0.94 / +1.18 |

- On every haircut book, ridge beats the incumbent on mean and worst fold in all 12 cells (worst −6..−9.5 vs −11..−14 %).
  Paired wins are 61-69/126 (48-55%), still at or below the registered 55%.
- On the ZEC-haircut book, hema beats the incumbent on mean and worst fold in all 4 cells, but has 54/126 wins on 8p.
- Neither passes G1 as registered. The haircut evidence moves both paper arms towards the incumbent's level or above it,
  and the incumbent's 8p lead depends on ZEC fills. The paper A/B (control/hema/ridge) is the arbiter, under the pre-registered 28/56-day rules.

## 3. Liquidity floor: rejected

| arm | 8p @14 | ex-ZEC @14 | notes |
|---|---|---|---|
| drop SUI+PEPE (widest spreads) | +0.04 (70/126) | −0.02 | under ×0.1 depth −0.14 ex-ZEC |
| 24h volume floor 3M | −1.27 | −0.60 | |
| 24h volume floor 8M | worse | | |

## 4. Universe as a searched parameter: mopt (lee101/mojo-optuna 7f5c939), daisy

**Setup:**
- Signal: the production recipe retrained on the 24-pair U+ panel (2023-06+).
- Simulator: the fast daily simulator (`uni_obj.py`), with costs of 14/33 bps plus per-pair half-spread.
- Search space: subset of 24 pairs × slots/hold/cooldown/reserve/EMA/stop × half-spread cap × 24h-volume floor.
- Sampler: GA, 802 trials. Objectives: mean return (max) and fold max DD (min). Constraints: DD ≤ 30, idle ≤ 25%.

**Results:**
- In-sample best ret.mean is +2.5..+3.3 %/fold. It trades BTC/DOGE/SHIB/SOL with a 5 bp half-spread cap.
- PBO (CSCV, S=16) 0.41; DSR 0.51 (N_eff 280).
- Post-hoc nested WF, 18 outer folds (24-41): outer mean −1.12 against an inner 2.87, −2.32±1.5 vs the U8 baseline, win
  0.39. The symbol-selection penalty is 5.7 pp.
- Strict nested WF (`mopt nested`, a fresh 150-trial search per outer fold, 6 outer folds): outer mean −1.12, +2.15±2.44
  vs baseline (5/6 wins, driven by baseline losses on 2 folds). Pick Jaccard is 0.59.
- symnull: the chosen universe beats 30 random same-size universes in-sample (percentile 1.0). That is in-sample only.

**Verdict:** the gain does not survive out of fold. No config goes on to the Go harness. The universe search will be
re-run when the paper A/B has data.
