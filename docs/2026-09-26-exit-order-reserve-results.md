# Reserving daily order capacity for exits

**Rejected by the fixed historical screen. No deployment is qualified.** The candidate passed 0/9 complete fee/geometry groups and
99/141 individual checks. A pass requires every group and both controls;
the individual-check fraction is not a probability of success.

**The historical simulation did not exercise the new rule.** Every account used
at most eight orders in any UTC day: 36 of the 45 accounts per arm peaked at six,
and nine peaked at eight. All 45 three-arm ledger triples were byte-identical.
Thus this study offers no historical evidence for profitable reserved exits.
By contrast, the retained real-book paper path used twelve buys in one day;
its small PEPE top-ups exercise an order-budget situation absent from these
hourly synthetic-book histories. This is a concrete simulation coverage gap.

The retained paper path consumed its twelve daily order allowances on buys.
This experiment asks whether keeping three allowances available for later sells
improves the account. The fixed arms are `baseline` (12 total, no reserve),
`cap9` (9 total, no reserve), and `reserve3` (12 total, buys blocked from order
count 9 onward). All successful buys and sells consume the same total allowance.
Ordinary sells can also use the reserved capacity; three reserved orders do not
guarantee full liquidation. This is the preregistered test in
[the protocol](2026-09-26-exit-order-reserve-prereg.md), with no parameter rescue.

The private source starts from the authenticated guarded release. Its stop/top-up
guard remains enabled; its original decision clock remains unchanged. The only
changed parent source is `internal/bot/engine.go`, plus two new native tests.
The reserve defaults to zero and rejects live mode and fallback mode.

## All historical groups

Each value sequence is **baseline / cap9 / reserve3**. Returns and drawdowns are
percentages. Drawdown includes the initially funded 495 USDT and every retained
hourly equity mark. Reset groups retain the partial final account.

| Window | Fee bps/side | Accounts/arm | Mean return % | Largest account drawdown % | Checks passed |
| --- | ---: | ---: | ---: | ---: | ---: |
| Continuous | 30 | 1 | 8.8520 / 8.8520 / 8.8520 | 12.9798 / 12.9798 / 12.9798 | 11/13 |
| Continuous | 40 | 1 | 18.3502 / 18.3502 / 18.3502 | 13.3214 / 13.3214 / 13.3214 | 11/13 |
| Continuous | 60 | 1 | 13.8338 / 13.8338 / 13.8338 | 13.7985 / 13.7985 / 13.7985 | 11/13 |
| 28-day resets | 30 | 9 | 2.3109 / 2.3109 / 2.3109 | 12.3826 / 12.3826 / 12.3826 | 11/17 |
| 28-day resets | 40 | 9 | 2.0876 / 2.0876 / 2.0876 | 12.6542 / 12.6542 / 12.6542 | 11/17 |
| 28-day resets | 60 | 9 | 1.6342 / 1.6342 / 1.6342 | 13.1936 / 13.1936 / 13.1936 | 11/17 |
| 56-day resets | 30 | 5 | 3.9804 / 3.9804 / 3.9804 | 12.6885 / 12.6885 / 12.6885 | 11/17 |
| 56-day resets | 40 | 5 | 3.6247 / 3.6247 / 3.6247 | 12.9732 / 12.9732 / 12.9732 | 11/17 |
| 56-day resets | 60 | 5 | 2.9271 / 2.9271 / 2.9271 | 13.3861 / 13.3861 / 13.3861 | 11/17 |

Against `baseline`, reserve3 had higher return in 0 accounts, lower in 0, and equal in 45. Funded full-window drawdown improved in 0, worsened in 0, and was equal in 45. The largest drawdown increase was 0.000000 percentage points. There were 0 distinct first-divergence timestamp/symbol/side combinations across the reused fee and reset arms.
Against `cap9`, reserve3 had higher return in 0 accounts, lower in 0, and equal in 45. Funded full-window drawdown improved in 0, worsened in 0, and was equal in 45. The largest drawdown increase was 0.000000 percentage points. There were 0 distinct first-divergence timestamp/symbol/side combinations across the reused fee and reset arms.

The largest candidate sampled rolling 28-calendar-day drawdown was 13.193550%;
the largest funded full-window drawdown was 13.798535%. These are checks on
the retained marks, not proof of intrahour risk. The required ceilings remain
35% and 40%, respectively. Group maxima can hide individual regressions;
[every paired return and drawdown difference](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/assessment/individual_differences.json) is retained.

The registered first-divergence checks found no differing historical paths.
They therefore provide no evidence of a reserved sale occurring in history.
The synthetic full-cycle tests exercise the boundary explicitly. Every historical
path with identical fills was required to have an identical complete native state.
[The paired summary](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/assessment/paired_summary.json) lists the distinct
first differences; [all accounts](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/assessment/accounts.json) retain their ledger bindings.
Fee arms and overlapping geometries are correlated reused observations.

| Group | Failed registered checks |
| --- | --- |
| Continuous, 30 bps | baseline:higher_mean, cap9:higher_mean |
| Continuous, 40 bps | baseline:higher_mean, cap9:higher_mean |
| Continuous, 60 bps | baseline:higher_mean, cap9:higher_mean |
| 28-day resets, 30 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |
| 28-day resets, 40 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |
| 28-day resets, 60 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |
| 56-day resets, 30 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |
| 56-day resets, 40 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |
| 56-day resets, 60 bps | baseline:gain_concentration_at_most_80pct, baseline:higher_mean, baseline:two_improving_windows, cap9:gain_concentration_at_most_80pct, cap9:higher_mean, cap9:two_improving_windows |

## Recorded public-market replay

The authenticated prefix 78–3297, 2026-09-24 03:14 through 2026-09-26 08:53 UTC,
was replayed with each arm's own continuing account state. It was already
observed and known to contain no stops. Across 28,980 native cycles, the baseline
matched the original complete outputs and request paths. Reserve3 and cap9 had
identical complete financial paths in all 9,660 paired comparisons, with no sells
and no unmarked cycles. Consequently this prefix cannot establish any benefit
from the additional sell allowance; any difference from baseline is the buying rule.

| Account / fee setting | Arm | Return % | Minute-sampled drawdown % | Buys | Fees USDT |
| --- | --- | ---: | ---: | ---: | ---: |
| control_fee30 | baseline | -0.592454 | 1.080628 | 12 | 0.849727 |
| control_fee30 | cap9 | -0.627038 | 0.942016 | 10 | 0.885127 |
| control_fee30 | reserve3 | -0.627038 | 0.942016 | 10 | 0.885127 |
| control_fee40 | baseline | -0.649675 | 1.081245 | 12 | 1.132970 |
| control_fee40 | cap9 | -0.686643 | 0.942526 | 10 | 1.180169 |
| control_fee40 | reserve3 | -0.686643 | 0.942526 | 10 | 1.180169 |
| control_fee60 | baseline | -0.764116 | 1.082483 | 12 | 1.699455 |
| control_fee60 | cap9 | -0.805852 | 0.998708 | 10 | 1.770253 |
| control_fee60 | reserve3 | -0.805852 | 0.998708 | 10 | 1.770253 |

[Observed summary](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/observed_accounts/summary.json) and
[final native account states](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/observed_accounts/final_states.json).
Sequential public snapshots and modeled IOC fills do not establish real execution.

The first nine buys were identical. Baseline then made three more small PEPE
top-ups on September 25. The restricted arms instead made one larger PEPE
top-up on September 26 after the UTC reset. Fewer orders therefore did not mean
less total exposure: PEPE quantity ended at 19525887 for
baseline versus 22153506 for both restricted arms. Turnover
rose from 283.242445 to
295.042187 USDT. Return was slightly
worse and sampled drawdown lower at all three fees. The
[per-symbol and per-day accounting attribution](/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1/observed_attribution/attribution.json)
reconciles cash, marked inventory, costs and PnL exactly for all nine accounts.

## Verification and synthetic behavior

Native tests: 104 passed; race tests: 104 passed; vet passed. Thirty default-off
complete cycles matched the authenticated baseline. The 256 full-cycle synthetic
accounting cases all passed and were repeated under the race detector with
identical outputs and paths. They cover shallow buying, reserved protective and
ordinary exits, partial reductions, failed buys, daily exhaustion, duplicates,
process restart, imported holdings, stale/missing/wide books, incomplete valuation,
risk halts and UTC reset. Prior-cycle, mark, position-entry and fill timestamps
were checked at nanosecond precision. Four deliberately future-dated timestamps
and two mutated order budgets were rejected.

All 135 historical accounts were independently reconciled using Decimal cash,
position, fee, fill, mark, decision-ID and order-budget calculations. There were
184,425 comparisons, with maximum reported metric error
0. All 45 baseline reports and ledgers matched the
guarded release byte-for-byte. Deliberate total-budget, buy-budget and decision-ID
violations were rejected. This reference consumes recorded intents; it is not a
complete independent planner and does not prove every eligible order was emitted.
Four calendar/precision tests and eleven adversarial selection tests passed,
including 100 seeded drawdown comparisons against an every-pair reference.
Focused Python correctness lint passed; the compact research scripts were not
required to pass Ruff's full style rules.

The synthetic shallow-buy example spends nine allowances before a stop. Reserve3
then sells all three small holdings; both exhausted controls cannot sell that day.
The next price either falls further or rebounds. At 30 bps, account equity is:

| Synthetic continuation | Baseline equity | Cap9 equity | Reserve3 equity |
| --- | ---: | ---: | ---: |
| falling | 465.815712 | 473.111784 | 486.599544 |
| rebounding | 504.215712 | 501.911784 | 486.599544 |

These constructed outcomes demonstrate both reduced downside and forgone rebound
exposure. They are behavior checks, not estimates of profitability.

Two original fixture failures remain preserved. First, the duplicate-cycle test
incorrectly demanded unchanged equity history: a repeated no-fill observation
updates the mark to include the preceding sale's fees. The corrected test checks
unchanged cash, positions, fills, order count and identity, plus the independently
reconciled mark. Second, the synthetic ordinary-exit entry time used a redundant
`.000000000Z` suffix that Go canonicalized to `Z`; the fixture formatter now
matches Go while preserving the exact nanosecond instant. Native treatment code
and accounting formulas were unchanged for both corrections. Their derivations
and original failed runs are included in the evidence.

The original historical audit also failed its final negative-test assumption:
it expected a baseline ledger to violate a nine-order total or buy limit, but
all ledgers stayed below nine. The preserved native replays and unchanged
financial reference were audited again without rerunning the simulations.
Explicit reference mutations then prohibited all orders (total 0) or all buys
(total 12/reserve 12), and both were rejected, as was a corrupted decision ID.
Separately, the already-required native full-cycle boundary-nine mutations were
rejected by the daily-budget checker. All original historical accounts remain
included, their nonactivation is reported, and selection gates were unchanged.

## Decision and limits

Rejected by the fixed historical screen. No deployment is qualified. No favorable fee, reset geometry or reserve size is selected after
the results. Historical books use hourly prices and synthetic depth, reused
during the entry hour; they cannot prove liquidity replenishment, market impact,
queue position, intrahour drawdown or realized fills. Neither the historical
accounts nor the recorded prefix are fresh holdout evidence. Even a screen pass
would require separately fixed unused/prospective evidence and production parity.

Forecasting, training, stop thresholds, sizing, cash reserve and cooldown were
held fixed. This study changed no installed trading binary, live process, account
state, or ongoing paper campaign. Evidence root: `/vfast/data/trading_research_20260924/poloniex_exit_reserve_v1`.
