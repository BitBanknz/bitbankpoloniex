# Walk-forward ranker: not promoted

Pre-registered in `2026-10-02-ranker-prereg.md`. Code `research/ranker20261001/`, replay table
`research/ranker20261001/replay_summary.txt` (baseline = production scores, deployed profile).

Window A (2023-2025, 420 days with all 8 live pairs eligible): linear and shallow-tree models carry
IC ~0.077 (t~3.6) but only +0.04-0.05%/day top-3 excess (t~0.5); MLPs and deeper trees are worse
(IC 0.05-0.06). Frozen rule selected `lgb_7` (IC 0.0790).

Window B (2026-01-14..09-06, 236 days, touched once): production IC 0.0857 (t=3.0), `lgb_7` 0.0682
(t=2.2), 50/50 rank blend 0.0923 (t=3.1); daily rank correlation between lgb_7 and production 0.30.

Replay (slots 3 / 120h / reserve 0.4 / halts 25-8; mean return %, 28-day folds at 40 bps / 56-day at 40 bps):

| scores | cont 30/40 | 28d@40 | 56d@40 |
|---|---|---|---|
| production (live) | +8.85 / +18.35 | +1.75 | +2.89 |
| R2 blend | -4.42 / -7.58 | -0.88 | -0.85 |
| R1 lgb_7 alone | -7.68 / -13.43 | -1.61 | -2.85 |
| R3 lgb_7, 51-pair universe | -24.92 / -26.02 | -2.95 | -5.64 |

All three lose to production on every mean cell; none passes any promotion rule. Conclusion: a
higher blended IC did not survive the engine's holding/stop/cooldown dynamics, a wider universe
hurt (illiquid-name book proxies and noise), and the production forecaster has information that
daily price/volume features from the archive do not reproduce. Live scores unchanged. IC on a 24h
label is a poor proxy for this engine's PnL; future ranker work should be judged in the replay only.
