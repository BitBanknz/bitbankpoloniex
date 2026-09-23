# KuCoin-signal mirror for Poloniex — 23 September 2026 (not deployed)

Hypothesis: the bitbankkucoin GBDT (bag 4, depth 3, 400 trees, stride 8, 24 h
target, 240-day window) is the fleet's strongest signal. Restrict its entries to
the 32 KuCoin coins that Poloniex lists with >200k USDT daily volume and run it
spot-only (leverage 1, gross 1, 3 longs, min hold 24 h, DD throttle 0.25).

Sim: bitbankkucoin research binary with `-tradable` (scored universe unchanged,
entries restricted), 20 bps fee + 5 bps slip base, 30+10 stress, 500 USDT.
Two price sources: KuCoin candles, and a mixed panel with the 32 coins' real
Poloniex hourly candles (public API, 2020→2026-09-23).

## 2024-08-13 → 2026-09-10 (continuous, 28-day folds)

| prices | seed | edge / vt | cont. ret / DD | stress ret | 28d mean / worst / max DD / pass35 |
|---|---|---|---|---|---|
| Poloniex | 1 | 120 / 3 | +195 / 24.2 | +133 | +7.9 / −13.7 / 22.0 / 27/27 |
| Poloniex | 2 | 120 / 3 | +313 / 25.7 | +226 | +9.7 / −16.5 / 22.8 / 27/27 |
| KuCoin | 1 | 120 / 3 | +138 / 23.7 | +90 | +6.5 / −10.9 / 22.5 / 27/27 |
| KuCoin | 2 | 120 / 3 | +198 / 24.3 | +126 | +7.3 / −12.1 / 22.9 / 27/27 |

Edge 160 was seed-fragile on KuCoin prices (+188 vs +54). Starting every run at
a 15% pre-existing drawdown (`-start-dd 0.15`) cost ~10% of return, no DD change.

## Rejected on 2026

Same eight 28-day folds 2026-01-14 → 2026-09-08 that the incumbent live engine
replay covers (`2026-09-18-slot-top-up-results.md`: legacy +1.12% mean, 7/9 positive):

| prices / seed | 30 bps | 30 bps + 10 slip | 60 bps | positive folds |
|---|---:|---:|---:|---:|
| KuCoin s1 | +0.13 | −0.48 | −1.66 | 3/8 |
| KuCoin s2 | +0.95 | +0.30 | −0.99 | 3/8 |
| Poloniex s1 | +0.93 | +0.17 | −1.27 | 4/8 |
| Poloniex s2 | −1.36 | −2.02 | −3.28 | 3/8 |

The 2024-25 edge did not persist into 2026 on the Poloniex-listed majors (the
KuCoin bot itself remains positive in 2026 on its full universe: +37/+65% cont.,
28d mean +7/+9%). Not clearly better than the incumbent → not deployed.

## Code kept (default off)

`--mirror-state <bitbankkucoin paper state.json>` makes the engine follow a
bitbankkucoin paper ledger hourly: targets = ledger positions ≥2% weight
(`BTC-USDT` → `BTC_USDT`), sized to `weight × (budget − reserve)` capped at the
slot target via repeated capped orders, exits as soon as the ledger drops a
symbol (repeatable capped sells within the hour), no cooldown, 30% peak stop
(`--mirror-stop`), ledgers older than `--mirror-max-age` (3 h) pause entries.
`--max-orders-day` exposes the daily cap. Tests: `internal/bot/mirror_test.go`.
The signal side is `bitbankkucoin live -paper -tradable <bases> ...`
(research patch in bitbankkucoin `research/crossvenue20260923/`).

## Correction and legacy re-run (same day)

The tables above came from a research binary that had picked up the other
session's strict `<` split rule (rejected for deployment). Live KuCoin uses the
legacy `<=` rule. Re-run with a legacy build of committed source (sanity: B35
HOLD reproduces +1345.26% exactly), e120 vt3:

| prices / seed | 2024-08→09-10 28d mean / worst / DD / pass | HOLD / stress | 2026 28d @30 bps / +10 slip / positive |
|---|---|---|---|
| KuCoin s1 | +8.2 / −11.7 / 23.4 / 27 | +295 / +222 | −1.62 / −2.22 / 2 of 8 |
| KuCoin s2 | +10.3 / −16.0 / 24.3 / 27 | +420 / +324 | −0.19 / −0.82 / 2 of 8 |
| Poloniex s1 | +7.9 / −15.7 / 23.6 / 27 | +196 / +133 | −1.02 / −1.67 / 3 of 8 |
| Poloniex s2 | +8.2 / −17.3 / 22.4 / 27 | +205 / +134 | −2.36 / −3.00 / 3 of 8 |

Same conclusion: strong 2024-25, negative 2026 versus the incumbent's +1.12%
(7/9 positive). Not deployed.
