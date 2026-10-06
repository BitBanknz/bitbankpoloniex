# Long-history causal k-fold + more-data scaling test — 2026-10-07

Research only. Nothing deployed, no production service touched (remote reads only:
release source, training seed, bundle manifest, forecast state).

## Verdict

- **Incumbent long-history k-fold (42 × 28-day folds, 2023-08-02 → 2026-10-06, native Go
  engine, deployed profile):** mean +2.02 %/fold at 30 bps (+1.73 at 40), median +2.11,
  worst −10.9, 24/42 positive, max calendar-month DD 13.3 % (13.6), fleet goodness −16.87
  (−17.75), PASS the 35 % gate. **Ex-ZEC the edge is gone:** −0.04 %/fold (−0.31),
  goodness −22.75 (−23.51). One fold (2025-09-24, ZEC rally) is +40.6 %; without it the
  mean is +1.08 (+0.79).
- **Scaling: no training window dominates.** Expanding-from-2023-06 beats rolling-365d
  and 2024-10 on the 42/24-fold windows *with* ZEC, but loses its edge ex-ZEC (2024-10 is
  best ex-ZEC); on the 11 folds where the production start (2025-10) exists, prod has the
  highest mean (+3.29) while 2023-06 has the best goodness and worst fold. More history
  does not monotonically help; rolling 365d is worst with ZEC everywhere.
- **Variants (run anyway because cheap):** bagged lgbm_rank ×16 (0.8/0.8) is −0.73 pp/fold
  on 42 folds (11/42 wins), neutral ex-ZEC. Cash reserve 0.3/0.2 is +1.4/+2.1 pp on the
  11 prod folds but −0.2/−0.15 pp on 42 folds, negative on the 24-fold window and ex-ZEC
  in every window, with worse goodness and +2–4 pp DD. Single-block effect — rejected.
- **Nothing is promoted.** Production stays: 2025-10-01 expanding seed, single lgbm_rank,
  `--cash-reserve 0.4`.

## Data and bit-exactness

`research/longkfold20261007/build_panel.py` pulls hourly candles for BNB ETC ETH PEPE SUI
TRX XRP ZEC from the Poloniex public API, 2023-06-01 00:00 → 2026-10-06 21:00 UTC
(29,374 h). Checks:

- Panel == production training seed (`data/rotation/training-seed`, 2025-10-01 →
  2026-09-08) exactly, all 8 pairs × OHLCV (the local `data/archive-hourly` differs by
  ~1e-10 float formatting, so it is only cross-checked).
- `fit_refresh` (imported unchanged from bitbankgo `scripts/rotation_refresh.py`, identical
  to the remote runtime copy) on the panel at valid_from 2026-09-23 reproduces the live
  bundle: `training_data_sha256` match, 338 origins, same last origin, max |prediction
  diff| 0.0. The reproduced raw scores for 2026-10-06 equal the live `forecast.json`
  `raw_scores` exactly.
- Only gap: 2023-10-30 03:00–04:00 UTC (venue returned no candles, all pairs) —
  forward-filled close, zero volume. Production `fetch_poloniex_research.py` would refuse
  this window (see deploy notes).

## Method

- **Refit grid** phase-locked to production (valid_from 2026-09-23, 28-day validity,
  5-day gap inside `fit_refresh`). At each refit the training data is the panel from the
  arm start to the refresh hour (valid_from−1, exclusive) — what `load_extended` hands
  `fit_refresh`. A refit is skipped until it has ≥40 origins (fit_refresh's own guard).
- **Inference** daily 00:00 UTC from the 337 completed hours, raw scores → EMA 0.35/0.65,
  continuous across refits (as `rotation_forecast.issue`).
- **Folds** = refit validity blocks (portfolio reset each fold, EMA not reset). Last fold
  2026-09-23 is 14 days.
- **Arms:** `e2306` expanding from 2023-06-01 (long-history incumbent recipe), `e2410`
  from 2024-10-01, `s2510` from 2025-10-01 (= production), `r365` rolling 365 days
  (identical to e2306 before 2024-06). First valid refit: e2306/r365 2023-08-02 (42
  folds), e2410 2024-12-18 (24), s2510 2025-12-17 (11).
- **Execution: native Go engine**, the deployed release source
  (`release-stop-guard-20260930_v3`, binary sha256 4cc91224…), built by `prepare_go.py`
  with the same clock/loopback patches as `research/sweep20260930/prepare.py`; driver
  `replay_test.go.txt`. Deployed profile: budget 495, max order 49, 12 orders/day, 12
  engine cycles in the 01:00 hour, slots 3, cooldown 120 h, 72 h min hold, 10 % trailing
  stop, slot top-up, reserve 0.4, halts 0.25 peak / 0.08 daily (latched to fold end; no
  fold halted at 0.4). Costs: `FeeRate` 0.003 / 0.004 plus the fixture's 5 bps proxy
  half-spread (35/45 bps per side effective vs 18–20 bps measured live). Books are
  hourly-open proxies with depth = 10 % of prior-hour turnover; market contracts are
  today's.
- **Harness check:** on the 2026-09-12 frontier fixture the driver reproduces the
  sweep20260930 deployed-config 28-day folds to 6 dp on 6/9 folds; the other 3 differ
  because that sweep predates the stop/top-up guard now deployed.
- **Ex-ZEC:** same scores, ZEC removed from the tradable universe (rank of the other 7).
- **Equity curves:** hourly engine marks per fold plus a start point at the budget and a
  final liquidation-at-bid-net-of-fee point; CSV `fold,ts,equity`, scored with
  `python3 ~/code/dashboard-finance/research/goodness/goodness.py curves.csv --folds`
  (fleet-v1, 35 % calendar-month DD gate). Goodness is negative for every arm because
  28-day folds and the 0.3·worst-decile + 0.2·worst-fold weights dominate; use it
  comparatively.

### Python walk-forward harness gap

`harness_gap.py` runs `rotation_policy.simulate_rotation` exactly as
`poloniex_deployed_walkforward.py --slots 3` (volatility entry budget, margin 0.4,
liquidated at fold end; fee = Go fee + 5 bps) on the same EMA ranks and folds:

| scores | fee | folds | Python mean | Go mean | gap | mean abs gap | corr | max DD py/go |
|---|---|---|---|---|---|---|---|---|
| e2306 | 30 | 42 | +0.79 | +2.02 | −1.23 pp | 4.17 pp | 0.62 | 10.4 / 16.1 |
| e2306 | 40 | 42 | +0.60 | +1.73 | −1.12 pp | 4.09 pp | 0.62 | 10.6 / 16.4 |
| s2510 | 30 | 11 | +1.99 | +3.29 | −1.30 pp | 3.57 pp | 0.90 | 9.2 / 12.9 |

The Python harness under-sizes (volatility budget vs 99 USDT slot target, no top-up, no
49 USDT/12-orders cap, margin hysteresis instead of plain top-3) and is only 0.62
correlated per fold over the long history: use the Go engine for decisions.

## Results (30 bps; 40 bps in `research/longkfold20261007/results/`)

### A. Long history, 42 folds 2023-08-02 → 2026-10-06

| arm | goodness 30/40 | mean %/fold 30/40 | median | worst | pos | max cal-month DD | max marked DD |
|---|---|---|---|---|---|---|---|
| **e2306 (incumbent recipe)** | −16.87 / −17.75 | +2.02 / +1.73 | +2.11 | −10.87 | 24/42 | 13.3 | 16.1 |
| r365 | −23.00 / −24.14 | +0.11 / −0.26 | +0.61 | −16.63 | 24/42 | 12.7 | 21.2 |
| e2306 bag16 | −17.91 / −18.70 | +1.29 / +0.99 | +1.40 | −11.39 | 23/42 | 12.6 | 14.6 |
| e2306 reserve 0.3 | −19.88 / −20.90 | +1.83 / +1.46 | +2.72 | −12.99 | 25/42 | 15.5 | 20.6 |
| e2306 reserve 0.2 | −22.93 / −24.09 | +1.87 / +1.40 | +2.29 | −15.73 | 25/42 | 17.2 | 22.9 |
| e2306 ex-ZEC | −22.75 / −23.51 | −0.04 / −0.31 | −0.24 | −15.30 | 20/42 | 12.3 | 16.7 |
| r365 ex-ZEC | −23.43 / −24.50 | −0.88 / −1.24 | −0.89 | −15.12 | 19/42 | 13.8 | 20.7 |
| e2306 bag16 ex-ZEC | −20.90 / −21.59 | −0.02 / −0.27 | −0.45 | −13.15 | 19/42 | 12.6 | 14.9 |
| e2306 res0.3 ex-ZEC | −25.98 / −26.95 | −0.16 / −0.56 | +0.29 | −18.06 | 22/42 | 15.5 | 21.2 |

Paired vs e2306 (30 bps): r365 11/42 wins, −1.91 pp (t −1.78); bag16 11/42, −0.73 pp
(t −1.83); reserve 0.3 20/42, −0.19 pp; reserve 0.2 20/42, −0.15 pp. Ex-ZEC: r365
−0.85 pp, bag16 +0.02 pp, reserve 0.3 −0.13 pp. Fold-chained e2306: +98 % (30) / +75 %
(40) over 3.2 years; ex-ZEC −13 % / −22 %. Top-3 folds sum to +74.5 pp of the +85 pp total.

### B. Scaling, 24 common folds 2024-12-18 → (e2306 vs e2410 vs r365)

| arm | goodness 30/40 | mean 30/40 | worst | max cal DD | paired vs e2306 (30) | ex-ZEC mean 30/40 | ex-ZEC goodness 30 |
|---|---|---|---|---|---|---|---|
| e2306 | −16.97 / −17.71 | +2.33 / +2.11 | −10.87 | 11.6 | — | −1.67 / −1.86 | −25.73 |
| e2410 | −20.79 / −21.69 | +0.21 / −0.06 | −11.82 | 12.4 | 10/24, −2.12 pp | −0.87 / −1.14 | −23.11 |
| r365 | −24.91 / −26.06 | −0.53 / −0.88 | −16.63 | 12.7 | 7/24, −2.86 pp | −1.52 / −1.86 | −25.48 |

Ex-ZEC, e2410 beats e2306 16/24 (+0.80 pp, t 1.71): the more-data advantage is ZEC.

### C. Scaling, 11 common folds 2025-12-17 → (all four; production start exists)

| arm | goodness 30/40 | mean 30/40 | median | worst | pos | max cal DD | paired vs s2510 (30) | ex-ZEC mean 30/40 | ex-ZEC goodness 30/40 |
|---|---|---|---|---|---|---|---|---|---|
| **s2510 (prod)** | −14.90 / −15.66 | +3.29 / +3.01 | +3.22 | −9.95 | 8/11 | 10.3 | — | −0.46 / −0.73 | −21.63 / −22.37 |
| e2306 | −12.37 / −13.18 | +2.97 / +2.69 | +2.43 | −8.87 | 7/11 | 9.5 | 7/11, −0.33 pp | −0.24 / −0.49 | −23.02 / −23.70 |
| e2410 | −13.66 / −14.36 | +2.81 / +2.62 | +2.09 | −9.20 | 8/11 | 10.2 | 7/11, −0.49 pp | +1.01 / +0.80 | −19.57 / −20.20 |
| r365 | −13.55 / −14.37 | +1.97 / +1.69 | +0.85 | −8.57 | 8/11 | 9.5 | 6/11, −1.32 pp | −0.68 / −0.95 | −21.28 / −21.99 |
| s2510 bag16 | −14.57 / −15.32 | +3.34 / +3.07 | +3.00 | −9.80 | 8/11 | 10.1 | 7/11, +0.05 pp | −0.83 / −1.10 | −20.63 / −21.45 |
| s2510 reserve 0.3 | −13.86 / −14.75 | +4.73 / +4.39 | +2.82 | −11.73 | 8/11 | 11.6 | 9/11, +1.43 pp (t 2.28) | −0.73 / −1.04 | −24.62 / −25.44 |
| s2510 reserve 0.2 | −15.34 / −16.33 | +5.36 / +4.97 | +3.63 | −13.51 | 8/11 | 13.4 | 9/11, +2.06 pp | −0.81 / −1.16 | −27.20 / −28.11 |

Dominance rule (better goodness AND mean, not worse worst fold, both fees, robust ex-ZEC):
no arm passes. e2306 vs prod: goodness/worst better, mean worse, ex-ZEC goodness worse.
e2410 vs prod: goodness better and ex-ZEC better, mean worse. Reserve 0.3 vs prod: mean and
goodness better, worst fold worse, ex-ZEC worse, and it fails to replicate on 24/42 folds.

### Per-fold returns (% per 28-day fold; e2306 columns also show calendar-month DD)

| fold start | e2306 @30 | e2306 @40 | e2306 xZEC @30 | e2306 xZEC @40 | r365 @30 | e2410 @30 | s2510 @30 | e2410 xZEC @30 | s2510 xZEC @30 |
|---|---|---|---|---|---|---|---|---|---|
| 2023-08-02 | −6.61 (8.3) | −7.03 (8.6) | −5.68 | −6.00 | −6.61 | | | | |
| 2023-08-30 | −1.53 (2.8) | −1.90 (2.8) | −1.53 | −1.90 | −1.53 | | | | |
| 2023-09-27 | +4.24 (4.9) | +3.96 (4.9) | +4.24 | +3.96 | +4.24 | | | | |
| 2023-10-25 | +3.16 (5.0) | +2.88 (5.1) | +3.28 | +3.04 | +3.16 | | | | |
| 2023-11-22 | +3.53 (7.4) | +3.01 (7.6) | +6.24 | +5.83 | +3.53 | | | | |
| 2023-12-20 | +2.32 (7.2) | +1.95 (7.2) | +3.31 | +2.92 | +2.32 | | | | |
| 2024-01-17 | +0.39 (4.6) | +0.08 (4.7) | +0.39 | +0.08 | +0.39 | | | | |
| 2024-02-14 | +4.87 (6.7) | +4.38 (6.8) | +1.38 | +0.91 | +4.87 | | | | |
| 2024-03-13 | −8.72 (9.6) | −9.14 (9.7) | −8.72 | −9.14 | −8.72 | | | | |
| 2024-04-10 | −4.11 (8.6) | −4.47 (8.7) | −4.44 | −4.79 | −4.11 | | | | |
| 2024-05-08 | −2.15 (6.9) | −2.60 (7.2) | −2.15 | −2.60 | −2.15 | | | | |
| 2024-06-05 | −5.99 (8.8) | −6.26 (8.9) | −5.24 | −5.52 | −5.15 | | | | |
| 2024-07-03 | +4.21 (7.4) | +3.82 (7.6) | +0.34 | −0.03 | +3.22 | | | | |
| 2024-07-31 | +10.44 (8.4) | +10.00 (8.6) | +8.43 | +8.00 | −3.49 | | | | |
| 2024-08-28 | +5.63 (5.4) | +5.26 (5.5) | +5.63 | +5.26 | +7.30 | | | | |
| 2024-09-25 | −1.59 (6.5) | −1.93 (6.7) | −1.25 | −1.55 | −1.14 | | | | |
| 2024-10-23 | +11.44 (4.7) | +11.08 (4.7) | +10.56 | +10.06 | +9.29 | | | | |
| 2024-11-20 | +9.55 (13.3) | +8.78 (13.6) | +23.77 | +23.07 | +12.03 | | | | |
| 2024-12-18 | −10.87 (9.6) | −11.37 (9.8) | −13.30 | −13.70 | −16.63 | −11.82 | | −13.00 | |
| 2025-01-15 | −7.03 (11.6) | −7.53 (11.8) | −7.06 | −7.55 | −10.54 | −11.20 | | −4.90 | |
| 2025-02-12 | −10.20 (11.5) | −10.63 (11.7) | −13.38 | −13.82 | −12.27 | −9.69 | | −9.69 | |
| 2025-03-12 | +1.24 (6.5) | +0.88 (6.6) | +0.65 | +0.29 | +0.04 | −3.18 | | −3.18 | |
| 2025-04-09 | +5.33 (4.0) | +5.02 (4.0) | +7.67 | +7.40 | +5.22 | +6.31 | | +6.31 | |
| 2025-05-07 | +7.42 (3.9) | +7.14 (3.9) | +6.02 | +5.74 | +7.42 | +2.85 | | +2.85 | |
| 2025-06-04 | −5.50 (7.4) | −5.83 (7.5) | −6.25 | −6.60 | −7.25 | −4.03 | | −4.03 | |
| 2025-07-02 | +9.89 (4.8) | +9.56 (4.8) | +9.89 | +9.56 | +10.00 | +12.79 | | +14.77 | |
| 2025-07-30 | −0.19 (6.4) | +2.38 (5.8) | −0.19 | +2.38 | −2.47 | −0.35 | | −0.35 | |
| 2025-08-27 | −1.27 (4.1) | −1.56 (4.1) | −2.38 | −2.62 | −2.27 | −0.90 | | −0.90 | |
| 2025-09-24 | +40.63 (7.0) | +40.17 (7.1) | −4.15 | −4.56 | +1.05 | +0.36 | | −1.11 | |
| 2025-10-22 | +2.34 (8.0) | +1.76 (8.2) | −7.19 | −7.63 | +2.87 | +2.87 | | −10.27 | |
| 2025-11-19 | −8.57 (6.8) | −8.95 (6.9) | −7.77 | −8.13 | −9.56 | −9.85 | | −8.45 | |
| 2025-12-17 | +1.91 (3.8) | +1.68 (3.9) | +13.38 | +13.20 | +2.99 | +2.45 | +1.66 | +14.90 | +4.02 |
| 2026-01-14 | −8.87 (9.5) | −9.26 (9.7) | −15.30 | −15.71 | −8.57 | −9.20 | −8.91 | −14.04 | −15.65 |
| 2026-02-11 | −1.53 (7.6) | −1.85 (7.7) | −0.53 | −0.79 | +0.85 | +1.76 | +3.22 | −1.35 | +2.75 |
| 2026-03-11 | +7.19 (5.9) | +6.90 (6.0) | −0.28 | −0.59 | +0.52 | +9.45 | +7.20 | +1.11 | +2.16 |
| 2026-04-08 | +10.06 (2.5) | +9.77 (2.6) | +2.39 | +2.14 | +2.52 | +8.80 | +6.68 | +2.40 | +2.33 |
| 2026-05-06 | +2.43 (5.1) | +2.13 (5.1) | −3.10 | −3.40 | +0.70 | +0.84 | +0.10 | −2.71 | −5.41 |
| 2026-06-03 | −7.77 (7.7) | −8.04 (7.9) | −8.33 | −8.62 | −7.53 | −7.77 | −9.95 | −7.25 | −7.71 |
| 2026-07-01 | +5.59 (3.1) | +5.41 (3.1) | +1.15 | +0.86 | +4.94 | +2.09 | +5.62 | +5.14 | +3.07 |
| 2026-07-29 | +3.35 (4.8) | +3.04 (4.9) | +9.26 | +9.08 | +14.16 | +4.84 | +13.79 | +10.23 | +8.54 |
| 2026-08-26 | +22.41 (5.2) | +22.14 (5.2) | +4.35 | +4.17 | +14.36 | +21.03 | +20.43 | +4.19 | +3.74 |
| 2026-09-23* | −2.15 (3.4) | −2.36 (3.5) | −5.61 | −5.78 | −3.27 | −3.42 | −3.60 | −1.46 | −2.86 |

\* 14-day partial fold. Full per-arm/per-fee tables (incl. bag16 and reserve variants,
calendar-month DD for every arm) are in `research/longkfold20261007/results/*.md`;
goodness `--folds` JSON for e2306, e2306 ex-ZEC and s2510 in `results/goodness_*.json`.

Rank IC of the EMA score vs 72 h forward return (top-3 excess in brackets): since
2023-08 e2306 +0.059 (+0.27 %), r365 +0.054 (+0.07 %); since 2025-12-17 s2510 +0.097
(+0.42 %), e2410 +0.075, r365 +0.073, e2306 +0.067 (+0.15 %). The recent-block ordering
reverses the long-history one — consistent with no stable more-data effect.

## If the owner still wants a variant deployed (not recommended by this gate)

Nearest candidate is e2306 (more history). Steps, bitbankgo on the remote:

1. `cd /nvme0n1-disk/code/bitbankgo && data/rotation/venv/bin/python scripts/fetch_poloniex_research.py --out data/rotation/training-seed-<start> --start <start> --end <today UTC>`
   (needs `--audit` with the 8-pair list; the default
   `content/poloniex-transfer-v1/data-audit.json` exists in the local bitbankgo tree but
   not on the remote — copy it, then verify the seed manifest's
   `frozen_universe_audit_sha256` matches the current one `80c71819…`). A
   2023-06-01 start fails its grid check on the 2023-10-30 03–04 UTC venue gap; use
   `--start 2023-10-31` or add forward-fill for missing hours (research did the latter).
   2024-10-01 has no gaps.
2. Stop nothing; swap `data/rotation/training-seed` for the new directory (or point
   `bitbankgo-rotation-refresh.service --seed` at it). The seed manifest hash enters the
   next bundle manifest.
3. Let the scheduled refresh refit at 2026-10-21 00:00 UTC (keeps the 28-day phase), or
   `data/rotation/venv/bin/python data/rotation/runtime/rotation_refresh.py --bundle data/rotation/bundle --seed data/rotation/training-seed --force`
   (new phase from the next UTC day). Check the new manifest's `training_origins`
   (≈ days since start − 20) and that inference continues the EMA state.
4. No bitbankpoloniex change: ranks arrive via the rotation-signals API.

A sizing change would be `--cash-reserve 0.3` in `bitbankpoloniex-live.service`
ExecStart plus restart; bagging would need a new model kind in
`poloniex_rank_models.py` and `rotation_forecast.checked_model` (which asserts a single
`lgbm_rank` with 38 features). None are supported by this evidence.

## Reproduce

```
R=research/longkfold20261007; D=data/longkfold20261007; P=<venv: numpy 2.2.6 pandas 2.3.3 lightgbm 4.6.0 scikit-learn 1.7.2>/bin/python
$P $R/build_panel.py --out $D/panel.npz --seed <copy of remote data/rotation/training-seed>
$P $R/scores.py --panel $D/panel.npz --start 2023-06-01 --out $D/scores/e2306.npz      # --start 2024-10-01 / 2025-10-01, --rolling-days 365, --bag 16
$P $R/scores.py --panel $D/panel.npz --start 2025-10-01 --out $D/scores/s2510.npz --verify-prod <copy of remote data/rotation/bundle>
$P $R/make_fixture.py --panel $D/panel.npz --scores $D/scores/e2306.npz --out $D/fx/e2306.json   # --drop ZEC for ex-ZEC
python3 $R/prepare_go.py --src $D/release_source --out $D/gobuild    # release_source = remote data/release-stop-guard-20260930_v3/release_package/source
$R/run_replay.sh $D/fx/e2306.json $D/rp/e2306 ['{"Reserve":0.3,...}']   # ~1-3 min per arm; state on /dev/shm (engine fsyncs every cycle)
$P $R/summarize.py $D/rp e2306 r365 [--from 2024-12-18]     # writes rp/<arm>/curves_fee<fee>.csv
python3 ~/code/dashboard-finance/research/goodness/goodness.py $D/rp/e2306/curves_fee0.003.csv --folds
$P $R/harness_gap.py --panel $D/panel.npz --scores $D/scores/e2306.npz --go $D/rp/e2306
```

Limitations: hourly-open proxy books and today's market contracts; the latched risk
halt ends at the fold boundary (live needs operator review); ex-ZEC keeps the 8-pair model
and only removes ZEC from the tradable set; costs 35/45 bps effective are above measured
live; fold-chained compounding ignores carry-over of positions across folds.
