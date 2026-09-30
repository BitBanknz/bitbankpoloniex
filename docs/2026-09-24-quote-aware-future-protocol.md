# Fixed future-data comparison: quote-aware entries

Freeze the tested quote-aware candidate and unchanged control before the first
included source capture. Use six flat 495-USDT paper accounts: control and
quote-aware entry selection, each at 30/40/60-bps fees per side. All other
parameters are the preceding preregistered native settings. Do not include the
separate deadband treatment. No tuning or account reset during this interval.

The first index is selected before launch, at least two minutes in the future,
within the existing seven-day Poloniex public recorder. The last index is its
fixed final index 10079. Preserve every intervening source slot, including
failed/missing captures. A missing receipt after 180 seconds becomes an explicit
gap and is never backfilled. No silent restart. Changes to source, executable,
protocol or recorder identity stop the worker. Bound archives to 4 GiB with
32 MiB headroom and require 20 GiB free disk.

This is a **prospectively frozen replay of future observations**, not a claim
that orders were submitted or decisions durably committed at those historical
logical times. Each native cycle uses the collector's completed-batch receipt
time as its logical clock. The inputs therefore existed at the modeled time;
the actual computation/commit clocks are retained separately. No later candles,
quotes or forecasts enter that cycle. The worker may compute a cycle later.

The native paper engine assumes an IOC buy/sell fills its constructed quantity
at its limit price, bounded by the observed book and existing participation
rule. This does not prove real exchange fills, queue position, latency or
liquidity replenishment. Quotes in one batch were requested sequentially. The
two arms receive identical recorded responses. Missing, stale and unavailable
sources remain unavailable; ranks are not carried beyond their expiry. A new
ranked symbol outside the frozen eight-book coverage stops the study for review.
The experiment has no fallback models, private accounts or order endpoint.

Write immutable gzip inputs and full outputs before a hash-chained receipt;
adopt the new states only after that receipt is durable. Keep all six fee/arm
paths. Reconcile every fill's cash, fee and quantity independently with Decimal
arithmetic, including explicit native dust write-offs. Preserve a post-cycle
bid valuation when every remaining position has a valid fresh observed quote;
otherwise report that valuation as unavailable. Retain native account marks
separately because their hourly, pre-trade observations differ from this mark.

At the fixed end, report paired net equity, fees, fills, turnover, exposure,
coverage/gaps and drawdown over the full available marked paths for every cost
case. Preserve open holdings and distinguish marks from liquidation value.
The minimum study evidence is all source slots and all paired accounts; a
partial run cannot be presented as a completed comparison. Do not select a
winning fee or favorable ending snapshot.

This interval can reveal whether extra feasible entries offset their added
costs over the observed days. It cannot establish rolling-28-day risk, long-run
alpha or live execution parity. A deployment requires a separate sufficiently
long qualification under the owner's 35% rolling-28-day / 40% full-window
drawdown limits. This worker never changes a production strategy or places a
real order.
