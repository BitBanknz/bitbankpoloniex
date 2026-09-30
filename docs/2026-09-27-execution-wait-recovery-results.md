# Poloniex paper execution-wait recovery

The paper completion checker now accepts a valid forecast that has been published but is not yet executable. Both repaired consumers were launched in new directories using the unchanged native trading binaries and all original account settings. The recorder was not restarted. No real-money order, service or setting changed.

The original consumers stopped at source index 173, logical 2026-09-27 00:05:24.993586862 UTC. A valid forecast issued at midnight was executable at 01:00. The native engines correctly returned a completed waiting cycle with no fills, but the old checker asserted that every successful cycle must already have an executable signal. The original failed directories and receipts remain preserved.

The added waiting outcome validates the published forecast, issue/execution clocks, successful native completion, state flags and intact fill prefix. New entries remain forbidden while waiting; protective sales remain allowed. Malformed forecasts, unknown errors, incomplete cycles and inconsistent states still fail. See the [recovery protocol](2026-09-27-execution-wait-recovery-protocol.md).

All 12 tests passed: the original five outcome tests, three waiting-state tests using both native variants, and four prefix-integrity tests. Native boundary checks cover one nanosecond before execution, execution itself, one nanosecond after it, and forecast expiry. Protective selling while waiting is exercised, and forged buys are rejected.

Before launch, 1,412 captured files were authenticated. All 173 originally committed batches in each consumer were replayed from initial state; every decoded input and output matched the authenticated originals exactly. This includes the unusable metadata gap at index 97. Across the two variants, 2,064 original native transitions and 24 additional transitions across indices 173–174 were checked with independent Decimal accounting. The accounting checker verifies execution/account arithmetic; it is not an independent implementation of the trading planner.

After launch, both recovered receipt chains were authenticated through source index 218. Their compressed prefix inputs and outputs also matched the original bytes. The complete recovered suffix from index 172 through 218 was downloaded and independently rerun: 564 native and Decimal transitions matched the remote outputs exactly. The snapshot was observed at 2026-09-27T00:51:20.463080+00:00.

| Variant | Paper PID | Verified through | Suffix transitions | Suffix fills | Outcomes |
|---|---:|---:|---:|---:|---|
| unguarded | 3666563 | 218 | 282 | 0 | entries_paused, waiting_execution |
| guarded | 3666564 | 218 | 282 | 0 | entries_paused, waiting_execution |

Recovery reconstructs the original cash, holdings, high-water marks and counters through verified replay. It does not reset the accounts at the interruption. The original consumers remain failed; the new streams are explicitly recovered observed-data replays, whose computations may occur after publication. They do not claim contemporaneous order decisions or actual exchange fills.

The source and recovered consumers retain the original October 3, 2026, 21:12:15 UTC endpoint. Their full-period comparison is still incomplete. This repair improves paper validation reliability and establishes no profitability improvement or trading-algorithm qualification.

The first full-prefix download hit its 60-second transfer limit; the partial archive and the consequent missing-input audit failure were retained. A separately named read-only transfer completed and was fully authenticated before replay or launch.

Evidence: `/vfast/data/trading_research_20260924/poloniex_execution_wait_recovery_20260927_v1`. Initial failure capture: `/vfast/data/trading_research_20260924/poloniex_consumer_failure_20260927_v1`.
