# Remote health and 168-hour cooldown rejection

The remote live service is active with zero restarts and a ledger updated
within one minute. Its mapped executable and installed file both hash to
`eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`.
It retains the 495-USDT budget, 49-USDT order cap, three slots and 120-hour
cooldown. There is no pending order or latched halt. The ledger contains 18
fills, most recently a 48.88266-USDT BNB buy on September 19. The fee is in
TRX and retained in the exchange-trade evidence; a zero quote-currency fee
field is not a free fill. Tracked BNB/TRX/ZEC and approximately 339.05 USDT
cash agree with the authenticated dashboard, which values the whole spot
account at approximately 498 USDT including small untracked dust.

Today's inference service completed successfully. Normal entry cycles ran
through 01:59 UTC. `missing_stale_or_invalid_state` from the signal endpoint
after 02:00 UTC is consistent with expiry of the declared entry window;
protective position checks continue. The unaccepted fallback remains disabled.

The bounded offline candidate lengthens only post-sale cooldown from 120 to
168 hours. Source-built Engine tests use the frozen January 14–September 7
fixture with one cycle per hour, 495/49 sizing, the current dust fix, unchanged
legacy halts and 30/60-bps fees per side. This is not the 12-cycles-per-entry-hour
top-up experiment, so its absolute returns need not match that earlier run.

| Surface | Fees/side | 120h return | 168h return | 120h max DD | 168h max DD |
|---|---:|---:|---:|---:|---:|
| Continuous | 30 bps | 11.2704% | 10.3329% | 6.4087% | 6.4714% |
| Continuous | 60 bps | 8.4508% | 7.8148% | 6.9763% | 6.9368% |
| 28-day mean | 30 bps | 1.4741% | 1.0321% | 5.5403% | 5.7548% |
| 28-day mean | 60 bps | 1.1030% | 0.6972% | 5.9729% | 6.1616% |

168h reduces continuous fills from 113 to 98, but loses return in all four
comparisons. Positive 28-day paths fall from seven to six of nine at both
costs. Reject it. No production change or real order was made by this audit.
Forty result cells include eight complete 28-day windows plus a 12-day tail
for each arm/cost and four continuous paths; they are not independent samples.
Synthetic books, current contracts and reused forecasts do not prove live
fill quality or independent out-of-sample alpha.

`go test -race ./...` passes. The frozen replay passes in 362 seconds.
Evidence: `data/validation_20260920/cooldown/` holds source/input hashes,
generated overlay, config, exact path results, continuous ledgers and summary.
Preparation reuses `research/cooldown20260914/prepare.py`, replacing only its
generated `72+48*int(bonus)` with `120+48*int(bonus)` before compilation.
The local `bin/bitbankpoloniex` is an older binary; tests compile current
source, and no attempt was made to use that local binary for deployment.
