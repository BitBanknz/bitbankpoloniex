# Knob grid at measured cost — pre-registration, 2026-10-08

Written and committed before any grid cell is run. Research only; nothing is deployed.

## Hypothesis

The deployed knobs (3 slots, 72 h minimum hold, 120 h cooldown, reserve 0.4, slot top-up, max order 49,
halts 25/8) were selected at 30–60 bps per side (09-14 cooldown, 09-24 top-up, 09-30 sweep, 10-07 k-fold at
35/45). Live cost is measured at ~19 bps per side (14 bps TRX-discounted fee + ~5 bps slippage). At that
cost the optimum may have moved toward more trading: more slots, shorter holds, shorter cooldown, less cash.

## Engine, data, costs

- Engine: deployed release source `release-stop-guard-20260930_v3`, research build
  `research/knobs20261008/prepare_go.py` = `research/levers20261008/prepare_go.py` (ExitRank, MinHoldH,
  fee floor 0.0005) plus one inert hook (Validate slot cap 4 → 5) and the 69fc1f2 in-process transport.
  Parity: deployed config at fees 0.0014/0.003 must reproduce `l1008/rp/inc_e2306` byte-for-byte.
- Scores/folds: e2306 (expanding from 2023-06-01, refit every 28 d, EMA 0.35), the 42 refit folds
  2023-08-02 → 2026-10-06 (`fx/e2306.json`); ex-ZEC universe `fx/e2306_xzec.json`.
- Costs: `FeeRate` 0.0014 (measured, **19 bps/side** with the fixture's 5 bps half-spread) and 0.0033
  (**38 bps/side, 2× measured**). Every cell runs both costs and both universes.
- Scorer: fleet goodness `~/code/dashboard-finance/research/goodness/goodness.py`, `--dd-limit 35`.

## Grid (21 configs × 2 universes × 2 costs = 84 fold sets)

Deployed D = slots 3, hold 72, cooldown 120, reserve 0.4, top-up on (everything else fixed: budget 495,
max order 49, 12 orders/day, 12 cycles in the 01:00 hour, halts 25/8, 10 % trailing stop).

| axis | values (D in bold) | deployable by flag? |
|---|---|---|
| slots | 1, 2, **3**, 4, 5 | 1–4 yes (`--slots`); 5 research neighbour only |
| minimum hold h | 24, 48, **72**, 96, 120 | no — hard-coded 72 h, needs a flag |
| cooldown h | 24, 72, **120**, 168, 240 | yes (`--cooldown-hours`) |
| cash reserve | 0.2, 0.3, **0.4**, 0.5 | yes (`--cash-reserve`) |
| slot top-up | **on**, off | yes |
| joint "more trading" cube | slots {3,4} × hold {48,72} × cooldown {72,120} (4 new cells) | |

Not in the grid, with reason: rank cadence (ranks are issued daily; daily is already the maximum, and the
trade-less direction is closed by the 10-08 hysteresis test); entry rank threshold (the engine has no
score threshold, entries are the top `slots`); halts (never trigger in replay, 10-01 halt sweep
byte-identical); trailing stop / exits (closed 10-02 and 10-08); max order (49 is the 10 %-of-budget cap).

## Pass rule (all must hold; primary cost 19 bps unless stated)

1. Mean return %/fold (42 folds, 8 pairs) > D.
2. Ex-ZEC mean %/fold > D.
3. Fleet goodness > D, both universes.
4. Max calendar-month DD ≤ 35 and goodness status PASS in all four cells (2 universes × 2 costs).
5. Paired fold wins ≥ 21/42 in both universes, and worst fold no more than 2 pp below D's worst fold (8 pairs).
6. **2× cost (38 bps):** mean, ex-ZEC mean and goodness (8 pairs) all > D at 38 bps.
7. **Plateau:** every tested one-step grid neighbour of the candidate (along each axis it differs from
   D on, cube included; D itself excluded) also beats D on rules 1 and 2. A candidate with no tested
   non-D neighbour fails, except the binary top-up knob.
8. **More-data split:** fold-paired mean difference vs D > 0 on the older 21 folds (2023-08-02 →
   2025-02-12) and on the newer 21 folds (2025-03-12 → 2026-09-23), in both universes.

If several configs pass, the pick is the one with the largest minimum paired mean difference across
{8 pairs, ex-ZEC} × {19, 38 bps}; no other number is used to choose. If none passes, the deployed
profile stays. Promotion would still need a forward check because these 42 folds were already examined
on 10-07/10-08 and 21 configs are being compared (multiple testing).
