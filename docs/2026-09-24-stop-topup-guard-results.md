# Stop/top-up guard: qualified correction, awaiting owner activation

The native engine can sell a capped portion of a stopped holding and then buy
most of it back in the same cycle. In later cycles, the already-processed stop
decision ID can block another sale while top-ups remain possible. The correction
skips entry/top-up for a holding whose current observed price breaches its stop.
It does not change the stop threshold, order cap, sell decision IDs, cooldown,
reserve, day cap, forecasts or training. A capped stop still sells at most once
per decision hour; this change does not implement repeated liquidation.

The live ledger snapshot contained 22 fills and no same-symbol sell/buy pair
within 60 seconds. The defect was reproduced in the complete native engine and
in reused historical accounts; an occurrence on the live account is not claimed.

## Historical result

All 45 accounts from the corrected 120-hour cooldown / 60 entry-hour-cycle
matrix were retained, including partial tails. The guard eliminated all 21
below-stop buys. Thirty-three complete ledgers were unchanged; nine accounts
earned more and three earned less. All six reset-account group means increased;
all three continuous accounts were unchanged. Return figures below are net of
the indicated fee **per side**, not annualized. Reset means include nine 28-day
accounts or five 56-day accounts, including their final partial accounts.

| Account horizon | Fee | Mean return before → guard | Largest account drawdown before → guard |
|---|---:|---:|---:|
| Continuous | 30 bps | 8.8520% → 8.8520% | 12.9798% → 12.9798% |
| Continuous | 40 bps | 18.3502% → 18.3502% | 13.3214% → 13.3214% |
| Continuous | 60 bps | 13.8338% → 13.8338% | 13.7985% → 13.7985% |
| 28 days | 30 bps | 2.2516% → 2.3109% | 12.3826% → 12.3826% |
| 28 days | 40 bps | 1.7462% → 2.0876% | 12.6542% → 12.6542% |
| 28 days | 60 bps | 1.5376% → 1.6342% | 13.1936% → 13.1936% |
| 56 days | 30 bps | 3.9021% → 3.9804% | 12.6470% → 12.6885% |
| 56 days | 40 bps | 2.8886% → 3.6247% | 16.0483% → 12.9732% |
| 56 days | 60 bps | 2.8172% → 2.9271% | 13.3582% → 13.3861% |

The three losing comparisons are the same 28-day starting account at each fee:
return changes of -0.158061, -0.124328 and -0.059357 percentage points. Drawdown
does not improve in every account or group. This is a protective-order behavior
correction with a favorable average historical result, not a proven new source
of alpha. The reused January–September fixture has hourly prices and synthetic
books; it does not reproduce actual minute liquidity, queueing or live fills.

An independent Decimal reference reconstructed cash, quantities, fees, marks,
peaks, cooldowns and decision state: **123,105 exact comparisons**, maximum
metric error zero. It rejects an old below-stop-buy path when the guard is
required. The first historical runner incorrectly asserted all reports would
be unchanged. Its failure is retained; the subsequent audit includes all changed
accounts and explains them by the old below-stop buys.

## Exact release identity and tests

The running binary was reproduced byte-for-byte from commit
`1ef4429233f550598bd96fdac64aff792f5ec009`, Go 1.25.0, Linux amd64 v1,
CGO disabled, `-buildvcs=true -trimpath`, with the dirty-worktree VCS stamp.
The remote source directory and newer local HEAD each differ from that release;
neither was used as an assumed deployment baseline.

Only `internal/bot/engine.go` changes: the stop guard plus one gofmt alignment.
The deployable candidate contains neither the quote-aware experiment nor newer
mirror changes. Its qualification passed:

- 102 native tests, 102 race tests, no skips, and `go vet`;
- 30 complete native cycle comparisons, including five guard regressions;
- all 45 complete historical ledgers and reports identical to the independently
  audited guarded results.

Candidate SHA-256:
`4cc9122477f3e5c6e030ecf5df4aaf73ceb4bf31c3747208944c737f99d44805`.
Reproduced current/rollback binary:
`eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`.

The release is packaged for owner review and activation. No installed live
binary, account state, service or live trading configuration was changed.

## Future-data paper comparison

The original quote-aware/control study remains frozen. A separate six-account
study applies this guard to both arms at 30/40/60-bps fees, starting with 495
USDT each at source index 78, **2026-09-24 03:14:15 UTC**, and ending at index
10079, **2026-10-01 01:55:15 UTC**. Each uses the same immutable public observations.

Remote prelaunch validation reproduced 55 native cycles and their money
accounting. The first two future source batches were independently verified:
12 native cycles, six exact-release guarded control comparisons, matching raw
sources, receipt chain and clocks, no gaps or failures. All six accounts remain
at 495 USDT with zero fills. The original unguarded study was independently
confirmed flat immediately before the guarded start, so both studies have a
matched economic initial state at that point. Registration and launch preceded
the first capture. No prospective profitability is established by this prefix.

These are future-data observed-book paper replays. Source-availability time and
actual computation time are recorded separately; contemporaneously committed
exchange orders are not claimed. Immediate native IOC paper fills remain an
assumption. The one-week study cannot establish 28-day risk or long-run returns.

## Evidence

Root: `/vfast/data/trading_research_20260924/poloniex_stop_topup_guard_v1`.

- `independent_verification.json` and `independent_audit/`: all account results.
- `release_source_rebuild/verification.json`: byte-identical incumbent rebuild.
- `release_candidate/validation.json`, `guard.patch`, `parity/verification.json`:
  candidate sources, tests and exact full-ledger compatibility.
- `guarded_future_launch/`: frozen protocol and launch validation.
- `guarded_future_first_two_audit/verification.json`: independently checked start.
- `release_package/README.md`: owner activation and rollback instructions.
- `packaging_verification.json`: archive and payload checksums.
