# Preserve completed protective cycles in future paper research

The frozen September 24 paper worker accepts only an empty native error or the
expected missing-signal entry pause. The native engine also saves completed
cycles when held quotes are missing and when account risk limits have latched.
Those cycles may include valid protective sales. Treating them as fatal loses
the continuing paper account path and makes a missing quote terminate research.

Build a separate worker candidate; do not edit or restart either existing study.
Classify only exact, internally consistent native outcomes. Require the complete
cycle clock, paper/unfunded identity, no pending order, and unchanged fill prefix.
For missing valuation, independently identify unavailable held quotes and require
the corresponding exact error/source fields; only protective sells on available
symbols are permitted. For a risk halt, require the native latch/error/source and
allow reductions only. Unexpected errors, stale cycle clocks, unsupported ledger
halts, invented missing symbols and entries during a protective-only cycle fail.

Retain original independent money checks and unavailable post-cycle marks. Do
not fill missing observations, reset accounts, treat a pause as a profitable
decision, or loosen trading/risk settings. A corrected worker requires its own
future protocol and source/code identities before paper launch; this work does
not alter live trading or any frozen account results.

Test actual frozen native engines with no signal, an unavailable held book and a
different observed protective stop, subsequent restored quotes, a newly latched
risk halt, and its next cycle. Verify independent Decimal cash/quantity/fee
transitions throughout. Include adversarial errors, clocks and protective-only
buys. Preserve derivation, test logs and source hashes. This is simulation control
correctness, not evidence of higher returns.
