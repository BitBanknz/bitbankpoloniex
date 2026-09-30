# Guarded future-data comparison

Run the same six-account quote-selection comparison with the validated stop
guard applied to both arms. This is a separate study, with a new immutable
protocol and a first source index at least two minutes after registration.
The original unguarded study remains frozen and provides a separate reference.
Do not overwrite its code, accounts, history or results.

Each account starts with 495 USDT paper cash, no holdings or orders. Control and
quote-aware entry selection each run at 30/40/60-bps fees per side. The common
guard skips an entry/top-up for a currently stopped holding; sell caps, stop
decision IDs, thresholds, model/forecast source, reserves, limits and cooldowns
are unchanged. Do not mix in the separate deadband treatment.

The source recorder, final index 10079, missing-slot treatment, native paper IOC
fill assumption, post-cycle bid valuation, immutable account journal, 4-GiB
storage bound and 20-GiB free-space floor follow the original future protocol.
Actual computation clocks remain distinct from modeled source-availability
clocks. No live order or contemporaneous order commit is claimed.

Before comparing guarded versus unguarded paths, verify that all unguarded
accounts were still at their original flat 495-USDT state immediately before
the guarded study's first source index. Preserve that prefix as evidence; do not
erase it or reset accounts. If this condition fails, the two studies do not
form a matched initial-state comparison. The two arms within the guarded study
remain matched independently of that cross-study condition.

At the fixed end retain every account and fee case, including all gaps and the
last partial entry hour. Report net equity, marked-path drawdown, costs, fills,
exposure and coverage. This short study cannot establish 28-day risk or long-run
alpha. The owner's 35% rolling-28-day / 40% full-window limits apply to a later
sufficient qualification; this worker does not activate a real-money strategy.
