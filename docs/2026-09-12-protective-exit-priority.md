# Protective exits retain access to valid quotes and order allowances

Two additional execution repairs are deployed to both existing paper services
at2026-09-12T11:15:00Z. Their strategies, $25 order ceiling,12-order daily cap,
spread/quantity checks and all hard halts remain in force. No real Poloniex
orders were enabled. These repairs extend the earlier latched-risk-halt fix.

A reproduced Engine cycle had one daily order allowance left, an ordinary
AAA rotation exit, and an ETH stop. Alphabetical scanning sold AAA and left
ETH exposed. Stops now precede ordinary rotation/funding exits, retaining
alphabetical ordering inside each class. They do not bypass the daily cap,
order deduplication, size limits or STOP file.

A second reproduced cycle had an unavailable AAA order book and a fresh ETH
stop. The AAA fetch failure previously aborted every protective exit. The
engine now continues independent fresh-book stops, pauses all forecasts,
fallbacks, entries and discretionary exits, and returns an explicit degraded
market result. It keeps the unavailable holding and last complete equity,
high-water and daily-loss baseline; it invents no price or fill.

UTC-day order counting is separate from establishing the first complete daily
valuation. `DayStartPending` records that distinction when necessary. Stops
can consume the new day's existing allowance while valuation is incomplete;
recovery sets the daily equity baseline without resetting orders already used
that day. A direct BUY is also blocked while the baseline is pending. The
optional field is omitted on ordinary complete-data states. Existing halts
remain latched. If all market contracts are unavailable, valid order creation
is still impossible; no contract/price checks are bypassed.

## Validation and release

Both regressions failed before repair and pass after it. The partial-book test
also covers quote recovery, preserved account history, no entry work, and the
current-day order counter. Full Go race tests and vet pass. Twenty matched
continuous/28-day baseline cells at30/60bps are exactly unchanged, including
reports, continuous cash/holdings, fills and equity paths. The isolated
stop-priority repair independently passes the same20 cells. Historical quote
books remain explicit proxies, not known historical exchange fills.

Candidate/running SHA256:
`275563f00a62cbb43c53206b4c83904a1daf07715360da5665ef551ae791a1a2`.
Both paper services are active with matching running hashes. The normal
account retains3holdings/5fills and correctly pauses entries outside the daily
forecast window; the experimental account completes cycles with4holdings/
17fills. First cycles preserve cash and every historical fill, with no new
fills. The accounts and history were not reset.

Evidence and the complete20-cell comparison are in
`data/frontier_20260912/protective-validated/`; deployment/source/state backups
and the prior859cdbede... binary are in its `release/` subdirectory. Earlier
source variants, failed tests and superseded replay attempts remain retained.
The exact-source final replay is the promotion basis. Fixed previously
rejected strategy overlays are being rebased separately on this final engine;
they do not change the running strategies unless their original gates pass.

For rollback, restore the prior binary while preserving the latest ledger.
If a current account has `DayStartPending=true`, retain an entry halt until a
complete valuation establishes its daily baseline; the older binary does not
understand that marker. Do not replace new fills/history with a backup ledger.
