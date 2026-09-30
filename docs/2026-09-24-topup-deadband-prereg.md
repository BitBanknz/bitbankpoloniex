# Corrected live-policy replay and fixed top-up deadband

Register before generating new market results. The retained September 24
top-up replay uses `DefaultConfig().CooldownHours == 72`; its generated test
does not override this. The running remote service explicitly uses 120 hours.
The existing report's claim of an exact tested profile is therefore unsupported.
Keep the original evidence and live service unchanged while correcting the
comparison. The 12-cycle entry-hour proxy also differs from minute scheduling.

First reproduce the four retained continuous accounts: legacy/top-up at
30/40 bps per side, 72-hour cooldown and 12 entry-hour cycles. Preserve the
complete final ledgers and require exact equality to the original JSON ledgers.
Use the same immutable source, fixture, prices, ranks and contracts. This checks
that instrumentation and the default-off treatment preserve prior results.

The new fixed matrix uses 120-hour cooldown, 60 minute-spaced cycles during
01:00–02:00 UTC, and one protective observation in every other hour. Synthetic
hourly books remain unchanged within the hour; this is still not a minute-price
or order-book replay. Run three policies at fees 30, 40 and 60 bps per side,
with continuous, 28-day and 56-day cash-reset geometries, retaining partial
tails of at least seven days exactly as the original harness does. This gives
135 accounts, including the full 60-bps stress rather than replacing it.

Policies:

- Legacy sizing: no top-ups, 40% reserve, original 10%/3% latched halts.
- Incumbent: top-ups, 40% reserve, 25%/8% latched halts.
- Candidate: incumbent plus a fixed 25% slot-target deadband. A held rotation
  position is topped up only when the gap is at least the larger of the existing
  25% of maximum-order threshold and 25% of its slot target. New entries, exits,
  imported inventory, mirrored policies, order caps and holding ages are unchanged.

The earlier proposed 10% slot threshold was discarded before implementation or
market testing because it is smaller than the existing $12.25 threshold at this
size. Do not sweep deadband levels or change the candidate after results.

Budget is 495 USDT, maximum order 49, three slots, maximum 12 orders per day,
the original frozen ranks and model receipts, no artificial terminal liquidation.
The actual live ledger retains its imported 489.1312417736-USDT budget; the flat
495-USDT research resets do not reproduce its inherited history or its cash.

For each of nine geometry/cost groups, require candidate mean and worst return
at least equal to the incumbent, maximum drawdown no greater, and no fewer
positive paths. Require strict mean improvement somewhere and positive continuous
return at all three costs. Also require maximum 28-day path drawdown <=35% and
continuous drawdown <=40%; these ceilings do not replace the relative checks.
Report legacy sizing separately so higher exposure cannot be mistaken for
new signal quality. All cells and failures remain visible.

Require native default-off parity, regression tests, source/input hashes, and
independent reconstruction of every account's cash, quantities, fees, discarded
dust and hourly marks before accepting any screen result. Preserve final pending
orders and holdings. This test does not retrain forecasts or claim an untouched
holdout. Reused history, current contracts, synthetic depth, missing intrahour
prices and limited live-cost evidence still prevent deployment on this screen
alone. No production binary, model, configuration or order changes here.
