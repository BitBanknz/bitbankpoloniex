# Stage-1 configuration sweep: no promotion

Pre-registered in `2026-09-30-config-sweep-prereg.md`; full 27-row table in
`research/sweep20260930/stage1.txt` (cells: mean / worst fold / positive folds / max DD, percent).
Harness check: slots 3 / 72h / 0.4 reproduces the recorded +13.14 continuous and +2.74 28-day
at 30 bps exactly. Baseline = deployed slots 3 / 120h / 0.4 / halts 25/8.

| config | cont 30/40 | 28d@40 mean/worst/pos | 56d@40 mean/worst/pos | rules 1-5 | wins vs base (28d@40) |
|---|---|---|---|---|---|
| s3 c120 r0.4 (live) | +8.85 / +18.35 | +1.75 / -10.0 / 6 | +2.89 / -11.9 / 3 | - | - |
| s3 c120 r0.3 | +16.05 / +18.38 | +2.26 / -11.7 / 6 | +5.25 / -11.7 / 3 | Y n Y Y n | 5/9 |
| s3 c72 r0.3 | +19.29 / +6.83 | +2.61 / -17.9 / 6 | +5.47 / -13.8 / 3 | n n Y Y Y | 6/9 |
| s4 c168 r0.3 | +14.79 / +12.05 | +2.22 / -11.4 / 6 | +5.19 / -8.3 / 3 | n Y Y Y n | 5/9 |

Result: no config passes all five rules, so the live profile is unchanged and stage 2 (halt sweep)
was not run. Slots 2 is dominated everywhere (fewer positive folds). Slots 4 only helps with 168h
cooldown. Every fold-mean gain comes with a deeper worst fold: raising mean in the 28/56-day cells
by 0.5 to 2.4 points costs 1.7 to 8 points of worst-fold, the same trade seen in the cash-reserve
frontier note. The nearest miss, reserve 0.4 to 0.3 at 120h, wins all four fold-mean cells but
misses on 56-day@30 worst fold (-11.3 vs -8.1) and paired wins (5/9 vs the required 6).

Notes: the baseline's continuous path (+18.35 at 40 bps, above its own 30 bps +8.85) is a single
lucky path and makes rule 1 hard to satisfy for any candidate; a fold-only rule would be a new
registration, not a reinterpretation of this one. 120h vs 72h is not clearly better on folds
(72h r0.4: 28d@40 +2.05 vs +1.75), so the live 120h choice rests on the earlier cooldown study,
not on this replay.
