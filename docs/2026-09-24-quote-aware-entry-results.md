# Quote-aware candidate tested; future comparison active

The private candidate filters unheld ranked names through the native quote and
size checks before selecting up to three targets. Held names keep their rank
eligibility; final orders retain the original preflight, cash, cooldown, stop
and order-count rules. The new flag defaults off and rejects live/mirror mode.
Production source and binaries were not changed.

## Native validation and discovery replay

The full suite and race suite each passed 117 checks, with no skips; `go vet`
passed. Fifty saved complete native cycles cover the five discovery captures
at three fee rates and ten paired synthetic account scenarios. All 25 control
cycles exactly match the original engine. Synthetic checks include blocked
entries, held-wide-quote retention, cooldown, daily order cap, reserve cash,
expired ranks, incomplete valuation and protective exits, including a halt.

The initial replay checker used Go field capitalization for lowercase JSON
order tags. Its failure is preserved; v2 corrects only that checker. Native
strategy code and inputs did not change. Decimal checks reconcile the saved
cash, quantities, amounts and fees.

The candidate opens ETH/TRX/XRP versus TRX alone in this discovery sample. More
fills are not a PnL win: added costs dominate the four-minute starting interval.
Post-cycle bid marks include all remaining holdings and entry costs:

| Fee per side | Control return | Candidate return | Control / candidate fills |
| --- | ---: | ---: | ---: |
| 30 bps | -0.098317% | -0.318193% | 2 / 6 |
| 40 bps | -0.118115% | -0.377587% | 2 / 6 |
| 60 bps | -0.157711% | -0.496374% | 2 / 6 |

These are discovery replays with immediate observed-book paper fills. They are
not forward results, realized live PnL or evidence of a long-run loss/advantage.

## Frozen future-data study

Six paired accounts were registered and started before source capture 38,
scheduled for **September 24 02:34:15 UTC**. They use the same 30/40/60-bps
fees and unchanged account rules. The fixed final capture is 10079, scheduled
for **October 1 01:55:15 UTC**; the source recorder ends one minute later.
The final partial entry hour is included as registered, not selected afterward.

The remote machine reproduced all 50 validation cycles and independent money
checks before launch. The first two future source batches independently verify
the raw bytes, hash chain, source/registration/computation clocks, twelve native
account cycles and six original-engine control reproductions. All six accounts
remain at 495 USDT cash with zero fills. The worker was alive with no gaps or
failure marker at the audit. Twelve worker-checker tests passed locally.

This is a prospectively frozen replay of future quotes. Computations can occur
after their modeled source-availability time; no contemporaneous order commit
or exchange fill is claimed. Seven days cannot prove 28-day drawdown or justify
a deployment. The owner's 35% rolling-28-day / 40% full-window limits remain
applicable to a later sufficiently long qualification.

## Additional stop/top-up defect found

A further synthetic case starts with a 100-USDT holding below its trailing stop,
a 49-USDT order cap and a valid rank. Both the original control behavior and the
quote-aware candidate sell 49 USDT, then top the same holding back up in the
entry pass. Quantity goes from 10 to 9.895204 instead of retaining the intended
partial reduction. In the next minute the existing processed stop ID suppresses
another sell within that decision hour. The initial probe incorrectly expected
the sell/rebuy to recur every minute; v2 records the actual two-cycle behavior.

This is a native synthetic reproduction, not an observed live occurrence. The
shared defect does not change the selection comparison's inputs, but blocks
promotion of the current candidate implementation. A separate correction should
prevent the entry pass from increasing a holding that is currently below its
stop, preserving ordinary sell caps and existing idempotency.

- [Treatment preregistration](2026-09-24-quote-aware-entry-prereg.md)
- [Future study assumptions and limits](2026-09-24-quote-aware-future-protocol.md)
- [Native validation](/vfast/data/trading_research_20260924/poloniex_quote_aware_v1/validation.json)
- [Paired cycle evidence](/vfast/data/trading_research_20260924/poloniex_quote_aware_v1/paired_replay_v2/verification.json)
- [Remote launch](/vfast/data/trading_research_20260924/poloniex_quote_aware_v1/future_launch/launch.json)
- [First future-prefix audit](/vfast/data/trading_research_20260924/poloniex_quote_aware_v1/future_first_two_audit/verification.json)
- [Capped-stop/rebuy reproduction](/vfast/data/trading_research_20260924/poloniex_quote_aware_v1/stop_refill_probe_v2/verification.json)
