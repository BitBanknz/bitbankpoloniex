# Minute protective reductions: tested paper candidate, no deployment qualification

The isolated treatment allows one capped protective sell per actual UTC minute
for a non-imported holding below its existing stop. The guarded control allows
one per forecast decision hour. Successful duplicate calls within a minute keep
the same durable order ID, even if forecast availability changes. Imported
allocations and ordinary rotation exits retain their existing behavior.

The research flag defaults off and rejects live mode and experimental fallback.
The order cap, daily cap, stop threshold, reserve, cooldown, quote validation,
depth participation, forecasts and training are unchanged. This follows the
[fixed protocol](2026-09-26-protective-minute-prereg.md). All changes are in a
private source copy based on the authenticated guarded release.

## All historical outcomes

Across all 45 paired accounts, treatment return was higher in 10,
lower in 2, and equal in 33. Observed
account drawdown was lower in 5 and higher in
7. There were 5
pairs with higher return and no worse drawdown. These are correlated account
windows and fee arms, not 45 independent observations. No losing account or
partial tail was removed. The largest individual account drawdown increase was
0.910372 percentage points; group maxima can hide that worsening.

| Horizon | Fee, bps/side | Accounts | Mean return: control → treatment | Largest account drawdown: control → treatment | Fills: control → treatment |
| --- | ---: | ---: | ---: | ---: | ---: |
| Continuous | 30 | 1 | 8.8520% → 8.8520% | 12.9798% → 12.9798% | 212 → 212 |
| Continuous | 40 | 1 | 18.3502% → 18.3502% | 13.3214% → 13.3214% | 197 → 197 |
| Continuous | 60 | 1 | 13.8338% → 13.8338% | 13.7985% → 13.7985% | 202 → 202 |
| 28 days | 30 | 9 | 2.3109% → 2.3307% | 12.3826% → 12.3826% | 236 → 237 |
| 28 days | 40 | 9 | 2.0876% → 2.1102% | 12.6542% → 12.6542% | 236 → 237 |
| 28 days | 60 | 9 | 1.6342% → 1.6627% | 13.1936% → 13.1936% | 237 → 238 |
| 56 days | 30 | 5 | 3.9804% → 3.9804% | 12.6885% → 12.6885% | 217 → 217 |
| 56 days | 40 | 5 | 3.6247% → 3.6247% | 12.9732% → 12.9732% | 217 → 217 |
| 56 days | 60 | 5 | 2.9271% → 2.9271% | 13.3861% → 13.3861% | 218 → 218 |

All 45 default-off reports and complete ledgers were byte-identical to the
sealed guarded-release controls. The independent Decimal reference checked
both arms, including cash, quantity, fees, dust, peaks, decision IDs, cooldowns,
daily allowances and reported marks: 122,971 exact
comparisons, maximum metric error 0. A corrupted
decision ID was rejected. 33 pairs had identical economic fills after
excluding the treatment's deliberately different client IDs.

All twelve changed accounts first diverged at one of only three underlying ZEC
episodes (April 16, May 12, and June 18). In each, the control's 00:00 protective
sell used the forecast's 01:00 decision key. That blocked the following 01:00
sell; the treatment's actual observation-time key permitted it. This establishes
the first divergence, not the cause of the entire eventual PnL difference.
Actual-hour keying and repeated minute reductions are combined in this treatment;
their separate performance effects have not been isolated. The
[first-difference proof](/vfast/data/trading_research_20260924/poloniex_protective_minute_v1/historical_accounts/first_difference.json)
retains the relevant fills and decision IDs for every changed account.

[Paired return/drawdown chart](/vfast/data/trading_research_20260924/poloniex_protective_minute_v1/historical_accounts/paired_changes.png) and
[all account comparisons](/vfast/data/trading_research_20260924/poloniex_protective_minute_v1/historical_accounts/accounts.json).

The candidate produced 3 symbol/hour
groups with multiple protective sells. In
0 of those groups,
cumulative sold quantity exceeded the modeled 10% allowance of a single quote.
The retained historical driver refreshes the same hourly price and synthetic
depth on each minute call during the entry hour. Actual replenishment was not
observed. These counts describe simulation dependence, not a demonstrated
exchange liquidity violation. Outside the entry hour this historical driver
calls the strategy once per hour, so it does not fully exercise the treatment.

## Native behavior and observed-data comparison

Qualification passed 103 native suite tests, 103 race tests, and vet. There are
240 valid complete-cycle accounting checks, each also repeated using the race
binary. They cover duplicate calls, consecutive capped reductions, full exit
and cooldown, forecast-clock changes, recovered prices, shallow depth, rejected
quotes, exhausted daily limits, risk halts and another holding's missing quote.

During review, twelve original clock-change executions were found to have an
invalid seed chronology: the test clock moved back an hour while the prior
cycle and equity mark stayed in the future. Those executions are retained and
superseded by twelve corrected cases. All corrected before/after state clocks
are causal. Expected sell counts, financial checks, tolerances and the trading
implementation were unchanged. The 240 valid checks exclude the superseded
executions and include their corrected replacements.

The corrected forecast-clock test exposes a separate consequence of the old
hour key: losing a pre-execution forecast within the same minute can change the
decision hour and permit another protective sell. The treatment's actual-minute
key suppresses that duplicate. This is a synthetic native reproduction, not a
claimed live incident.

All three fee controls and treatments were replayed with their own continuing
state across the fixed public prefix 78–3297: 19,320 native account cycles and
9,660 paired cycle comparisons. Every treatment state and financial output
matched its control. The prefix contained no protective stops and provides no
observed-market performance test of faster exits. Its previously reported
returns remain −0.592454%, −0.649675%, and −0.764116% at 30/40/60 bps per side.

Synthetic falling and rebounding paths explicitly show the tradeoff. At 30 bps,
the falling path ended at 489.6153 USDT with the treatment versus 479.5530 with
the control. The rebound ended at 495.3060 versus 510.1530. These deliberately
constructed paths verify behavior and accounting; they are not alpha evidence.

## Decision

Retain this as a tested research candidate. No live algorithm promotion or
activation is justified by this study. The historical fixture is reused,
uses hourly prices and synthetic liquidity, and has no independent holdout.
Fee stress does not establish realistic fills, latency, intraminute prices or
liquidity replenishment. The observed public prefix did not activate the rule.
The owner's 35% rolling-28-day and 40% full-window drawdown requirements remain
unchanged and are not established by this experiment.

Evidence root: `/vfast/data/trading_research_20260924/poloniex_protective_minute_v1`. Existing live code, credentials, trading services,
account state, sealed studies and running paper workers were not changed.
