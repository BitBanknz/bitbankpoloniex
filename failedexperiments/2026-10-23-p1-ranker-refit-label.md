# P1 2026-10-23: ranker refit cadence, refit-phase bag, label horizon / DD weight — rejected

Preregs + results: lee101/bitbankpoloniexmojo branch research/p1-20261023, research/p1_20261023/{PREREG,PREREG_R2,RESULTS}.md.
Harness: research/p1_20261023 (this branch), fidelity replay with in-memory ledger store, byte-identical to the spike20261014 build.
42 e2306 folds x 6 book seeds, archive book, deployed profile, 8p/ex-ZEC, 14/33 bps.

| arm | 8p@14 d pp/fold (t) | 8p Sharpe (inc 0.89) | xZEC@14 d |
|---|---|---|---|
| refit 7 d | -0.07 (-0.2) | 0.87 | -0.05 |
| refit 14 d | +0.18 (+0.7) | 0.96 | +0.03 |
| 4-phase 28 d bag | -0.41 (-1.7) | 0.71 | +0.11 |
| label 48 h | -0.91 (-1.8) | 0.54 | -0.64 |
| label 120 h | -0.12 (-0.4) | 0.81 | +0.21 |
| DD weight 0 | -1.08 (-1.2) | 0.38 | -0.62 |
| DD weight 1.0 | -1.00 (-0.8) | 0.47 | +0.68 |

None passes G1 (mean AND worst AND paired wins AND t >= 2). Seed-bagging the production lambdarank is a no-op (deterministic fit).
Do not redo: these refit cadences, phase bagging, label horizons 48/120 h, DD weights 0/1.0.
