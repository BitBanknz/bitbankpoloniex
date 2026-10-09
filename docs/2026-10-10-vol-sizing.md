# Volatility-scaled slot sizing (KuCoin port) — 2026-10-10

Research only. Nothing deployed; no remote host, service, ledger or model touched.
Branch `research/volsize-20261010`.

## Verdict: rejected

- **Vol targeting loses.** On the 42-fold Go-engine k-fold (deployed + safeguard profile, measured
  14 bps fee, archived books, 3 book seeds), every vol arm costs **−0.8 to −1.6 pp/fold** on 8 pairs
  (t −1.9 to −2.7, 41–72/126 wins), at both 14 and 33 bps. Most of the loss is jackpot exposure:
  the 2025-09-24 ZEC fold goes from +37.4 % to +1–9 %, and the 2026-08-26 fold goes from +22.7 % to
  +6–21 %. Ex-ZEC the gains are noise (+0.03 to +0.34 pp, |t| ≤ 1.2), and they come only from the
  second half of the folds. On block B (Binance majors, 49 folds) all 7 vol arms lose (−0.07 to −0.29 pp).
  Vol targeting lowers calendar-month DD (8.9–12 % vs 12.7 %) by holding less. The cash reserve
  already provides that, and so do the closed lower-exposure knobs.
- **Leverage on low-vol names (max weight 1.5) does not help either.** That was the KuCoin mechanism
  (w1.5 / vt0.5). On spot with a 0.4 reserve, a 1.5× slot only takes cash from the next entry. It is
  worse than w1.0 at vt 0.8 and 1.2.
- **The DD throttle alone (ddt 0.15/0.2/0.3, floor 0.25) is a tails lever, not a PnL lever.**
  - 42 folds: −0.17 to −0.31 pp on 8 pairs (t −1.2 to −2.1) and +0.03 to +0.14 ex-ZEC (t ≤ 0.9).
    Worst fold, goodness and cal DD are better in every universe.
  - Block B: about 0 (−0.01 to +0.03 pp), with a better worst fold and better goodness.
  - 84-day folds: **−1.5 to −1.7 pp/fold on 8 pairs (t −2.1)**, because the throttle is still
    engaged when the 2025-08-27 ZEC rally starts (+6.0 % → −4.3/−5.0 %).
  - It fails the "mean clearly better" gate. Like reserve 0.5 and cooldown 168 (10-09), it wins
    goodness by holding less.
- Production stays on the deployed profile. The flags stay default-off on this branch, and no deploy is
  prepared.

## Port

`internal/bot/volsize.go`. All of it is off by default, and with the flags off the engine reproduces
the 10-09 incumbent byte for byte (`curves.csv` matches in 6/6 seed × universe cells).

- `--vol-target T --vol-max-weight W --size-vol rms|24|168` scales each rotation slot target (the
  new-entry cap and the top-up goal) by `min(W, T/vol)`. `vol` is the annualized population std of
  hourly log closes, and rms = √((v24²+v168²)/2), as in KuCoin `-size-vol rms`. It is read from
  `Client.History` (169 completed candles) and cached per symbol per UTC hour. It fails closed: no
  buy for a symbol without a valid vol.
- `--dd-throttle D --dd-floor F` multiplies the target by `max(F, 1 − dd/D)`, where dd is measured
  below the ledger high-water mark.
- Only buys are sized. A holding is never trimmed when its target falls, the same as KuCoin's hold
  rule. The flags are exclusive with mirror mode. Every order is still a capped LIMIT/IOC.
- Tests are in `internal/bot/volsize_test.go`: estimator, validation, scaled top-up goals (off,
  half, 1.5× cap, DD), the candle cache, and fail-closed.

## Setup

- Harness `research/volsize20261010/`, which is the 10-09 fidelity harness plus a causal
  `/markets/{sym}/candles` endpoint fed from full panel history (`candles.py`). It only serves
  candles with `endTime` < replay now.
- Profile: 3 slots, budget 495, max order 49, reserve 0.4, top-up, 120 h cooldown, 72 h hold,
  halts 25/8, min-exit 24.5, exit ramp 20 min, `FeeRate` 0.0014 (also 0.0033 as a 2× cost check),
  archived Poloniex book shapes, book seeds 1–3.
- Folds: the 42 e2306 refit folds (2023-08 → 2026-10), with ZEC and without it.
- Block B (replication) uses the bitbankgo forecast-quality Binance-majors archive (ADA AVAX BTC DOGE
  ETH SHIB SOL XRP) and its deployed-recipe walk-forward scores (`fq-out/B/base_D.npz`), converted by
  `block_b.py` + `make_fixture.py`. It has 49 folds from 2022-04 to 2025-12, proxy books (no archived
  Binance-pair books) and the same 14 bps fee. The incumbent has almost no edge there (+0.34 %/fold),
  so this block tests tails more than alpha.
- Scaling: the 42 folds merged into 14 × 84-day folds (`fx84*.json`), for inc, ddt0.15, ddt0.2 and
  vt1.2_w1.0.
- Arms ddt0.15 and ddt0.3 were added after reading seed 1, where ddt0.2 was the only near-tie.

## Paired table (14 bps; full tables with 33 bps, half splits and attribution in `research/volsize20261010/results*.md`)

d = paired mean difference vs inc, pp/fold (t over fold × seed; wins). The gate needs a clearly
better mean, worst-fold calendar-month DD ≤ 35 %, and a worst fold that is no worse.

| arm | 8p mean / worst / good / calDD | 8p d (t) | xZEC mean / good | xZEC d (t) | block B mean / worst / good | B d (t) | 84d 8p d (t) |
|---|---|---|---|---|---|---|---|
| inc (deployed+safeguard) | +2.05 / −11.76 / −18.78 / 12.7 | — | +0.17 / −21.92 | — | +0.34 / −11.52 / −20.88 | — | — |
| vt0.5 w1.0 | +0.63 / −8.42 / −16.59 / 8.9 | −1.42 (−2.6) | +0.27 / −18.17 | +0.11 (+0.4) | +0.09 / −11.51 / −20.54 | −0.25 (−0.6) | |
| vt0.5 w1.5 | +0.93 / −10.73 / −17.38 / 10.5 | −1.12 (−1.9) | +0.44 / −18.40 | +0.27 (+0.9) | +0.14 / −12.65 / −21.30 | −0.20 (−0.4) | |
| vt0.8 w1.0 | +1.02 / −9.92 / −17.75 / 10.3 | −1.03 (−2.2) | +0.19 / −20.05 | +0.03 (+0.2) | +0.12 / −11.35 / −20.63 | −0.22 (−0.8) | |
| vt0.8 w1.5 | +0.47 / −11.01 / −18.82 / 12.3 | −1.58 (−2.7) | +0.26 / −19.55 | +0.09 (+0.3) | +0.18 / −13.34 / −21.91 | −0.16 (−0.4) | |
| vt1.2 w1.0 | +1.24 / −10.85 / −18.52 / 11.4 | −0.82 (−2.0) | +0.24 / −21.29 | +0.08 (+1.0) | +0.27 / −11.44 / −20.83 | −0.07 (−0.4) | −0.58 (−1.7) |
| vt1.2 w1.5 | +0.46 / −11.23 / −19.56 / 14.2 | −1.60 (−2.7) | +0.50 / −20.22 | +0.34 (+1.2) | +0.24 / −17.26 / −24.65 | −0.11 (−0.3) | |
| vt0.8 w1.5 size-vol 168 | +0.50 / −12.20 / −19.37 / 12.8 | −1.56 (−2.6) | +0.43 / −20.37 | +0.26 (+0.8) | +0.05 / −15.78 / −23.84 | −0.29 (−0.8) | |
| ddt0.15 | +1.74 / −9.62 / −16.55 / 9.8 | −0.31 (−1.8) | +0.26 / −18.66 | +0.10 (+0.5) | +0.34 / −9.37 / −18.86 | −0.00 (−0.0) | −1.66 (−2.1) |
| ddt0.2 | +1.88 / −9.95 / −16.84 / 10.6 | −0.17 (−1.2) | +0.30 / −19.28 | +0.14 (+0.9) | +0.33 / −9.83 / −19.62 | −0.01 (−0.0) | −1.48 (−2.1) |
| ddt0.3 | +1.75 / −10.52 / −17.73 / 10.8 | −0.30 (−2.1) | +0.19 / −20.55 | +0.03 (+0.3) | +0.37 / −10.51 / −20.18 | +0.03 (+0.2) | |

All arms pass the 35 % cal-DD rule; incumbent cal DD is 12.7 %, so DD was never the binding constraint.

Why it worked on KuCoin and not here:
- KuCoin's gain came from re-spending the risk budget. It had margin (w1.5), and its 35 % DD
  budget was binding.
- Poloniex is spot with 60 % deployable capital. DD sits at 13 %, far below the gate, and the edge is
  in a few high-vol jackpots (ZEC). Vol targeting shrinks exactly those jackpots.
- This agrees with the 10-08 TP cross-pollination result: any rule that caps high-vol upside cuts the
  ZEC fold.

## Reproduce

```
R=research/volsize20261010; W=/vfast/data/trading_research_20261010/volsize; P=/vfast/data/code/bitbankpoloniex/data/longkfold20261007
python3 -I $R/candles.py $P/panel.npz $W/candles.json.gz
python3 -I $R/prepare_go.py --out $W/gobuild
python3 -I $R/grid.py $W/rp > $W/jobs.txt && BIN=$W/gobuild/replay.test $R/queue.sh $W/jobs.txt 12
python3 -I $R/block_b.py /vfast/data/wt/td-venv/rep/archive /vfast/data/wt/fq-out/B/base_D.npz $W/blockb
python3 -I research/longkfold20261007/make_fixture.py --panel $W/blockb/panel.npz --scores $W/blockb/scores.npz --out $W/blockb/fx_b.json
python3 -I $R/candles.py $W/blockb/panel.npz $W/blockb/candles_b.json.gz   # block B jobs: Book proxy, CANDLES=$W/blockb/candles_b.json.gz, out $W/rpb/<arm>_b0
python3 -I $R/evaluate.py $W/rp --parity /vfast/data/trading_research_20261009/fidelity/rp --block-b $W/rpb --md $R/results.md
python3 -I $R/evaluate.py $W/rp84 --fees 0.0014 --arms inc,ddt0.15,ddt0.2,vt1.2_w1.0 --md $R/results_84d.md   # fx84 = e2306 folds merged x3
```

Limitations:
- The folds were already examined on 10-07/08/09.
- Block B has proxy books and no edge.
- Vol uses close-to-close returns of the panel, which match the venue candles that the live path
  would read.
