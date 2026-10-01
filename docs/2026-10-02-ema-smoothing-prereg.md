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
