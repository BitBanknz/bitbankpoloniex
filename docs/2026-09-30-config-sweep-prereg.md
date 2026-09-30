# Stage-1 configuration sweep: pre-registration

Frozen fixture `data/frontier_20260912/ledger`, top-up arm only, budget 495, order cap 49,
halts 25%/8%, fees 30/40 bps, geometries continuous / 28-day (9 folds) / 56-day (5 folds),
12 cycles in the 01:00 window. Harness: `research/sweep20260930/`.

Grid (27): slots {2,3,4} x cooldown hours {72,120,168} x cash reserve {0.3,0.4,0.5}.
Baseline is the deployed profile, slots 3 / cooldown 120 / reserve 0.4, run in the same grid
(the earlier top-up replays used the 72h default cooldown, not the live 120h).

Promotion rule, fixed before any result is seen. A candidate must, against the baseline:
1. beat its mean return in all six cells (3 geometries x 2 fees);
2. have worst-fold return no more than 2 points below baseline in each 28/56-day cell;
3. have positive-fold count >= baseline in each 28/56-day cell;
4. keep max drawdown <= 25% in every cell;
5. beat baseline in >= 6 of 9 paired 28-day folds at 40 bps.

Among passers pick the highest mean of (28-day, 56-day) mean returns at 40 bps. No passer: live
profile unchanged. A stage-2 halt sweep {20/6, 30/10, 35/10} runs only on a stage-1 winner.
Caveat recorded up front: 27 candidates on one fixture carries selection bias; rule 5 and the
all-cells requirement are the guard, and any deploy is judged live afterwards.
