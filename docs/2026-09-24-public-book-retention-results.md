# Prospective quotes expose an execution gap

The new recorder is active on the IP-allowed host. Its **10,080 scheduled minute
slots** run from **September 24 01:56:15 UTC to October 1 01:56:15 UTC**, with
the end exclusive. It retains the local public rank publication, exchange
contracts, 24-hour tickers and five-level books for eight fixed symbols.
The recorder uses public GET requests and does not load trading credentials or
place orders. Its original source and protocol remain frozen.

## First independent verification

The first five captures contain **55 responses**, with no missing requests or
gaps. All raw bytes, archive hashes, endpoints, request ordering, monotonic/wall
clock checks and publication receipts verified. Rank responses were HTTP 200
at 01:56–01:59 and HTTP 503 at 02:00, reporting unavailable state. The expired
ranks are not carried into the 02:00 assessment.

All eight markets met the public NORMAL/USDT, fresh-ticker and 100,000-USDT
24-hour-volume requirements at the audited observation times. Entry sizing
then applied the actual bot's 30-bps spread limit, 30-second book age, depth
within 10 bps of the best ask, 10% depth participation, lot/tick rounding and
exchange quantity/notional bounds. The descriptive calculation assumes a
49-USDT buy allowance; private cash, existing positions, cooldowns, risk halts
and daily order allowances are outside this calculation.

| Capture UTC | Original top three | Names passing quote/size constraints |
| --- | --- | --- |
| 01:56 | TRX, ZEC, PEPE | TRX |
| 01:57 | TRX, ZEC, PEPE | TRX |
| 01:58 | TRX, ZEC, PEPE | TRX |
| 01:59 | TRX, ZEC, PEPE | TRX |
| 02:00 | No valid current ranks | No entry target list |

ZEC failed both the spread and minimum-notional checks in all five captures.
PEPE failed minimum notional at 01:56, spread at 01:57–01:59, and both at 02:00.
In particular, a narrow spread alone does not imply enough executable size.

An independent Decimal calculation and the actual Go `BuildOrder` function
agreed on acceptance for **all 40 symbol/capture cases**: 17 accepted and 23
rejected. Accepted prices, quantities and amounts matched exactly. This native
check used only a clock overlay and retained public responses; it made no
network requests. The 40 cases include the eight post-expiry books and are not
40 independent strategy observations or simulated trades.

The recorder passed eleven tests locally and on the remote before launch.
The independent verifier passed ten initial tests; v2 adds two tests ensuring
that a response with an unstable clock can never supply usable market data.
Both verifier versions produce identical results on this real prefix. The
earlier source and result are retained, and the running recorder was unchanged.

## Implication for the next strategy comparison

The live engine constructs its three ranked targets before checking their
books. The historical replay instead supplies synthetic books with a uniform
approximately 10-bps spread. These observations demonstrate that this proxy
can miss rejected entries and limited depth; they do not measure the proxy's
full historical bias or establish profitability for another policy.

A useful next comparison is entry selection that considers executable quotes,
against the existing target-selection order. Keep held-position exit/retention
rules explicit: treating a temporarily unbuyable holding as unwanted could
cause unintended rotation. Retain the 25% slot-target deadband as its own arm,
so execution selection is not confounded with the preceding sizing change.
Lower-ranked scores are ranks, not expected returns; substituting ETH/XRP in
these discovery observations would increase exposure, without proving an edge.

These first observations are discovery data. Fix any new policy and evaluation
rules before its future outcome interval; do not label a replay of these same
observations an untouched validation set. Use actual receipt availability and
preserve unavailable forecasts and missed observations. The owner's applicable
risk limits remain **35% rolling 28-calendar-day drawdown and 40% full-window
drawdown**, alongside the strategy's existing operational halts. Do not silently
replace those limits with a tighter relative-drawdown requirement.

The independently fetched books are not an atomic exchange snapshot, and the
collector's receipts are not committed order decisions. Visible depth does not
prove a real IOC fill. Seven days cannot certify a long-horizon policy. No live
algorithm was promoted based on this diagnostic.

## Operation and evidence

At 02:08:39 UTC the recorder was alive with 13 completed captures, zero gaps and
no failure or stopped marker. The live service remained active, PID 25868,
with zero restarts and matching installed/mapped binary SHA256
`eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`.

- [Frozen collection protocol](2026-09-24-public-book-retention-protocol.md)
- [Remote launch receipt](/vfast/data/trading_research_20260924/poloniex_public_retention_v1/launch.json)
- [Exact first-prefix mirror](/vfast/data/trading_research_20260924/poloniex_public_retention_first_prefix_v1/transfer.receipt.json)
- [Independent v2 audit and per-symbol constraints](/vfast/data/trading_research_20260924/poloniex_public_retention_first_audit_v2/verification.json)
- [Native order-builder parity](/vfast/data/trading_research_20260924/poloniex_public_quote_native_parity_v1/verification.json)
- [Operational health and unchanged binaries](/vfast/data/trading_research_20260924/poloniex_public_retention_health_v1/verification.json)
- [Official spot market-data schema](https://api-docs.poloniex.com/spot/api/public/market-data)
