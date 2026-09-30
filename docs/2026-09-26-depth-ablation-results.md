# Depth assumptions change the account simulation's coverage

This fixed diagnostic compared the same recorded prices, spreads, market
contracts, forecasts and timestamps under observed depth and deliberately
abundant depth. Changing only displayed quantities changed final return in
9/9 matched accounts. The largest daily filled-order count was
12 with observed depth and 6 with abundant depth.
9/9 policy-pair/fee comparisons under abundant depth
had identical financial paths for the entire prefix. These are simulator
sensitivity results, not evidence of better real trading performance.

The original hourly historical replay stayed at or below eight orders per day,
so it could not exercise a buy boundary at nine. The observed-book path used
twelve buys in one day. This ablation holds prices and decision clocks fixed to
isolate one source of that coverage difference. It does not attribute every
historical/public discrepancy to depth: the two original datasets also differ
in dates, sampling frequency, forecasts and execution observations.

## Fixed comparison

The [protocol](2026-09-26-depth-ablation-protocol.md) was frozen before the new
native replay. The existing compiled guarded engine and its three private order
budget policies were reused: baseline 12 total, cap9 total, and reserve3 with 12
total and buys blocked once nine daily orders have succeeded. Fees remain
30/40/60 bps per side. Every account starts with 495 USDT and retains the 49-USDT
order cap, sizing, stop, cooldown and cash-reserve rules.

The diagnostic quantity floor is ceil(49000 / the smallest price in the current
book), in base units. Every positive quantity below that floor is raised to it;
zeros stay zero. Invalid, stale and unavailable inputs are not repaired. All
nonquantity values remain unchanged. This is an intentionally abundant-depth
counterfactual, not a proposed execution model or a claim of available liquidity.
It uses only the current received packet and has no future-price input.

All values below are **observed / abundant depth**. Drawdown is calculated from
the initially funded equity and retained minute observations. Filled orders
are counted separately from their notional size; unsuccessful attempts are not
inferred from fills.

| Fee bps/side | Policy | Return % | Sampled drawdown % | Filled orders | Largest daily order count |
| --- | --- | ---: | ---: | ---: | ---: |
| 30 | baseline | -0.592454 / -0.586818 | 1.080628 / 1.183907 | 12 / 6 | 12 / 6 |
| 30 | cap9 | -0.627038 / -0.586818 | 0.942016 / 1.183907 | 10 / 6 | 9 / 6 |
| 30 | reserve3 | -0.627038 / -0.586818 | 0.942016 / 1.183907 | 10 / 6 | 9 / 6 |
| 40 | baseline | -0.649675 / -0.646211 | 1.081245 / 1.184609 | 12 / 6 | 12 / 6 |
| 40 | cap9 | -0.686643 / -0.646211 | 0.942526 / 1.184609 | 10 / 6 | 9 / 6 |
| 40 | reserve3 | -0.686643 / -0.646211 | 0.942526 / 1.184609 | 10 / 6 | 9 / 6 |
| 60 | baseline | -0.764116 / -0.764999 | 1.082483 / 1.186015 | 12 / 6 | 12 / 6 |
| 60 | cap9 | -0.805852 / -0.764999 | 0.998708 / 1.186015 | 10 / 6 | 9 / 6 |
| 60 | reserve3 | -0.805852 / -0.764999 | 0.998708 / 1.186015 | 10 / 6 | 9 / 6 |

Abundant depth raised return in 8 comparisons and lowered
it in 1; it increased sampled drawdown in
9 and reduced it in 0.
Thus the model change is not uniformly favorable or conservative. The main
coverage result is that every abundant-depth account completed its buying in
six orders, making the nine-order buy boundary irrelevant on this prefix.

![Account equity by depth assumption](/vfast/data/trading_research_20260924/poloniex_depth_ablation_v1/depth_equity.png)

Curves are merged in the chart only when their complete plotted equity sequences
are exactly equal within the same depth model. The
[full paired return/drawdown and first-fill differences](/vfast/data/trading_research_20260924/poloniex_depth_ablation_v1/audit/comparisons.json)
retain all nine comparisons, including negative differences. The
[coverage matrix](/vfast/data/trading_research_20260924/poloniex_depth_ablation_v1/audit/coverage.json) includes every observed UTC day,
including days with zero orders, and counts days reaching nine, twelve, the
policy's buy boundary and its total allowance. It does not claim that reaching
a boundary proves an additional order was attempted.

## Quote feasibility and policy activation

Across 360 forecast-target observations,
the flat hypothetical 49-USDT order was constrained by displayed depth in
134 observed-book cases versus
0 abundant-book cases. Quote feasibility was
108 versus 112.
The observed hypothetical notional range was
0.099370–48.999999 USDT;
the abundant-depth range was
48.999227–49.000000 USDT.
Depth-limited counts and notional ranges include quotes rejected by other quote
gates. Among quote-feasible observations specifically, depth constrained
30 observed cases and 0 abundant cases.
These quote checks exclude account sizing, holdings, cooldown, reserve and risk
gates. Repeated minutes and fee arms are not independent trading opportunities.
[Every quote comparison](/vfast/data/trading_research_20260924/poloniex_depth_ablation_v1/audit/quotes.json) is retained.

Identical financial paths below mean no observed account effect for that pair
under that depth model. In particular, cap9 versus reserve3 isolates extra sell
capacity after the same buy restriction; equality supplies no reserved-exit
performance evidence.

| Depth model | Fee bps/side | Policy pair | Identical financial cycles | Any account effect? |
| --- | ---: | --- | ---: | --- |
| ample | 30 | baseline vs cap9 | 3220 / 3220 | No |
| ample | 30 | baseline vs reserve3 | 3220 / 3220 | No |
| ample | 30 | cap9 vs reserve3 | 3220 / 3220 | No |
| ample | 40 | baseline vs cap9 | 3220 / 3220 | No |
| ample | 40 | baseline vs reserve3 | 3220 / 3220 | No |
| ample | 40 | cap9 vs reserve3 | 3220 / 3220 | No |
| ample | 60 | baseline vs cap9 | 3220 / 3220 | No |
| ample | 60 | baseline vs reserve3 | 3220 / 3220 | No |
| ample | 60 | cap9 vs reserve3 | 3220 / 3220 | No |
| observed | 30 | baseline vs cap9 | 1322 / 3220 | Yes |
| observed | 30 | baseline vs reserve3 | 1322 / 3220 | Yes |
| observed | 30 | cap9 vs reserve3 | 3220 / 3220 | No |
| observed | 40 | baseline vs cap9 | 1322 / 3220 | Yes |
| observed | 40 | baseline vs reserve3 | 1322 / 3220 | Yes |
| observed | 40 | cap9 vs reserve3 | 3220 / 3220 | No |
| observed | 60 | baseline vs cap9 | 1322 / 3220 | Yes |
| observed | 60 | baseline vs reserve3 | 1322 / 3220 | Yes |
| observed | 60 | cap9 vs reserve3 | 3220 / 3220 | No |

The reusable coverage output makes this nonactivation explicit instead of
treating an unchanged return as an improvement. It is descriptive evidence for
future validation design, not a replacement for out-of-sample strategy gates.

## Verification

Seven adapter tests passed, including 200 seeded price-scale examples, input
immutability, preservation of zero sizes, price/status/clock projection, malformed
data and exact native freshness boundaries. All 256 existing complete-cycle
fixtures matched their original full outputs and request paths in identity
mode. Another 256 abundant-depth complete cycles passed independent money,
nanosecond clock and daily-budget checks, and all 256 were repeated under the
existing race binary with identical full outputs and paths.

No native engine source or binary was changed. The prior 104 native tests,
104 race tests and successful vet run remain authenticated by the sealed parent
study. All nine new account paths cover the full 3220-capture prefix: 28,980 native
cycles. The already-reconciled observed accounts were reused as fixed controls.
A further independent audit reconstructed cash, quantities, fill costs, fees,
source-price marks and equity for all 57,960 observed/counterfactual cycles.
It matched every reported return, drawdown, fill, fee and final position.

The audit checked the quantity floor using exact integer ratios, independently
of the adapter's Decimal division. There were 25,757 changed
book responses and 252,539 raised levels across the fixed
source prefix. Every capture retained the original price and clock projection;
all three fee processes produced identical adapter records. Five coverage tests
check zero-order days, successful-sale counting, day resets, invalid budgets and
same-timestamp quantity differences.
Four additional accounting tests verify hand-calculated buys and partial sales,
rejection of fee/quantity/source-mark mutations, unavailable valuation, and dust
removal without creating cash.

## Scope and decision

The result supports keeping recorded book depth and order-budget coverage in
future account comparisons. Abundant-depth results must not replace observed
results or be used to select a winning strategy. This experiment did not train
a model, tune a strategy, qualify deployment, alter a live account, or change an
ongoing paper campaign.

The source prefix, September 24 03:14 through September 26 08:53 UTC, was already
observed. Its snapshots are sequential, and both models still use hypothetical
IOC fills. Neither displayed depth nor this counterfactual proves matching,
queue priority, replenishment, market impact or intraminute risk. Longer unused
or prospective evidence and production parity remain required for advancement.

Evidence root: `/vfast/data/trading_research_20260924/poloniex_depth_ablation_v1`.
