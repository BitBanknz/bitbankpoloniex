# Exit-rule sweep: pre-registration

Untested hardcoded exit knobs in `internal/bot/engine.go`: trailing stop 0.90 of peak bid
(`stopFraction`) and 72h minimum hold before a non-target holding is rotated out. One-at-a-time
variants against the live profile (slots 3 / 120h / reserve 0.4 / halts 25-8), frozen fixture,
fees 30/40 bps, continuous / 28d / 56d, harness `research/sweep20260930/prepare_exit.py`:
stop 0.85, 0.93, 0.95; minimum hold 24h, 48h, 120h (six runs; baseline `s3_c120_r0.4_h25_8`).
Promotion rule identical to `2026-09-30-config-sweep-prereg.md` (all six mean cells beaten, worst
fold within 2 pts, positive folds >= baseline, DD <= 25%, >= 6/9 paired 28d wins at 40 bps). A
combination of two passing singles would be registered separately before running.
A BTC 50d/200d regime gate was built and dropped before any run: BTC was below one of the two
averages on 222 of 244 days of the fixture window, so the gate reduces to holding cash and carries
no information about forward regimes. Live change, if any, needs a build-time engine patch as for
the stop guard, so a winner would also need its own qualification package.

## Result of the six runs, and confirmation registered before it is run

`research/sweep20260930/exit_summary.txt`: no variant passes all five rules. `stop 0.90 / minhold 24h`
passes rules 1-4 (beats baseline mean in all six cells; worst fold -9.0 vs -9.7 and -7.0 vs -8.1; max DD
10.5-11.4 vs 12.4-16.0) and fails rule 5 (5/9 paired 28d wins at 40 bps). Stops 0.85/0.93/0.95 lose; 48h is
weaker than 24h and 120h is no better than baseline.

Confirmation (registered now, run once): baseline (0.90/72h) versus 0.90/24h, same fixture, fees 30 and
50 bps, geometries 14-day (17 folds), 42-day (5-6 folds) and 84-day (2-3 folds); these folds and the 50 bps
cost were not used to pick 24h, though they re-slice the same 236 days (not independent data).
24h is confirmed only if: (i) mean return beats baseline in all six cells; (ii) it wins >= 60% of paired
folds pooled over the three geometries at 50 bps; (iii) max DD no higher than baseline in any cell;
(iv) worst fold within 2 points of baseline in every geometry. Confirmed or not, a live change still needs a
reviewed code change (a `--min-hold-hours` flag defaulting to 72), the full test suite, a qualification
package like the stop guard's, and an authenticated deploy; absent confirmation nothing is deployed.
