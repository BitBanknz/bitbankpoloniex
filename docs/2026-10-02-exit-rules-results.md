# Exit-rule sweep and confirmation: not promoted

Registered in `2026-10-02-exit-rules-prereg.md`. Tables: `research/sweep20260930/exit_summary.txt`
(six variants, vs baseline 0.90 stop / 72h hold) and `confirm_summary.txt` (24h hold, new geometries and 50 bps).

Sweep: stops 0.85, 0.93, 0.95 all lose (0.93/0.95 are clearly worse: 28d@40 -0.14 / -1.93 vs +1.75);
hold 120h is no better than 72h; hold 24h beat baseline on every mean cell (28d@40 +2.37 vs +1.75;
56d@40 +4.27 vs +2.89; continuous +19.8 vs +18.4) with lower max DD (10.5-11.4 vs 12.4-16.0) but won
only 5/9 paired 28d folds, so it failed the registered rule 5.

Confirmation (14/42/84-day folds, 30 and 50 bps): mean better in all six cells, max DD no higher in any
cell (8.1-11.1 vs 8.6-13.5), worst fold within tolerance, but pooled paired wins at 50 bps are 12/26 = 46%
(14-day 6/17, 42-day 4/6, 84-day 2/3) against the required 60%. Result: NOT CONFIRMED. The improvement is
carried by a few large folds, not a consistent edge, and the drawdown benefit is the only uniform effect.
Live `min hold 72h` unchanged; no code change was made for it.

Housekeeping found while checking prerequisites: the deployed stop/top-up guard was a build-time
patch to `internal/bot/engine.go` that `main` lacked; its one behavioural hunk (never buy a holding that
is below its stop) is now merged (commit 50a4fca), vet and tests pass. `main` equals the live source plus
default-off mirror mode. Builds use `-buildvcs=true`, so rebuilt binaries will not be byte-identical.
