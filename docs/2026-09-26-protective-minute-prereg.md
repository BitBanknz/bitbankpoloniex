# Fixed research treatment: one protective reduction per observed minute

The guarded rotation engine can sell at most one capped portion of a stopped
holding per decision hour. A 99-USDT holding and 49-USDT order cap can therefore
leave exposure below the stop until a later hour. The existing guard prevents
buying that stopped holding back but does not complete its reduction.

Test one treatment, without a parameter search: for a non-imported holding
currently below its existing protective stop, permit one capped sell per UTC
minute instead of one per forecast decision hour. Use the actual observed UTC
hour and minute in the deterministic decision ID, so forecast availability or
a risk-latch change within a minute cannot create another protective sell.
Successful partial paper reductions remain bounded by the original daily order
allowance, lot/minimum rules, spread, book freshness and depth participation.
If a quote or another gate rejects the order, the ordinary retry semantics stay
unchanged. Preserve ordinary rotation/funding exits and imported allocations.

Build from the authenticated, exact-release stop/top-up-guard candidate. Add a
private research flag that defaults off and rejects live mode or experimental
fallback. This is an isolated paper experiment; no installed trading code,
account configuration, worker or ongoing study changes.

Before reading treatment outcomes, freeze:

- Controls: the guarded release, with unchanged 495-USDT budget, 49-USDT order
  cap, three slots, 40% reserve, twelve orders/day, 120-hour cooldown, 72-hour
  rotation holding rule and 25%/8% account halt bands.
- Fees: 30, 40 and 60 bps per side, retaining every result.
- Native behavior checks: default-off equivalence; consecutive stop minutes;
  repeated calls within a minute; forecast-clock change; unavailable/stale/wide
  books; shallow depth; daily cap; below-stop buy suppression; full exit and
  cooldown; recovered price; risk halt; incomplete other holding valuation.
- Explicit synthetic falling and rebounding paths. These illustrate the
  exposure/fee tradeoff and are not profitability evidence.
- The same nine historical cases and 45 accounts as the guarded-release study:
  continuous, 28-day and 56-day resets at all fees, retaining partial tails.
  Exact default-off reports and full ledgers must match the sealed guarded
  release. Independently reconstruct each candidate ledger and its decision IDs.
- All three guarded control accounts across the already frozen public prefix
  78–3297. Run the treatment with its own continuing state, keep complete marks
  and gaps, and independently check cash, fees and quantities. This prefix is
  reused diagnostic data, not an unseen holdout; it previously contained no
  protective stops, so unchanged financial paths are expected, not improvement.

Run native suite, race checks and vet. Retain failures; do not relax financial
tolerances or discard losing accounts. Report PnL, drawdown, fees, turnover,
holding exposure, and changed fill counts against the guarded control.

The historical fixture uses hourly prices and synthetic books, repeating the
same hourly quote during sixty entry-hour cycles. It cannot demonstrate actual
minute liquidity replenishment or reaction to within-hour price moves. Label
any treatment gains conditional on that model. No interpolation of unseen minute
prices, claim of independent alpha, or deployment qualification follows from
these reused data. Higher PnL and lower drawdown under realistic future fills,
source parity and the owner's 35% rolling-28-day / 40% full-window limits remain
required for an algorithm promotion.
