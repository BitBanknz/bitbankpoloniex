# Completed protective cycles retained by the separate paper-worker candidate

The September 24 paper worker stopped on native errors that actually describe
completed protective cycles: an unavailable held quote or a latched account risk
limit. The native engine had already saved the resulting account, including any
observed protective sales. The worker discarded that cycle before publishing its
paper receipt.

A separate v2 worker now recognizes these exact outcomes and preserves the
account path. It checks the native cycle's nanosecond clock, account identity,
fill history, unavailable held symbols, entry pause and risk-latch fields. Every
paused cycle forbids new buys; missing or stale prices remain unavailable marks.
Unexpected errors and inconsistent states still fail. The original cash,
quantity, fee and immutable receipt checks remain in place. The derived worker
requires a new `poloniex-fixed-future-replay-v2` protocol.

Five outcome tests pass using both frozen native engines, including missing
quotes followed by fresh quotes, a protective sale, a newly latched risk limit,
its subsequent cycle, and adversarial errors/clocks/buys. All twelve inherited
worker checks pass against the derived candidate. The first fixture assertion
was corrected to accept Go's omitted false `DayStartPending` field; no native
behavior or accounting tolerance was changed.

A complete publication fixture exercises all six fee/selection accounts across
four logical minutes. After the initial purchases, one held book becomes
unavailable while another holding triggers an observed stop; fresh valuation in
the third minute trips the daily risk limit, which remains latched in minute
four. The original worker publishes one batch and stops on minute two. The
candidate publishes all four, preserves the unavailable mark in minute two,
retains the risk latch, and submits no modeled buys in the paused cycles. Thirty
published account transitions pass independent Decimal accounting. All receipts
retain a valid hash chain. These are synthetic correctness fixtures, not returns
from an investment strategy.

Evidence: `/vfast/data/trading_research_20260924/poloniex_completed_cycle_worker_v1/`.
`verification.json` binds the candidate, derivation and unit checks;
`integration/verification.json` binds both publication runs and their retained
receipts. Source is in `research/futureworker20260926/`.

The candidate has not been launched. Neither existing prospective study was
edited or restarted, and live trading is unchanged. The separately registered
two-day prefix comparison continues under the original frozen study rules.
