# Reserve daily capacity for exits: fixed three-arm account comparison

The retained public prefix shows twelve daily orders consumed by buys. Existing
stop priority handles simultaneous orders, but cannot recover capacity already
spent earlier in the day. Test reserving three allowances, one per configured
rotation slot, before inspecting new account results. This is a trading-policy
hypothesis; fewer buys can also reduce profitable exposure.

Start from the authenticated guarded release, with its unchanged protective
clock and one-successful-sell-per-symbol/hour rule. Add a private paper-only
`ExitOrderReserve` setting, default zero. Reject negative values, values above
the daily total, live mode with a reserve, and combining a reserve with fallback.
Before order construction, suppress a BUY when OrdersToday >= MaxOrdersDay minus
ExitOrderReserve. SELLs retain the existing total cap. Successful orders of
either side count toward that total; failed/blocked orders consume no allowance.
No new counters, state schema, unbounded exits, price or liquidity exceptions.
Ordinary and protective sells share the remaining capacity. Reserving three
orders does not guarantee full liquidation of three holdings.

Freeze three arms: baseline total12/reserve0; matched total9/reserve0;
candidate total12/reserve3. The matched control separates reduced buying from
additional exit capacity. Do not combine this experiment with the clock-only or
minute-selling treatments, change signals, or sweep the reservation size.

Run the same nine historical configurations and all 45 accounts per arm:
continuous, 28-day and 56-day resets with retained partial final windows, each
at 30/40/60 bps per side. Keep 495 USDT cash, 49/order, three slots, 40% cash
reserve, 120-hour cooldown, 72-hour ordinary rotation holding, 10% trailing stop,
25% peak and 8% daily halt. Reproduce baseline reports and ledgers byte-for-byte
against the guarded release. Independently reconcile cash, fills, fees, holdings,
marks, decision IDs and both order limits for every arm. The inherited Decimal
reference consumes recorded intents; it is not a complete independent planner.
Supplement it with first-divergence checks against the nine-order control:
any different path must first diverge through a candidate SELL after that
control has exhausted its total allowance. Report all exceptions as failures.

Require native suite/race/vet, default-off full-cycle parity, exact fixture
clock causality, and complete-cycle money/race tests covering nine shallow buys
followed by protective exits, exhaustion, failed buys, duplicates, restarts,
partial reductions, missing/stale/wide books, risk halts and UTC reset. Keep
falling and rebounding synthetic paths as behavioral examples, not PnL evidence.

Replay the same authenticated public prefix78–3297 with each arm's own continuing
state at all three fees. Baseline must reproduce its recorded outputs; each new
state must reconcile independently. This already-observed prefix had no stops,
so it can measure the changed exposure and compatibility but cannot supply fresh
confirmation of the protective reservation. Do not modify its source or workers.

For every fee/geometry group, a historical screen requires positive mean return
strictly greater than both controls; median/P10/worst-return nonregression and
maximum-drawdown nonregression against both. For reset groups additionally require
at least two improved windows and no single window contributing more than80%
of positive paired gains against either control. Also report every individual
return/DD regression. Apply the owner's35% rolling28-calendar-day/40% full-window
drawdown ceilings to the available hourly marks, explicitly as sampled research
checks rather than proof of intrahour risk. All groups and both comparators can
veto advancement. Do not relax gates or choose a fee/window/reserve after results.

Hourly historical books use synthetic depth and do not establish real fills,
liquidity replenishment, intrahour drawdown or market impact. The public replay
uses sequential snapshots and modeled IOC fills. Even a historical pass needs
separately fixed unused/prospective evidence and production parity. No live
activation or changes to ongoing paper campaigns follow this experiment.
