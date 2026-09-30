# Poloniex prospective research replacement launched

A separate public recorder and two v2 paper workers are running. The original September 24 archives, accounts, failures and protocols remain intact. No live trading strategy or real order changed.

The original paper workers both exited after an unavailable held TRX quote. Their native engines had completed protective cycles, but the old wrapper rejected that outcome before publishing its receipt. The public recorder later stopped on a detected wall-clock discontinuity. SSH connectivity subsequently recovered; the stopped processes were confirmed by a read-only check.

The new interval starts **2026-09-26T21:12:15+00:00** and ends **2026-10-03T21:12:15+00:00**, covering 10,080 one-minute source slots. Both paper workers started before index zero, from matching flat 495-USDT accounts. Each compares control and quote-aware selection at 30/40/60-bps fees; one has the common stop guard and one is unguarded. This retains all twelve fee/selection/guard combinations.

The native binaries and strategies are unchanged. The new worker uses the previously tested completed-cycle fix, preserving unavailable valuations and protective actions on missing-held-quote or latched-risk outcomes. The earlier five outcome tests, twelve inherited worker checks and 30-transition synthetic publication fixture remain authenticated. Eleven unchanged recorder tests passed before this launch. An initial packaging attempt ran 33 passing recorder/verifier tests but stopped on an incorrect expected-count assertion; that attempt and source are retained.

The fixed first-three-batch audit checked **33 public response records**, all source/protocol identities, availability clocks and receipt chains. It reproduced all **36 native account transitions** and independently checked the same **36 Decimal cash/quantity/fee/valuation transitions**. Those batches contained **0 modeled fills**. These initial checks establish launch and replay correctness only; they do not complete the seven-day comparison or qualify profitability.

At the subsequent captured health observation, the collector and both workers had processed six source batches without a gap or failure. This is point-in-time evidence, not a guarantee of future uptime. The original Binance paper study was not restarted or altered.

The recorder still stops on clock discontinuity, rate limits and resource bounds. The paper workers retain all missing slots and unavailable marks. No automatic restart, historical backfill, account reset, private API request or credential transfer was introduced. Paper IOC execution remains an observed-book assumption, and actual compute times remain separate from logical source-availability times.

The full comparison remains pending until its fixed end. It must report all twelve paths, missing data, fees, turnover, open holdings and available marked drawdown. Seven days cannot establish the owner’s rolling-28-day risk limit or long-run alpha; no deployment eligibility is claimed.

Protocol: [2026-09-27-prospective-replacement-protocol.md](2026-09-27-prospective-replacement-protocol.md). Local evidence: `/vfast/data/trading_research_20260924/poloniex_prospective_replacement_20260927_v2`.

Remote research roots:

- `/nvme0n1-disk/code/bitbank-poloniex/data/public_retention_20260927_v1`
- `/nvme0n1-disk/code/bitbank-poloniex/data/completed_cycle_unguarded_future_20260927_v1`
- `/nvme0n1-disk/code/bitbank-poloniex/data/completed_cycle_guarded_future_20260927_v1`
