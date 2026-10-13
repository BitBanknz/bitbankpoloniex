# Resting spike sells, depth haircut and liquidity floor on the daily rotation: pre-registration — 2026-10-14

This was written and committed before any result. It is round 4 of W2, prompted by the owner's input.

Harness: `research/spike20261014`, the 10-09 fidelity replay (archive books, 14/33 bps, 42 folds, book seeds 1-3,
8 pairs and ex-ZEC) plus three default-off hooks. With every hook off it reproduces the incumbent; this is checked as `parity_inc_b1`.

1. **Resting close-side spike sell.**
   - Each hour every holding carries a limit sell at open·(1+K·sd). sd is the population std of the prior W hourly
     open-to-open log returns, so the order is re-placed every hour.
   - It fills at the limit only when the hour's high trades through it by 10 bps (`SpikeTT` .001), and only for holdings
     held since before that hour. Intrahour ordering is unknown.
   - Fee 14/33 bps. The sale triggers the normal post-sale cooldown.
   - Grid: K {2,3,4,6} × W {24,168}.
2. **Depth haircut.**
   - The archive book size is scaled by `DepthMult` {0.25, 0.1}, or by 0.02 for ZEC only (`z02`).
   - W7 measured live fill ratio 0.51 against 0.98 in sim, with ZEC at 01:00 at 1/49 USDT.
   - The calibrated book is the haircut whose sim notional fill ratio for the incumbent is closest to 0.51.
     Every arm is re-scored there: the incumbent, the hema and ridge paper arms, and the best spike and liquidity arms.
3. **Liquidity floor.** 24h quote-volume floor `MinVolume` {3M, 8M} USDT, or a static drop of the two widest-spread pairs
   (SUI, PEPE; archived median spreads of 109 and 52 bp, PEPE 341 bp today).

## Gates

These are the same as rounds 1-3.
- G1: better mean and worst fold than the incumbent in all 4 cells (8p/ex-ZEC × 14/33 bps), with ≥55% paired fold-seed wins.
  It must hold both on the default book and on the calibrated haircut book.
- G2: worst calendar-month DD ≤ 30%.
- G3: 84-day folds keep the sign.

A pass goes to the Go and Mojo consumer, parity, codex review, paper, then live with rollback.
- For spike sells, a pass also requires a recent-month 1m-data check that the hourly trade-through rule does not
  overstate fills.
- The haircut re-score is a measurement, not a candidate. If the calibrated book reverses a ZEC conclusion
  (ex-ZEC vs 8-pair ranking of arms), that is reported.
