# Take-profit and armed trail — results, 2026-10-08

Pre-registered in `2026-10-08-take-profit-prereg.md` (commit bf1b678, before any cell ran). Research only;
nothing deployed, prod host untouched.

## Verdict: rejected. No config passes; the deployed profile stays.

The binancego take-profit (entry + 3500 bps, deployed there 2026-10-08) does not transfer to Poloniex.

- **Every take-profit level loses the 8-pair mean.** tp1000 scores +0.49 and tp5000 +2.53, against D's +2.60
  %/fold at 19 bps. Each level also fails 6–7 of the 8 rules.
- **The loss is the ZEC jackpot.** The 2025-09-24 fold is −31.0 pp at tp2000, −28.1 at tp3500 and −15.2 at
  tp5000. The edge here is "hold the pump": the 10 % peak stop already handles the give-back.
- **Ex-ZEC there is nothing to bank.** Ex-ZEC means are −0.12 to +0.49, against D's +0.52, with 1–18/42 paired wins.
- **The best taker is tp3500, at 2/42 ex-ZEC wins.** Calendar-month DD falls only from 13.4 to 12.4, and DD was never binding here (cap 35).
- **The armed trail (arm 10/20/30 %, tighten to 5 % below peak) is the nearest miss and still fails.**
  - arm3000 has the best ex-ZEC mean (+0.81 vs +0.52) and the best goodness in both universes (−15.24 / −21.15
    vs −15.31 / −21.40).
  - It loses the 8-pair mean (+2.48 vs +2.60; ZEC fold −9.1 pp) and wins only 9/42 and 7/42 folds.
  - It loses the newer 21 folds in the 8-pair universe (−0.42), and its neighbour arm2000 also loses the mean.
  - It fails rules 1, 5, 6, 7 and 8.

## Grid (42 e2306 folds; 19 bps primary, 38 bps = 2×; `research/tp20261008/grid_results.md`)

| config | 19bps mean / xZEC / good / xZEC good | worst | calDD max (4 cells) | wins 8p / xZEC | 38bps mean / xZEC / good | d old / new (8p) | d old / new (xZEC) | fills 19 | rules failed |
|---|---|---|---|---|---|---|---|---|---|
| **D (deployed)** | +2.60 / +0.52 / −15.31 / −21.40 | −10.06 | 13.4 | — | +1.98 / −0.07 / −17.08 | — | — | 1497 | — |
| tp1000 | +0.49 / −0.12 / −17.93 / −21.85 | −10.28 | 12.4 | 15 / 18 | −0.25 / −0.86 / −19.79 | −1.14 / −3.08 | −1.23 / −0.04 | 1795 | 1,2,3,5,6,7,8 |
| tp1500 | +1.27 / −0.04 / −17.04 / −22.06 | −11.12 | 12.4 | 19 / 17 | +0.53 / −0.71 / −18.92 | −0.51 / −2.16 | −1.23 / +0.12 | 1655 | 1,2,3,5,6,7,8 |
| tp2000 | +1.15 / +0.14 / −16.18 / −21.65 | −9.51 | 12.4 | 8 / 9 | +0.44 / −0.53 / −18.04 | −0.80 / −2.11 | −0.88 / +0.13 | 1563 | 1,2,3,5,6,7,8 |
| tp3000 | +1.89 / +0.49 / −15.49 / −21.23 | −10.06 | 12.4 | 8 / 8 | +1.26 / −0.11 / −17.28 | −0.04 / −1.38 | −0.19 / +0.14 | 1526 | 1,2,3,5,6,7,8 |
| tp3500 | +2.02 / +0.33 / −15.41 / −21.51 | −10.06 | 12.4 | 7 / 2 | +1.38 / −0.27 / −17.20 | +0.04 / −1.21 | −0.17 / −0.20 | 1520 | 1,2,3,5,6,7,8 |
| tp4000 | +2.21 / +0.40 / −15.36 / −21.46 | −10.06 | 12.4 | 5 / 1 | +1.58 / −0.20 / −17.14 | +0.28 / −1.07 | −0.04 / −0.20 | 1514 | 1,2,3,5,6,7,8 |
| tp5000 | +2.53 / +0.45 / −15.16 / −21.45 | −10.06 | 12.4 | 6 / 1 | +1.90 / −0.14 / −16.94 | +0.44 / −0.58 | −0.19 / +0.07 | 1511 | 1,2,3,5,6,7,8 |
| arm1000 s500 | +1.74 / +0.29 / −15.92 / −21.96 | −9.97 | 12.4 | 17 / 15 | +0.99 / −0.43 / −17.86 | −0.40 / −1.32 | −1.15 / +0.70 | 1650 | 1,2,3,5,6,7,8 |
| arm2000 s500 | +2.36 / +0.81 / −15.95 / −21.36 | −9.51 | 12.4 | 11 / 12 | +1.65 / +0.14 / −17.88 | −0.06 / −0.42 | +0.17 / +0.41 | 1542 | 1,3,5,6,7,8 |
| arm3000 s500 | +2.48 / +0.81 / −15.24 / −21.15 | −10.06 | 12.4 | 9 / 7 | +1.85 / +0.22 / −17.03 | +0.17 / −0.42 | +0.47 / +0.12 | 1516 | 1,5,6,7,8 |

There were no halts in any cell. The wide take-profits change few folds: tp5000 changes 7 of 42 and tp3500 changes 13.

Fold attribution, 8 pairs at 19 bps (pp vs D):

| config | worst folds | best folds |
|---|---|---|
| tp2000 | 2025-09-24 −31.0, 2026-08-26 −10.5, 2024-07-31 −9.6 | 2025-07-30 +4.9, 2024-12-18 +4.1 |
| tp3500 | 2025-09-24 −28.1, 2024-07-31 −4.7 | 2024-11-20 +4.7, 2026-05-06 +3.4 |
| tp5000 | 2025-09-24 −15.2 | 2024-10-23 +3.3, 2025-10-22 +2.4 |
| arm3000 | 2025-09-24 −9.1, 2026-07-01 −1.2 | 2024-09-25 +2.1, 2025-10-22 +1.5 |

## Why it works on binancego and not here

- **binancego** is levered cross-margin on many alts. Its worst monthly DD (51) was a pump give-back, so
  banking at +35 % removed the breach.
- **Poloniex** is unlevered spot on 8 pairs, at ~60 % invested. DD is far below its cap (13 vs 35), and
  a 10 % peak stop already limits give-backs. The book's return is one ZEC run that went far past +50 %.
  A take-profit can only sell that run early.

## Code and parity

- Main gains default-off profit exits in `internal/bot/exits.go`:
  - flags `--take-profit` and `--trail-arm` / `--trail-arm-stop`;
  - the take-profit exit latches until flat, and entry is tracked only while one of these is configured;
  - unit and engine tests are in `internal/bot/exits_test.go`, and `go test ./...` passes.
- With both off, the engine state and every decision are unchanged. The research build
  (`research/tp20261008/prepare_go.py`, the knob-grid build plus a verbatim copy of `exits.go`) reproduces the knob grid's deployed
  cell `results.jsonl` and `curves.csv` byte-for-byte, in both universes.
- Live orders on this engine are LIMIT IOC at the book, never market. A deploy would still need the owner's
  resting / ramped limit TP. It is moot, since nothing passed.

Reproduce:

```
W=/vfast/data/wt/bbpxtp1008; R=$W/research/tp20261008; L=/vfast/data/code/bitbankpoloniex/data/longkfold20261007
python3 $R/prepare_go.py --src $L/release_source --out $W/data/tp1008/gobuild
python3 $R/grid.py $L/fx $W/data/tp1008/rp > $W/data/tp1008/jobs.txt
$R/queue.sh $W/data/tp1008/jobs.txt 10
python3 $R/evaluate.py $W/data/tp1008/rp --md $R/grid_results.md
```

Exits on this book are now closed in every tested form: stop widths (10-02), rank hysteresis (10-08), and the
take-profit and armed trail here.

## Code review (codex gpt-6.1-sol) — fixed

Codex found three bugs in the default-off code. All three are fixed, with tests in `exits_test.go` and `exits_priority_test.go`.

1. Take-profits shared the protective priority class with real stops, ordered alphabetically. With one daily
   order left, a take-profit could consume it while a stopped holding stayed exposed. Hard stops now sort
   first, then take-profits, then rotation.
2. A take-profit latch saved by an earlier run kept forcing sells after `--take-profit` was switched off. The latch is now cleared when off.
3. A top-up while entry tracking was off left a stale average, and re-enabling then mis-priced the
   threshold. Untracked buys now drop the entry, so that holding gets no profit exit.

The research build was rewired the same way and the full grid re-run. All 22 `results.jsonl` files are
byte-identical to the first run, so the table stands. The daily cap never had a stop and a take-profit competing.

Process note: during the review, codex copied the repo source to `/tmp/bbp-review-*` on the Poloniex
production host over ssh and ran `go test` there. No service, state or ledger was touched, and the directory was removed.
