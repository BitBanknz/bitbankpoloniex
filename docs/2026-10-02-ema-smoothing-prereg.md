# Score smoothing constant: pre-registration

Finding: the fixture's `Ranks` are the production forecast job's EMA (`.35*raw + .65*previous`, from
`rotation_forecast.py` on the remote) of per-day z-scored raw model scores; inverting the recursion recovers
raw scores with std exactly 1.0000 and mean 0 on all 236 days, so re-smoothing is exact.

Candidates (one parameter, four values): EMA weight on the new score a in {0.15, 0.25, 0.50, 1.00}
(1.00 = no smoothing; live is 0.35). Same fixture, engine, profile (slots 3 / 120h / reserve 0.4 / halts
25-8, stop 0.90, hold 72h), fees 30/40 bps, continuous / 28d / 56d. Promotion rule is the five-rule test of
`2026-09-30-config-sweep-prereg.md` against the 0.35 baseline (`s3_c120_r0.4_h25_8`). A winner would be
deployed only by changing the constant and its state continuity in the remote forecast job (not the trading
binary), with a rollback that restores `.35` and the stored smoothed scores.

## Result, and a noise calibration registered before it is run

`research/sweep20260930/ema_summary.txt`: no value passes all five rules. a=1.00 (no smoothing) is clearly worse
(28d@40 +0.86 vs +1.75). a=0.25 passes rules 1-4 (28d@40 +2.43, 56d@40 +5.35 vs +1.75 / +2.89, lower DD) and
fails rule 5 (5/9 paired wins); a=0.15 fails rule 3 by one positive fold; a=0.50 fails rule 1 only on the baseline's
anomalous continuous 40 bps path (+18.35, above its own 30 bps +8.85). The live 0.35 sits inside a plateau yet
trails both neighbours, which suggests the baseline is a low draw of a path-dependent engine.

Calibration (not candidates): replay a = 0.20, 0.30, 0.40 with the same harness. Interpretation fixed now:
if both 0.30 and 0.40 reach 28d@40 mean >= 2.2 the 0.35 baseline is an outlier and smoothing changes are not
supported (regression to the mean); if both stay <= 2.0 there is a real gradient between 0.35 and 0.25 and a=0.25
gets a confirmation test on 14/42/84-day folds at 30/50 bps with the same four rules and 60% pooled-wins bar as
the hold-time confirmation. Either way nothing deploys without passing a registered rule.

## Calibration outcome and confirmation registered before it is run

`research/sweep20260930/ema_summary_full.txt`. a=0.30 gives 28d@40 +1.87 and a=0.40 gives +2.10: neither of the two
registered branches (both >= 2.2, both <= 2.0) holds, so the calibration is ambiguous. Across all values 28d@40 is
+0.86 (1.00), +2.37 (0.50), +2.10 (0.40), +1.75 (0.35, live), +1.87 (0.30), +2.43 (0.25), +2.23 (0.20), +2.43 (0.15);
56d@40 steps from +3.3-3.6 (a >= 0.30) to +5.0-5.35 (a <= 0.25), with only 5 folds in that geometry.
Resolution: take the stricter branch. Confirm a=0.25 against the live 0.35 on 14/42/84-day folds at 30 and 50 bps
(baseline already run: `data/exit_20261002/conf_st0.9_mh72`), confirmed only if mean beats baseline in all six cells,
max DD is no higher in any cell, worst fold is within 2 points, and pooled paired wins at 50 bps are >= 60%.
