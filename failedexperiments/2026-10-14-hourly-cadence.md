# Hourly rotation decisions (bitbankgo ranks issued + consumed hourly): rejected — 2026-10-14

Workstream W2 of `plan/trading-supervisor-20261013.md`. Research only: nothing deployed, no prod
service, ledger, model or unit touched. Branch `research/hourly-20261013` (off live 730408a).

## Verdict

- **Hourly decisions lose.** Every arm that lets the engine act every hour loses to the daily
  01:00-window incumbent on 42 long-history folds x 3 book seeds, in 8 pairs and ex-ZEC, at 14 and 33 bps.
  Typical cost is -0.7 to -1.4 pp/28d (t -1.2 to -3.3), plus a worse worst fold and 15-140 % more fills.
- **The signal is not the reason.** An hourly EMA of hourly inference has higher static IC and top-3 excess
  than the daily EMA (72h IC .062 vs .055, top-3 excess +29.5 vs +21.2 bp). The losses come from execution
  cadence. `h_stale` keeps the *daily* ranks but lets the engine trade at every hour, and it loses
  -1.07 pp (t -2.1). Removing the 1 h execution delay (`_d0`) does not help. Debouncing exits by 24 h
  (`_cf24`) also does not help. All-day entries, top-ups and re-entries after stops lose to the
  once-a-day window. This agrees with the closed trading-frequency direction (10-02 hold, 10-08 hysteresis).
- **Chronos-2 features (zero-shot q50 24h/72h and q10-q90 width, plus ranks) lose** at both cadences
  (daily -0.48, hourly -1.00 pp; after the Chronos-2 release, 2025-10-22+, -1.13/-1.25). Their IC is higher
  but their top-3 excess is lower. Pretraining leakage cannot be excluded before 2025-10.
- **Hourly-origin training** (24x phase-pooled origins) has similar IC but its top-3 excess is far
  worse, so it was not replayed.
- **Near miss: `d_hema`** (hourly inference, EMA alpha .0178 = the same 1.86-day half-life, sampled at
  00:00 and executed in the normal daily window). This is not an hourly decision rule.
  - 28-day folds: 8p -0.55 pp (t -1.1). That comes from the single ZEC jackpot fold; without that fold it
    is +0.28 (t 1.4). Ex-ZEC it is +0.72 (t 2.3). The worst fold is better in both universes.
  - 84-day folds: +0.5 to +1.5 pp in all 4 cells, but paired wins are only 20-23/42.
  - It fails G1, because the 8p mean is worse and it does not win paired folds clearly. It is in the same
    family as the EMA 0.25 near miss, which failed confirmation on 10-02. If wanted, the only honest next
    step is a forward paper A/B: an hourly inference job plus a sidecar, like `bitbankpoloniex-ema25-signal`.

Gates: G1 fails for every arm. G2: all arms are within the limit (max calendar-month DD 11-16 %). G3/G4
were not reached, except the 84-day geometry check on the near miss. No endpoint or consumer was deployed.

## Results (means over book seeds 1-3; `research/hourly20261013/results/all.md`)

| arm | what | 8p mean / worst @14 | d vs inc (t) | xZEC mean / worst @14 | d (t) | 8p @33 d | max cal-month DD (8p/xZEC @14) |
|---|---|---|---|---|---|---|---|
| inc | daily incumbent (10-09 fidelity, byte-identical) | +2.05 / -11.76 | - | +0.17 / -13.31 | - | - | 12.8 |
| h_ema | hourly EMA .0178, 1h delay | +0.80 / -13.62 | -1.26 (-2.4) | -0.67 / -16.18 | -0.84 (-2.7) | -1.36 | 13.1 |
| h_anch | .35 hourly raw + .65 yesterday's daily EMA | +1.40 / -15.63 | -0.66 (-1.2) | -0.74 / -15.06 | -0.90 (-2.4) | -0.94 | 15.0 |
| h_ema05 | hourly EMA .05 | +0.95 / -14.29 | -1.10 (-1.6) | -0.48 / -17.45 | -0.64 (-1.7) | -1.32 | 13.7 |
| h_raw | hourly raw | -0.23 / -17.76 | -2.28 (-3.3) | -1.13 / -17.07 | -1.30 (-3.0) | -2.69 | 15.0 |
| h_ema_d0 | h_ema, 0h delay | +0.80 / -13.55 | -1.26 (-2.4) | -0.74 / -16.13 | -0.90 (-2.8) | | 12.6 |
| h_anch_d0 | h_anch, 0h delay | +1.63 / -13.90 | -0.42 (-0.7) | -0.61 / -16.66 | -0.77 (-1.9) | | 15.9 |
| h_ema_cf24 | h_ema, exit after 24h outside top 3 | +0.66 / -13.87 | -1.39 (-2.6) | +0.17 / -16.18 | +0.00 | | 13.1 |
| h_anch_cf24 | h_anch, same debounce | +1.04 / -13.72 | -1.01 (-1.4) | +0.41 / -15.64 | +0.25 (+0.7) | -1.04 | 13.7 |
| h_stale | daily ranks, engine acts every hour | +0.98 / -13.39 | -1.07 (-2.1) | +0.06 / -15.01 | -0.10 (-0.4) | -1.18 | 13.4 |
| h_chr | +Chronos-2 features, hourly EMA (41 folds) | +1.25 / -12.32 | -1.00 (-1.7) | -0.21 / -16.65 | -0.50 (-1.7) | | 14.4 |
| d_chr | +Chronos-2 features, daily (41 folds) | +1.77 / -13.30 | -0.48 (-1.4) | +0.07 / -16.53 | -0.21 (-0.7) | | 13.1 |
| **d_hema** | hourly-EMA ranks, daily execution | +1.51 / **-11.18** | -0.55 (-1.1) | **+0.89 / -12.20** | **+0.72 (+2.3)** | -0.54 | 12.2 |

Paired t is over 42 folds x 3 seeds (126). Win counts are in `results/all.md`. Not every 33 bps cell is
listed here; `all.md` has all of them.

## Method

- Panel, refit grid and EMA are the 10-07 long-history ones: e2306 expanding training, phase-locked
  28-day refits. `scores_hourly.py` runs inference at every hour from the 337 completed bars before
  it. With `--origins daily` it reproduces the production daily raw scores exactly (max |diff| 0.0) at 00:00.
- Engine: live source 730408a plus the new default-off consumer flag `--signal-cadence hourly`.
  `ValidateCadence` requires `cadence:"hourly"`, an issue on the hour and execution at issue or issue+1h.
  A daily consumer rejects hourly issues. Test: `internal/bot/cadence_test.go`.
- Harness: the 10-09 fidelity replay (archive books, measured 14 bps, safeguard exits, follow cycles),
  extended with `Cadence:"hourly"`, `Delay` (default 1 h, as daily), 12 cycles every hour, and the
  research-only hooks `ExitRank`/`ExitConfirmH` (gobuild2, inert by default).
  Parity: the daily incumbent reproduces the 10-09 `s3_h72_c120_r0.4_safe_b1` `curves.csv` and
  `results.jsonl` byte-for-byte (abf4f36e…), with both builds.
- Data, runs and fixtures: `/vfast/data/trading_research_20261013/hourly` (hashes in `results/sha256.txt`).

## Reproduce

```
R=research/hourly20261013; W=/vfast/data/trading_research_20261013/hourly; L=/vfast/data/code/bitbankpoloniex/data/longkfold20261007; P=<venv numpy/pandas/lightgbm 4.6.0>
$P $R/scores_hourly.py --panel $L/panel.npz --out $W/scores/m0.npz --cache $W/feat.npz --check $L/scores/e2306.npz
<chronos venv> -I $R/chronos_feats.py $L/panel.npz $W/chronos.npz; $P $R/scores_hourly.py ... --chronos $W/chronos.npz --out $W/scores/m0c.npz
$P $R/make_fixture.py --panel $L/panel.npz --scores $W/scores/m0.npz --smooth ema:0.0178 [--drop ZEC] --out $W/fx/m0_ema00178[_xzec].json
python3 -I $R/prepare_go.py --out $W/gobuild2; python3 -I $R/grid.py s1|s2|s3 $W/rp $W/fx > jobs.txt
BIN=$W/gobuild2/replay.test GOMAXPROCS=1 $R/queue.sh jobs.txt 10
$P $R/evaluate.py $W/rp --arms h_ema ... [--since 2025-10-22] [--base inc84 --arms d_hema84]
```

Do not redo: hourly execution cadence of any rank signal on this engine, 0 h delay, hourly exit debounce,
hourly-origin training, or Chronos-2 zero-shot features in the ranker.
