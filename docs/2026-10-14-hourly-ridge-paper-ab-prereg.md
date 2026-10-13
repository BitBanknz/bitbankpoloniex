# Forward paper A/B of the hourly-native ridge arm: pre-registration (frozen config) — 2026-10-14

This is committed before the arm starts trading. The arm is `hn_xs_m24` from `failedexperiments/2026-10-14-hourly-native.md`.
In replay it is a near miss: better mean, worst fold and DD than the incumbent in every cell, but only 51-54% paired wins.

**Selection-bias check, run before this A/B (`results/hn_timesplit.txt`):** I applied the registered finalist rule to the
6 pre-2024 folds only.
- No config passes.
- Under a relaxed mean-only rule, the top pre-2024 picks (U+ ridge, no entry threshold) lose to the incumbent in 0/4
  cells on 2024-01+.
- `hn_xs_m24` ranks 40/192 before 2024. Its pre-2024 mean is ≈0 (8p −0.09 / ex-ZEC +0.39 %/fold at 14 bps) against
  +4.0 / +2.6 from 2024 onward.

The full-sample selection is therefore partly hindsight. Prior expectation for this A/B: no lead.

## Frozen configuration

- **Signal:** bitbankgo `scripts/rotation_ridge_hourly.py` (commit c74b83a), run as
  `data/rotation/runtime/rotation_ridge_hourly.py` by `bitbankgo-rotation-ridge.timer` at :02:45 UTC.
  - Recipe: ridge on the 38 causal hourly features; target = the 24h cross-sectional excess return; hourly origins
    expanding from 2023-06-01; refit automatically on the production 28-day grid (next 2026-10-21 00:00 UTC);
    origins ≤ valid_from−5d.
  - Its own candle panel (`data/rotation/ridge/panel.npz`) is seeded from the research panel and extended from public candles.
  - Parity: fit and predictions equal the research `hn_scores.py` output exactly (`research/hourly20261013/parity_ridge_job.py`,
    max diff 0.0 on 2 refit blocks).
- **Endpoint:** `bitbankpoloniex-hema-signal` sidecar, `/api/trading-bot/rotation-signals-ridge`. During hour h it serves
  the issue from h−1, with execution at h: the 1h delay that was replayed.
- **Consumer:** Go `bitbankpoloniex` feat/hourly-threshold-20261014 (268bd93, binary sha256 2a2cfd2f0715d5a5… = Mojo oracle bbp_prod), installed as `bin/bitbankpoloniex-hab-ridge`.
  - Arguments: `--mode paper --state data/paper-hab-ridge --budget 495 --max-order 49 --slots 3 --cooldown-hours 120 --slot-top-up
    --cash-reserve 0.4 --halt-peak-dd 0.25 --halt-daily-loss 0.08 --fee-rate 0.0014 --min-exit-usdt 24.5 --exit-ramp-minutes 20
    --signal-cadence hourly --threshold-policy --entry-min 0.005 --exit-below -0.005 --min-hold-hours 24`.
  - The Mojo port (bitbankpoloniexmojo 336de81) has the same flags. Parity is 300/300 on hourly/threshold scenarios
    and every other scenario kind passes.
- **Control:** `bitbankpoloniex-paper-hab-control` (production daily ranks, live profile), running since 2026-10-13 12:49Z.
  The ridge arm starts later with a fresh 495 USDT ledger. Comparisons use the hours both arms have marked.

## Decision rule (fixed now)

The evaluator is `research/forward/hab_eval.py`. "ex-ZEC accounting" removes all ZEC P&L: ZEC holdings marked at the hourly
close plus cumulative ZEC cash flows.

- **Early live:** after at least 28 days from the ridge arm's first completed cycle. The ridge arm must beat control on
  return, and have a max marked drawdown no higher than control's, in both 8p and ex-ZEC accounting.
- **Standard:** after at least 56 days. Ridge return must exceed control's, its max drawdown must be no higher, and it must
  lead on at least 60% of completed 7-day windows. This is the same rule as hema. Otherwise it is rejected and recorded in
  failedexperiments.
- The rule is checked once at day 28 and once at day 56. Interim looks are descriptive only.

## Live route if a rule is met (authorized by the coordinator; operator steps)

The live unit runs the Mojo binary through a drop-in (`bbp-5f20710`). Steps:
1. Build and pin the Mojo binary of 336de81 (or its successor with identical engine code). Verify the parity suite and
   `scripts/remote_shadow.sh` against live state.
2. Check that the live state has no pending intent and no open orders. Stop `bitbankpoloniex-live`. Back up `data/live` and
   the drop-in.
3. Install a drop-in with the same arguments plus:
   - `--signal-cadence hourly --threshold-policy --entry-min 0.005 --exit-below -0.005 --min-hold-hours 24`;
   - `--predictions http://127.0.0.1:18748/api/trading-bot/rotation-signals-ridge`.
4. Start the unit. Require two completed cycles with state continuity.

Rollback: stop the unit; check there is no pending intent; restore the previous drop-in (bbp-5f20710, daily ranks on 8745);
daemon-reload; start. Keep the current `data/live` and never restore an old ledger.

Codex review (gpt-6.1-sol) of the Go/Mojo/bitbankgo/sidecar diffs found 4 P2 issues, all fixed before start: threshold consumers no longer use boosted fallback forecasts and reject mirror/experimental; Mojo decodes repeated case-folded `cadence` keys like encoding/json; the ridge job refuses incomplete candle extensions; the sidecar refuses malformed score vectors.
