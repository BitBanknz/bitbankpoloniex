# Longer re-entry cooldown: validation and remote deployment

The fixed 120-hour post-sale cooldown improves every preregistered comparison
against 72 hours. It is deployed to the remote live service at the existing
495-USDT budget and 49-USDT order cap. It changes when a sold symbol can be
bought again; the 72-hour minimum hold, ranks, stops and exposure limits remain
the same. Existing persisted deadlines are retained until subsequent sales.

This is reduced churn on already examined history. The continuous cash-start
candidate still loses money, including under doubled fees; it is not evidence
that future trading will be profitable.

## Frozen experiment

The prediction2 protocol is
`docs/2026-09-14-crossbot-risk-selector-prereg.md`. Only 72 versus 120 hours was
tested, without searching intermediate durations. Continuous and 28-day
cash-start checks had to improve return and not worsen worst return or maximum
drawdown at 30/60-bps fees per side before opening 56/84-day or imported-ETH
checks. All those later comparisons passed too.

The fixture contains 5,664 hourly observations, January 14 at 01:00 UTC through
September 7 at 00:00 UTC, and eight symbols. It uses the actual standalone
Engine through a loopback HTTP fixture with no credentials or exchange writes.
The clock is replaced only in the research overlay. Daily causal rank forecasts
are available only in their issue/execution window; protective checks continue
when signals expire. The imported-book scenario starts with 20% ETH and 80%
cash; it is a sensitivity test, not reconstruction of today's four holdings.

There are 144 result cells across 16 paired surfaces: two cooldowns, two fees,
two starting books and four geometries. These are not 144 independent folds.
The 28-day geometry has eight complete windows and one 12-day tail; 56 days has
four complete windows and a 12-day tail; 84 days has two complete windows and
a 68-day tail. Arithmetic fold means include these tails. Continuous replay
retains cash, holdings, risk state and cooldowns throughout the full path.

## Results

All numbers are percentages; arrows show 72 hours to 120 hours. DD is the
largest within-path drawdown over that surface. Returns include the modeled
spread and fees, with terminal positions marked rather than forcibly sold.

| Starting book | Window | Fee/side | Mean return | Worst return | Maximum DD |
|---|---|---:|---:|---:|---:|
| Cash | Continuous | 30 bps | -2.7850 → -0.5129 | -2.7850 → -0.5129 | 9.0390 → 3.6227 |
| Cash | Continuous | 60 bps | -4.4727 → -1.2546 | -4.4727 → -1.2546 | 9.6202 → 4.0028 |
| Cash | 28 days | 30 bps | 0.9862 → 1.2919 | -7.3409 → -5.0742 | 8.2012 → 5.5403 |
| Cash | 28 days | 60 bps | 0.6383 → 0.9832 | -8.0066 → -5.5069 | 8.7816 → 5.9729 |
| Cash | 56 days | 30 bps | 0.9320 → 2.0656 | -5.2004 → -2.1471 | 9.0390 → 4.0362 |
| Cash | 56 days | 60 bps | 0.3805 → 1.6292 | -6.3728 → -2.6783 | 9.6202 → 4.3895 |
| Cash | 84 days | 30 bps | 1.4594 → 3.5044 | -2.9713 → -1.0085 | 9.0390 → 5.4013 |
| Cash | 84 days | 60 bps | 0.6147 → 2.8732 | -4.4175 → -1.5064 | 9.6202 → 5.8140 |
| 20% ETH | Continuous | 30 bps | -1.8816 → 0.3905 | -1.8816 → 0.3905 | 8.1993 → 3.0798 |
| 20% ETH | Continuous | 60 bps | -3.5727 → -0.3545 | -3.5727 → -0.3545 | 8.7558 → 3.2160 |
| 20% ETH | 28 days | 30 bps | 0.9425 → 1.2481 | -6.4376 → -5.5355 | 7.3620 → 6.0016 |
| 20% ETH | 28 days | 60 bps | 0.5411 → 0.8861 | -7.1066 → -6.0270 | 7.9175 → 6.4930 |
| 20% ETH | 56 days | 30 bps | 1.1081 → 2.2417 | -4.2970 → -2.3728 | 8.1993 → 4.0574 |
| 20% ETH | 56 days | 60 bps | 0.5077 → 1.7564 | -5.4728 → -2.9634 | 8.7558 → 4.4708 |
| 20% ETH | 84 days | 30 bps | 1.4040 → 3.3774 | -2.0679 → -0.1549 | 8.1993 → 6.1849 |
| 20% ETH | 84 days | 60 bps | 0.3500 → 2.6764 | -3.5175 → -1.1386 | 8.7558 → 6.6651 |

Ordinary-fee continuous cash-start fills fall from 66 to 29. The 72-hour
incumbent reproduces 160 prior metric checks. After adding the production
configuration field, all 40 native-code screen rows match the experimental
overlay exactly in report and boundary fields. Input/source hashes were checked
again after replay. Full race tests and vet pass; regression tests cover
default/configured deadlines, fill accounting, bounds and retained saved state.

Hourly-open synthetic books, five-bps half-spreads, prior-hour volume capacity,
current market contracts and current-member symbols do not reconstruct
historical order books, minute stops, queue position, delistings or partial
fills. These histories have been examined by earlier campaigns. The daily
forecaster was reused, not retrained by this cooldown experiment. The separate
BitBank server forward-paper portfolio is a different ledger and strategy.

## Standard paper account size

The standard paper service uses a 1000-USDT budget and 25-USDT order cap. A
separate preregistered scale check retained that configuration and the same
72/120-hour pair, using continuous and 28-day cash-start paths at both fees.
All four paired surfaces passed in 40 additional cells; input hashes remained
unchanged. This is a narrower check than the live-account confirmation suite.

| Paper-account surface | Mean return, 72h → 120h | Maximum DD, 72h → 120h |
|---|---:|---:|
| Continuous, 30 bps | -1.1050% → -0.2129% | 2.2945% → 0.9190% |
| Continuous, 60 bps | -1.5150% → -0.3545% | 2.4404% → 0.9996% |
| 28 days, 30 bps | 0.2421% → 0.2742% | 2.0818% → 1.3992% |
| 28 days, 60 bps | 0.1585% → 0.2005% | 2.2276% → 1.5085% |

Worst 28-day return also improves from -1.8539% to -1.2815%, and from -2.0221%
to -1.3908% under doubled fees. Standard paper therefore retains 120 hours.
`paper-scale/` contains the exact command/environment, 40 rows, configuration,
hashes and paired summary. Use `--budget 1000 --max-order 25` to reproduce.

## Reproduction and artifacts

`research/cooldown20260914/prepare.py --out <new-directory>` creates a frozen Go
overlay. Its defaults are 495/49 and continuous/28-day geometries. Use
`--geometries 56 84` for the confirmation windows. Set
`POLONIEX_LEDGER_FIXTURE` and `POLONIEX_LEDGER_MARKETS` to the absolute
`data/frontier_20260912/ledger/{fixture,markets}.json` paths, and
`POLONIEX_LEDGER_OUT` to a new result JSONL. Then run
`go test -overlay <absolute-overlay.json> ./internal/bot -run '^TestFrozenLedgerReplay$' -count=1 -v -timeout 20m`.
Use `POLONIEX_IMPORTED_ETH=1` for the imported-book scenario. A memory-backed
`TMPDIR` avoids unnecessary ledger I/O without changing the Engine or results.

Evidence under `data/cooldown_20260914/` includes the original screen
`results-memory.jsonl`, `cold-confirm/results.jsonl`,
`imported-confirm/results.jsonl`, `complete-comparison.json`,
`native-confirm/{results.jsonl,parity.json}`, source/input hashes, saved
continuous ledgers and test logs. Retained initial failures include a relative
fixture-path error and an interrupted slow disk replay; neither was counted as
a completed result or used to change parameters.

## Deployment and rollback evidence

Poloniex continues to trade on `administrator@93.127.141.100`, in
`/nvme0n1-disk/code/bitbank-poloniex`. The candidate binary SHA-256 is
`c5d0364880ad03dec6a6838e9a1b5d36ef975dcfb676ac857464581357e78ec2`;
the previous binary is
`275563f00a62cbb43c53206b4c83904a1daf07715360da5665ef551ae791a1a2`.
Live PID 99573 became 1044832; standard paper PID 99575 became 1044834.
Both run with `--cooldown-hours 120`. The experimental fallback account retains
its existing process and 72-hour default. Credentials stayed on the remote host.

The initial deployment verifier split process arguments using a literal
backslash-zero instead of NUL. The new processes were correct, but its error
handler restored older on-disk files without restarting those processes.
Finalization corrected that verification bug and reconciled the desired binary,
unit files and systemd-loaded configuration to the already running candidate.
The final checks compare actual process arguments and mapped binary hashes,
installed files, loaded settings, process IDs and complete ledger continuity.
There is no unresolved mixed deployment.

At 10:21 UTC both services were active with zero restarts and state less than a
minute old. Live retained 385.5250528883 cash, four holdings and 14 fills; paper
retained 940.10514904628 cash, three holdings and nine fills. Neither had a
pending order or halt. Cash, quantities, entry timestamps, fills, processed IDs,
risk state and existing cooldowns match the stopped ledgers; marks may advance.
No test trade was submitted.

Private local evidence is in `data/cooldown_20260914/release/`. Remote
`data/cooldown-release-20260914/` retains the prior binary and units, stopped
ledgers, staged candidate, deployment receipt and post-rollout health.
Rollback means stop the affected service, restore the prior executable/unit,
reload systemd and start, retaining its latest ledger. Never overwrite a ledger
that has advanced with the pre-deployment snapshot. Existing 120-hour deadlines
also remain valid if the configuration is restored to 72 hours.
