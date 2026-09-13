# Production fill and account-scale replay

The remote live service is healthy with zero restarts. At 01:00:07 UTC on
13 September, order `621993499604250624` filled 0.009066 ZEC for
10.15673046 USDT. Its fee was 0.041722774338336362 TRX. Both cash and tracked
TRX quantity reconcile exactly to the exchange fill. The ledger now has 11
fills, no pending intent or halt, and advances every minute. Four holdings are
expected: one imported ETH allocation plus three bot allocations; imported
inventory does not consume one of the three bot slots.

The new replay uses the actual Engine at a 495-USDT budget and 49-USDT order
cap, instead of the earlier research account's 1,000/25 configuration. It uses
the same frozen Poloniex data/causal rank forecasts, 40% reserve, daily quota,
minimum holding period, stops, rounding and modeled historical book proxies.
Two initial states are separate: all cash, and 20% imported ETH / 80% cash.
Neither is asserted to recreate the account's full historical holdings.

The sole candidate tops up selected non-imported positions to the existing
49-USDT allocation ceiling, subtracting marked residual value and preserving
idempotency and risk controls. It is only a research overlay.

| Start / fee per side | Continuous baseline → top-up | Fold mean baseline → top-up | Maximum continuous DD baseline → top-up |
|---|---:|---:|---:|
| Cash / 30 bps | −2.7850% → +1.4418% | +0.9862% → +0.7008% | 9.0390% → 8.8546% |
| Cash / 60 bps | −4.4727% → −5.3154% | +0.6383% → +0.2661% | 9.6202% → 10.2039% |
| Imported ETH / 30 bps | −1.8816% → +2.3648% | +0.9425% → +0.9444% | 8.1993% → 7.9956% |
| Imported ETH / 60 bps | −3.5727% → −0.6178% | +0.5411% → +0.4526% | 8.7558% → 9.3701% |

**Rejected:** fold means regress, and stressed continuous drawdown worsens in
both starting-book cases. No 56/84-day escalation or production strategy
change follows. An attractive continuous result alone is insufficient.

All 80 evaluation cells completed: two starting books × two fee assumptions ×
two variants × (one continuous period + eight full 28-day folds + one 12-day
tail). These are repeated cost/profile cells, not 80 independent folds. History
was already examined; hourly-open bid/ask and 1% prior-turnover capacity are
proxies, not historical executable books. The observed ZEC fee is below the
30-bps base assumption; future actual fees can differ.

Reproduction: `research/live_parity20260913/prepare.py --out <new-directory>`
generates the offline overlay. Run `go test -overlay <dir>/overlay.json
./internal/bot -run '^TestFrozenLedgerReplay$' -count=1 -timeout=30m -v` with
`POLONIEX_LEDGER_FIXTURE`, `POLONIEX_LEDGER_MARKETS`, `POLONIEX_LEDGER_OUT` set
to the retained fixture, contract snapshot and new output. Set
`POLONIEX_IMPORTED_ETH=1` for the imported-book case. Temporary ledgers used
`TMPDIR=/dev/shm`; the mock server rejects non-GET requests.

Complete results, overlays and source/input hashes are retained under
`data/live_parity_20260913/`; `summary.json` checks all expected cells, exact
paired comparisons and rejection reasons. Production remains on the previously
validated executable at the remote host described in the migration runbook.
