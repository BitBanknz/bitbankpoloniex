# Protective clock ablation: actual-hour keys without minute selling

This private candidate keys protective sells for non-imported positions to the
actual observed UTC hour, independently of the forecast's execution hour. It
retains the existing one-successful-sell-per-symbol-per-hour limit and ordinary
decision suffix. The previous minute candidate also allowed later-minute sells
within an hour; this ablation separates that added frequency from the clock rule.

Against the guarded control, return improved in 10 of 45
historical accounts, worsened in 2, and was equal in
33. Drawdown improved in 8 and worsened in
4; the largest increase was
0.910372 percentage points. Against the minute
candidate, the clock-only return was higher in 0, lower in
3, and equal in 42. These are reused,
correlated windows and cost arms, not independent holdout results.

No live deployment is qualified by this experiment. The source and research
protocol were fixed before running this arm, following
[the ablation preregistration](2026-09-26-protective-clock-prereg.md).

## All registered historical groups

Values in each sequence are **guarded control → clock-only → minute selling**.
Reset groups retain their partial final accounts. Individual account drawdown
worsening can be hidden by a group's largest drawdown; the complete paired
differences are retained separately.

| Horizon | Fee, bps/side | Accounts | Mean return: control → clock → minute | Largest account drawdown: control → clock → minute |
| --- | ---: | ---: | ---: | ---: |
| Continuous | 30 | 1 | 8.8520% → 8.8520% → 8.8520% | 12.9798% → 12.9798% → 12.9798% |
| Continuous | 40 | 1 | 18.3502% → 18.3502% → 18.3502% | 13.3214% → 13.3214% → 13.3214% |
| Continuous | 60 | 1 | 13.8338% → 13.8338% → 13.8338% | 13.7985% → 13.7985% → 13.7985% |
| 28 days | 30 | 9 | 2.3109% → 2.3210% → 2.3307% | 12.3826% → 12.3826% → 12.3826% |
| 28 days | 40 | 9 | 2.0876% → 2.1004% → 2.1102% | 12.6542% → 12.6542% → 12.6542% |
| 28 days | 60 | 9 | 1.6342% → 1.6530% → 1.6627% | 13.1936% → 13.1936% → 13.1936% |
| 56 days | 30 | 5 | 3.9804% → 3.9804% → 3.9804% | 12.6885% → 12.6885% → 12.6885% |
| 56 days | 40 | 5 | 3.6247% → 3.6247% → 3.6247% | 12.9732% → 12.9732% → 12.9732% |
| 56 days | 60 | 5 | 2.9271% → 2.9271% → 2.9271% | 13.3861% → 13.3861% → 13.3861% |

The clock-only arm has identical economic fills to the control in
33 accounts and to the minute arm in
42. Client IDs are excluded only for
this economic-fill comparison; every arm's complete decision IDs were checked
by the independent accounting reference.

Only three comparisons differ economically between clock-only and minute
selling, all from the same April 16 ZEC episode at the three fee levels. The
minute arm earned more in those cases, by up to
0.087499 percentage points, and also had
higher drawdown in those same three comparisons. The other 42 economic paths
were identical. Thus the extra selling frequency did not explain the other
changed accounts in the earlier experiment. All clock-only/control first
differences remain concentrated in three ZEC episodes (April 16, May 12 and
June 18), not twelve independent opportunities.

[Three-way return/drawdown chart](/vfast/data/trading_research_20260924/poloniex_protective_clock_v1/historical_accounts/clock_ablation.png) and
[all paired accounts, fees, fills and first differences](/vfast/data/trading_research_20260924/poloniex_protective_clock_v1/historical_accounts/three_way_accounts.json).

## Behavior and accounting verification

The native suite passed 103 tests, the native race suite passed 103, and vet
passed. There were 278 valid complete-cycle accounting checks, each repeated
under the race detector: 254 core cases plus 24 unavailable-to-available forecast
arrival cases. Prior-cycle, equity-mark, position-entry and fill timestamps were
checked for causality in every before/after state. A fresh process respected the
persisted decision key after reloading the ledger.
An independent nanosecond-precision audit checked all 553 non-null states and
rejected four mutations that moved a prior-cycle, equity, entry or fill timestamp
just one nanosecond into the future.

Two concrete failures of the old clock were reproduced. A pre-execution sell
could consume the following execution-hour key and suppress that later hour's
reduction. Separately, losing or receiving a forecast within the current hour
could switch the key between actual and future hours, allowing another sell.
The clock-only candidate allows one actual-hour reduction in both situations.
Consecutive minute calls do not enable extra reductions. Hour/day boundaries,
full exit and cooldown, imported and ordinary exits, depth, spread/stale/missing
quotes, daily caps, risk halts and incomplete valuation were checked.

All 45 default-off historical reports and full ledgers were byte-identical to
the sealed guarded-release baseline. Native control ledgers were also identical
across the two experiments. The independent Decimal audit made
122,971 exact comparisons, with maximum reported metric
error 0. A corrupted decision ID was rejected.
All 904 candidate symbol/hour sell groups contained
at most one successful sell.

The observed-book replay covered all three fees on fixed source indices 78–3297
with each arm's own continuing state: 19,320 native account executions and 9,660
paired comparisons. Every treatment state and financial output matched its
guarded control. The prefix had no protective stops, so this is compatibility
evidence and does not demonstrate a performance benefit for the new rule.

## Limits and decision

Both the historical data and the observed prefix were reused, not held out.
The historical driver uses hourly prices and synthetic books, repeats those
quotes during the entry hour, and calls only once per hour outside that window.
It does not capture every real forecast-availability transition, intraminute
price move, replenishment event, queue position or realized fill. Fee stress
does not replace those missing execution observations.

This candidate establishes more consistent decision timing in native tests.
It does not establish durable alpha or the owner's 35% rolling-28-calendar-day /
40% full-window drawdown requirements. Its private flag defaults off and rejects
live mode and fallback mode. Sizing, order/daily caps, protective thresholds,
cash reserve, cooldown, forecasting, training, imported allocations and ordinary
rotation exits were not changed. Existing live processes, account state and
ongoing paper studies were not modified.

Evidence root: `/vfast/data/trading_research_20260924/poloniex_protective_clock_v1`.
