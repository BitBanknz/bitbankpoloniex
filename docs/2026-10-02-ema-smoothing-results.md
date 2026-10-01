# EMA smoothing constant: not promoted

Registered in `2026-10-02-ema-smoothing-prereg.md`; tables `research/sweep20260930/ema_summary_full.txt` and
`confirm_ema025_summary.txt`. The production forecast job smooths z-scored daily scores with
`.35*raw + .65*previous` (remote `data/rotation/runtime/rotation_forecast.py` line 62); the fixture ranks are that
EMA (recovered raw scores have std exactly 1.0000 on all 236 days), so other constants were replayed exactly.

Registered sweep (a = 0.15, 0.25, 0.50, 1.00) plus calibration (0.20, 0.30, 0.40), 28d@40 mean: 0.15 +2.43, 0.20 +2.23,
0.25 +2.43, 0.30 +1.87, 0.35 live +1.75, 0.40 +2.10, 0.50 +2.37, 1.00 +0.86. No value passed the five-rule test;
no smoothing is clearly harmful; the calibration was ambiguous, so a=0.25 went to the stricter confirmation.

Confirmation (14/42/84-day folds, 30/50 bps): NOT CONFIRMED. a=0.25 is worse than live on 14-day folds (mean +0.95
vs +1.13 at 30 bps; 4/17 paired wins), better on 42/84-day means but with higher max DD at 42 days (13.4-14.0 vs
12.9-13.5), and pooled paired wins at 50 bps are 10/26 = 38% against the required 60%. The 56-day gain seen in the
sweep does not carry across fold geometries, so it is path noise rather than an edge. Live constant stays 0.35.

Across hold time, stops, smoothing, sizing, reserve, slots, cooldown and a new ranker, every candidate that looked
better in one slicing of the 236 days failed a second slicing. Further search on this fixture is not informative;
new evidence has to be forward data (see `research/forward/`).

Forward evidence: `research/forward/collect.sh` (local cron, daily 01:20 UTC) appends the production raw and smoothed
scores (`data/forward/scores.jsonl`) and the trailing hourly history from the remote (read-only ssh). From
2026-10-01 these are unseen days; once ~60 accumulate they extend the fixture for a true out-of-sample test of the near
misses (EMA 0.25, 24h hold). Nothing on the remote was changed for this.
