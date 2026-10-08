# Placebo ranks, measured costs and rank-hysteresis exits — 2026-10-08

Research only. Nothing deployed; no remote host, service, ledger or model touched.

## Verdict

- **Do not turn the bot off.** On the 42-fold long-history Go-engine k-fold (2023-08-02 → 2026-10-06,
  deployed profile, e2306 scores) the ranker beats a 20-seed random-rank placebo on every seed, both
  costs, with and without ZEC. Fold-paired against the placebo mean it wins 30/42 folds (+2.36 pp/fold,
  t 1.99) with ZEC and 24/42 (+0.66 pp, t 1.10) ex-ZEC. Its main contribution is avoiding bad folds:
  worst fold −10.1 % vs a placebo average of −18.5 %.
- **At the measured cost the incumbent is better than the 10-07 doc reported.** That doc ran the
  engine at 30/40 bps fee + 5 bps half-spread (35/45 per side), roughly twice the measured 18–20 bps.
  At 14 bps fee + 5 bps half-spread (19 per side) the incumbent is **+2.60 %/fold** (was +2.02),
  goodness −15.31, max calendar-month DD 12.9 %; ex-ZEC **+0.52 %/fold** (was −0.04).
- **Rank-hysteresis exits (keep a holding while it is in the top 4/5/6) are rejected.** They cut
  turnover but lose 0.9–1.4 pp/fold with ZEC (13–15/42 wins, worse goodness at both costs); ex-ZEC
  the differences are noise (|t| ≤ 1.2) and goodness is still worse. Live stays: exit when a held
  name leaves the top 3 after the 72 h minimum hold.
- No promotion. The edge is real but thin; the honest expectation ex-ZEC at measured cost is about
  +0.5 %/28 d on ~60 % invested capital.

## Setup

- Engine: the deployed release source (`release-stop-guard-20260930_v3`), built by
  `research/levers20261008/prepare_go.py`. It adds three research hooks to the longkfold build, all inert
  at their defaults: an exit keep-set of the top `ExitRank` names, a driver-set minimum hold, and the
  `Validate` fee floor lowered from 0.003 to 0.0005 so the measured 14 bps TRX-discounted fee can be replayed.
- **Parity:** at the default config and fees 0.003/0.004 the build reproduces
  `data/longkfold20261007/rp/e2306` byte-for-byte (`results.jsonl` and `curves.csv`).
- Profile: budget 495, max order 49, 3 slots, reserve 0.4, top-up, cooldown 120 h, 72 h minimum hold,
  10 % trailing stop, halts 25/8, 12 cycles in the 01:00 hour.
- Costs: `FeeRate` 0.0014 (measured) and 0.003 (the 10-07 standard), each plus the fixture's 5 bps proxy half-spread.
- Folds: the 42 refit-validity folds of `fx/e2306.json`; ex-ZEC uses `fx/e2306_xzec.json`. The deployed
  lgbm ranker is deterministic, so replication comes from the 20 placebo seeds, the two costs and the ex-ZEC universe.
- **Placebo** (`placebo_scores.py`): the same issue dates, refit blocks and pairs, with raw scores drawn iid N(0,1)
  per day and pair, then put through the production EMA 0.35 by `make_fixture.py`. This matches the
  persistence and turnover mechanics of real ranks but carries no information. 20 seeds.

## Results

### Real ranks vs placebo (`results/placebo.txt`)

| universe | cost/side | incumbent mean / worst / goodness | placebo mean (sd, range) | placebo worst / goodness | beats placebo seeds (mean, goodness) |
|---|---|---|---|---|---|
| 8 pairs | 19 bps | **+2.60** / −10.06 / −15.31 | +0.24 (0.56, −0.94..+1.43) | −18.45 / −25.21 | 20/20, 20/20 |
| 8 pairs | 35 bps | +2.02 / −10.87 / −16.87 | −0.83 (0.60, −2.23..+0.43) | −19.31 / −27.55 | 20/20, 20/20 |
| ex-ZEC | 19 bps | **+0.52** / −14.66 / −21.40 | −0.15 (0.54, −1.29..+0.63) | −17.61 / −24.88 | 18/20, 20/20 |
| ex-ZEC | 35 bps | −0.04 / −15.30 / −22.75 | −1.08 (0.54, −2.24..−0.34) | −18.47 / −27.03 | 20/20, 20/20 |

The seed-rank z-scores (4.2 and 1.2–1.9) overstate significance, because all placebo seeds share the same
fold-level market noise. The fold-paired test against the placebo mean is the honest one: t 1.99 with ZEC
and t 1.10 ex-ZEC, at 19 bps.

Passive reference (`results/buyhold.txt`): an equal-weight buy-and-hold of the 8 pairs averages +7.5 %/fold,
but its worst fold is −37 % (ex-ZEC +5.3 %, worst −36 %). It fails the 35 % monthly-DD gate at full
investment. It is 2023–24 meme-coin beta (PEPE, SUI), not an alternative strategy; compare
prediction2's rejected idle-ETF sleeve.

### Rank-hysteresis exits (`results/hysteresis_*.md`)

| arm | 19 bps mean / goodness / cal DD | paired vs incumbent (19) | 35 bps mean / goodness | paired (35) |
|---|---|---|---|---|
| incumbent (exit outside top 3) | +2.60 / −15.31 / 12.9 | — | +2.02 / −16.87 | — |
| keep while top 4 | +1.69 / −17.00 / 13.0 | 15/42, −0.91 pp (t −0.89) | +1.16 / −18.44 | 17/42, −0.86 |
| keep while top 5 | +1.47 / −17.77 / 13.2 | 14/42, −1.13 pp (t −1.07) | +0.97 / −19.18 | 18/42, −1.05 |
| keep while top 6 | +1.21 / −18.38 / 13.9 | 13/42, −1.39 pp (t −1.32) | +0.75 / −19.65 | 16/42, −1.27 |
| ex-ZEC incumbent | +0.52 / −21.40 / 11.8 | — | −0.04 / −22.75 | — |
| ex-ZEC top 4 | +0.65 / −21.68 | 19/42, +0.13 (t 0.34) | +0.16 / −22.89 | 19/42, +0.19 |
| ex-ZEC top 5 | +0.85 / −22.06 | 21/42, +0.33 (t 0.78) | +0.49 / −23.15 | 21/42, +0.53 |
| ex-ZEC top 6 | +0.23 / −22.78 | 20/42, −0.28 | −0.19 / −23.95 | 20/42, −0.15 |

Fills fall from 1497 to 1301 (top 4), 1210 (top 5) and 1136 (top 6) over the 42 folds at 19 bps. Rank changes carry information, as the placebo result implies, so holding a name after it leaves the top 3
gives up return. Hysteresis is the "trade less" lever; together with the 120 h hold (09-30) and the 24 h
paper A/B, the trading-frequency direction is closed.

## Reproduce

```
R=research/levers20261008; P=/vfast/data/code/bitbankpoloniex   # 10-07 panel, scores, fixtures, release source
python3 $R/prepare_go.py --src $P/data/longkfold20261007/release_source --out data/l1008/gobuild
python3 $R/placebo_scores.py --like $P/data/longkfold20261007/scores/e2306.npz --seed <s> --out data/l1008/scores/plc<s>.npz
python3 $P/research/longkfold20261007/make_fixture.py --panel $P/data/longkfold20261007/panel.npz --scores data/l1008/scores/plc<s>.npz [--drop ZEC] --out data/l1008/fx/plc<s>[_xzec].json
$R/queue.sh data/l1008/jobs1.txt 8      # lines fixture|outdir|config; config adds "ExitRank":k, "Fees":[0.0014,0.003]
python3 $P/research/longkfold20261007/summarize.py data/l1008/rp inc_e2306 er4_e2306 er5_e2306 er6_e2306 --fees 0.0014,0.003
python3 $R/placebo_summary.py data/l1008/rp inc_e2306 plc [--suffix _xzec]
python3 $R/bh.py $P/data/longkfold20261007/fx/e2306.json 0.0019
```

The run directories are gitignored, under `data/l1008/` of the research worktree.

Limitations: hourly-open proxy books, today's market contracts, and fold-end liquidation. The 42 folds reuse
history that was already examined on 10-07. The deterministic ranker has no model-seed replication.
