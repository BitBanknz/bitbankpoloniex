# Poloniex fixed prospective prefix: no strategy improvement observed

All four strategy variants produced identical financial paths at each registered
fee level: original selection, quote-aware selection, and each with the stop/top-up
guard. This prefix provides no basis to promote either treatment for better PnL.
The seven-day paper studies continue with their original configurations.

The common comparison covers source indices 78–3297: 3,220 scheduled observations
from September 24, 03:14 UTC through September 26, 08:53 UTC. The earlier
unguarded indices 38–77 were independently verified as cash-only at 495 USDT.
The cutoff was fixed before inspecting the extended outcomes, as specified in
[the comparison protocol](2026-09-26-future-prefix-comparison-protocol.md).

## Financial results

Every row below applies to all four variants. Holdings are marked at captured
bids after each cycle; they have not been liquidated.

| Fee per side | Ending equity, USDT | Net return | Observed maximum drawdown | Fees, USDT |
| --- | ---: | ---: | ---: | ---: |
| 30 bps | 492.067353 | −0.592454% | 1.080628% | 0.849727 |
| 40 bps | 491.784111 | −0.649675% | 1.081245% | 1.132970 |
| 60 bps | 491.217626 | −0.764116% | 1.082483% | 1.699455 |

Each account made twelve modeled buys, with 283.242445 USDT gross turnover and
no sells. All retained holdings were priced at every sampled minute. There were
no dust removals, below-stop buys, or account risk halts. Maximum observed gross
exposure was 57.4683%, 57.5012%, and 57.5670% across the respective fee levels.
At 30 bps, ending cash was 210.907827 USDT and marked holdings were 281.159526
USDT. Cash alone is not the account's equity.

At 30 bps, the net contribution including entry fees was −1.200030 USDT from
BNB, −0.830252 from PEPE, and −0.902364 from TRX. Their sum equals the account's
−2.932647 USDT change exactly using Decimal arithmetic. These are open-position
marks, not completed round-trip trading profits.

[Equity chart](/vfast/data/trading_research_20260924/poloniex_future_prefix_3297_v1/completed_v2/audit/equity.png)
and [machine-readable report](/vfast/data/trading_research_20260924/poloniex_future_prefix_3297_v1/completed_v2/audit/report.json).

## Why the treatments had no effect here

Valid forecasts were available in all sixty scheduled execution minutes on each
of September 25 and 26. TRX, BNB, and PEPE were the top three names throughout.
At the first eligible minute, source index 1384, all three passed quote checks
and all twelve account variants bought them. In all remaining 119 forecast
minutes, each account already held all three names. Quote-aware selection
deliberately retains held names, so later quote failures did not select different
holdings. All twelve buys occurred on September 25; eight were PEPE fills, and
the daily twelve-order allowance was consumed by 01:18 UTC.

A hypothetical flat-account diagnostic would select different names in 114 of
the 120 forecast minutes. That diagnostic is not the actual account path:
the accounts were already invested. Across the 360 top-three quote checks,
108 passed; 248 had a spread rejection and 36 a minimum-amount rejection,
with overlapping rejection reasons. This is a liquidity diagnostic, not evidence
that replacing held assets would improve returns.

The stop guard also had no opportunity to change these observed paths. Even
the minimum captured bid divided by the final holding peak remained 98.0623%
for BNB, 95.0336% for PEPE, and 98.8374% for TRX, above the 90% stop threshold.
Using the final peak makes this check conservative for these continuously held
assets. It says nothing about prices between observations.

The [account-state explanation](/vfast/data/trading_research_20260924/poloniex_future_prefix_3297_v1/completed_v2/audit/path_explanation.json)
checks all 1,440 forecast/account cycles. The financial path comparison checks
28,980 paired account rows; the twelve accounts are correlated variants, not
twelve independent observations of strategy performance.

## Verification and replay-driver correction

The authenticated capture contains 25,990 files. There are 3,260 usable source
batches and 35,860 public endpoint requests, with no missing source batches or
cross-batch chronology failures. The rank endpoint returned 503 in 3,030
off-window minutes. Another 110 responses were available before their execution
hour and correctly not eligible; 120 were eligible. Other endpoints returned
200 throughout the prefix.

The audit reproduced 38,880 candidate account cycles and 19,440 independent
baseline cycles with the frozen native engines. It independently reconstructed
cash, quantities, fees, fill bounds, dust handling, holding peaks, and post-cycle
bid equity. Financial outputs matched exactly in all 58,320 native executions.

The first auditor stopped on one request-trace discrepancy: an additional `/`
request at unguarded index 2062, `quote_aware_fee30`. Financial output already
matched. All original data and the failed run were retained. An inventory of
all 38,880 saved outputs found this single unrequested path, and forty additional
native replays did not reproduce it. The old test server logged any inbound
public GET, including unrelated requests.

Under the separately recorded
[trace reconstruction protocol](2026-09-26-native-trace-reconstruction-protocol.md),
a controlled root probe reproduced the complete recorded request multiset and
the exact financial result. The replacement audit permits only this identified
case, retains both answers, and rejects any other discrepancy. The original
request's sender remains unknown. The audit therefore includes one explicitly
reconstructed trace; it does not claim every raw trace was identical without
reconstruction.

A private driver candidate now marks native requests with a fresh per-cycle
token and rejects unrelated requests before recording them. Engine source is
unchanged. Fifty existing native cases per driver and six controlled probe cases
passed. The isolated driver also passed 100 native race cases, with exact
financial results and engine paths; all 100 unmarked probes were rejected.
This candidate has not replaced the drivers in the ongoing studies.

## Decision and limits

No PnL improvement was demonstrated, and no live deployment is qualified by this
comparison. Keep the fixed seven-day studies running through their registered
end. A read-only check at September 26, 10:49:36 UTC found the source recorder and
both paper workers alive with matching process identities, zero recorded gaps,
and no failure or stopped files.

The modeled IOC fills do not establish real exchange queue position, latency,
partial fills, or realized sale proceeds. Source responses are sequential, not
an atomic market snapshot. These are decisions at the completed source batch's
logical time; the largest observed subsequent computation lag was 36.541 seconds.
The forecast payload does not establish the full production model identity.
Only two forecast execution hours and no exits are present. This interim prefix
cannot establish the owner's 28-day drawdown requirement or durable alpha.

The simulation work does provide two concrete reliability improvements for a
future registered paper campaign: request-trace isolation here and the separately
tested [completed-cycle worker handling](2026-09-26-paper-cycle-outcomes-results.md).
Neither improvement is counted as trading performance evidence. Existing source
data, sealed artifacts, active studies, and live trading processes remain intact.
