# Hourly-native rotation algorithm and wider universe: pre-registration — 2026-10-14

Written before any result of this study. Context: on 10-14, hourly execution of the daily rotation recipe lost to the
daily window (`failedexperiments/2026-10-14-hourly-cadence.md`), because rank-driven hourly trades do not
clear costs. W4 also reports that the KuCoin GBDT recipe has no 2024-26 edge on a survivorship-free Binance universe.
Prior expectation: no pass.

## Hypothesis

A model trained for hourly decisions can beat the daily incumbent if it is cost-aware:
- it predicts the 24h-ahead return net of each pair's round-trip cost;
- it enters only when the predicted edge clears an entry threshold;
- it exits when the edge falls below an exit threshold after a minimum hold.

A wider cross-section could help this model.

## Universe (rule fixed now, applied to first-year data only)

- U8 is the production 8 pairs.
- U+ is U8 plus the Poloniex USDT pairs that pass the rule below, chosen from the 33 candidates in
  `research/hourly20261013/build_wide_panel.py`, which were picked by today's 24h volume.
  - Rule, measured over 2023-06-01..2024-05-31 only: listed for the whole period, at least 95% nonzero-volume
    hours, and median hourly quote volume of at least $20k.
  - Take the top 24 by that median.
- Survivorship bias remains, because candidates are pairs listed today. That is why results from 2024-01 onward
  are reported separately.
- Book shapes for the new pairs come from a public 5-level recorder started 2026-10-13
  (`book_recorder.py`). It is thinner and more recent than the 8-pair archive.

## Model family (hourly origins, same refit grid and purge as production)

- Features: the 19 causal raw features plus same-hour ranks (`features_at`), at every hour.
- Targets:
  - `abs24` = open(h+25)/open(h+1) − 1 − round-trip cost(pair);
  - `xs24` = the 24h return minus the same-hour cross-sectional mean.
- Learners: LightGBM regression (depth 3, 200 trees, lr .03, min_child 200, L2 10), and ridge.
- Training: expanding from 2023-06; refit on the production 28-day grid; origins at most valid_from−5d.

## Policy (consumer hooks, research-only until a pass)

- Score = predicted edge.
- Entry: score ≥ θ_in (θ_in = margin over 0, since the cost is already in `abs24`), among the top `slots`.
- Exit: after `min_hold`, when score < θ_out. The 10% trailing stop, the 120h cooldown, the 0.4 reserve and the
  safeguard exits are unchanged.
- Screening grid (fast Python simulator, selection only):
  - universe {U8, U+} × target {abs24, xs24} × learner {gbdt, ridge}
  - × θ_in {0, 50, 100 bp} × θ_out {0, −50 bp} × min_hold {24, 72} × slots {3, 5}.
  - For `xs24` the thresholds apply to the excess-return prediction.
- Screening costs: 14 bps fee + the pair's median half-spread, 1h execution delay, the 42 refit folds.
- Selection rule (fixed): finalists = at most 3 configs. Each must:
  - have positive mean at 33 bps in the screen;
  - beat the screen's own run of the incumbent-like policy (top-3 daily on the production ranks) on mean
    and worst fold, ex-ZEC included;
  - be ranked by ex-ZEC mean.
  If none qualify, the study stops: rejected.

## Decision (the same gates as W2 round 1)

Finalists run in the Go fidelity harness:
- research hooks `EntryMin`/`ExitBelow`;
- 42 folds × book seeds 1-3, 14/33 bps, 8 pairs (or U+) and ex-ZEC.

The gates:
- G1: better mean and worst fold than the incumbent in every universe and fee cell, with ≥55% paired fold-seed wins.
- G2: worst calendar-month DD ≤ 30%.
- G3: 84-day folds hold the sign.
- Also reported separately: folds from 2024-01 onward.
- G4: final fit on all data.

Only a full pass goes on to endpoint + Go/Mojo consumer + codex review + paper.
