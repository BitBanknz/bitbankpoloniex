# Cross-exchange ranker, BTC regime gate and entry execution — results 2026-10-11

Prereg: `docs/2026-10-11-xregime-prereg.md` (e6f97bf, pushed before any result).
Verdict: **all five arms fail development at both costs. No finalist, confirmation folds
(30-41), 84-day windows and the full-data fit were not run.** Live unchanged.

## Checks before results

- Hooks-off research build of f3aa665 reproduced the 10-09 `s3_h72_c120_r0.4_safe` seed-1
  results and curves byte-for-byte (sha256 e5d23b26… / abf4f36e…).
- Control rebuild of the ranker (no Binance features) reproduced `e2306.npz` raw scores exactly
  (max diff 0.0) and its fixture equals `fx/e2306.json` byte-for-byte.
- Binance panel: 9 symbols, no missing hours from first listing to 2026-10-06 21:00; BTC 720h
  gate on 54.7% of days.

## Development (folds 0-29, seed-mean of book seeds 1-3, archive books, production argv)

| arm | fee | mean % | median % | worst % | Sortino | cal/r30 DD % | wins | delta ± se |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| incumbent | 14 bps | 1.99 | 1.94 | -11.36 | 1.49 | 12.5 / 18.6 | - | - |
| xr_feat | 14 | 1.06 | 1.98 | -11.70 | 0.83 | 12.3 / 19.7 | 16/30 | -0.94 ± 1.05 |
| btc720_entry | 14 | 0.99 | -0.17 | -13.65 | 0.83 | 12.3 / 16.1 | 10/30 | -1.00 ± 0.81 |
| btc720_flat | 14 | 0.01 | -0.48 | -13.65 | -0.04 | 12.3 / 16.1 | 9/30 | -1.98 ± 1.37 |
| xr_feat_btc720 | 14 | 0.30 | 0.78 | -14.31 | 0.25 | 11.4 / 16.8 | 13/30 | -1.70 ± 1.46 |
| exec_buy | 14 | 2.15 | 1.28 | -11.53 | 1.57 | 12.6 / 18.8 | 12/30 | +0.15 ± 0.19 |
| incumbent | 40 bps | 1.05 | 1.19 | -12.59 | 0.74 | 13.1 / 19.5 | - | - |
| xr_feat | 40 | 0.15 | 1.12 | -13.06 | 0.15 | 12.8 / 20.6 | 16/30 | -0.90 ± 1.06 |
| btc720_entry | 40 | 0.33 | -0.50 | -14.50 | 0.20 | 12.9 / 16.8 | 10/30 | -0.72 ± 0.81 |
| btc720_flat | 40 | -0.70 | -1.05 | -14.50 | -0.71 | 12.9 / 16.8 | 9/30 | -1.75 ± 1.37 |
| xr_feat_btc720 | 40 | -0.34 | 0.28 | -15.16 | -0.32 | 12.2 / 17.5 | 13/30 | -1.39 ± 1.45 |
| exec_buy | 40 | 1.17 | 0.58 | -12.76 | 0.81 | 13.2 / 19.7 | 8/30 | +0.12 ± 0.19 |

Gate failures: every arm has fewer than 18/30 paired wins and a worse worst fold at both costs;
the four signal/regime arms also lose mean and Sortino. `exec_buy` raises mean and Sortino
slightly (t ≈ 0.7-0.8) but loses the median fold and most paired folds: larger entry clips
buy more of the move on winners and more of the loss on losers, not a consistent edge.
Entries made while BTC is below its 720h mean were net profitable in these folds, so blocking
them costs return; going flat on those days is the worst arm. The Binance features shift
scores (corr 0.974 with the incumbent) without improving the realised rotation.

Drawdown: every arm stays far inside the 30% monthly target (max 20.6% rolling-30-day).

Reproduce: `research/xregime20261011` (prepare_go.py, binance_panel.py, xscores.py,
split_fixture.py, jobs.py, queue.sh, evaluate.py); hashes in `results/sha256.txt`.
