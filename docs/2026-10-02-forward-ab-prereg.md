# Forward paper A/B of the 24h minimum hold: pre-registration

Why: every in-sample slicing of the 236-day fixture is exhausted (see `2026-10-02-exit-rules-results.md`); the 24h hold
beat the live 72h hold on mean return and max drawdown in all 18 replay cells but won only 46% of paired folds, so it
was not deployed to the real-money account. A zero-risk way to get unseen evidence is two paper traders on the remote
reading the same live signals and books, identical except `--min-hold-hours`.

Arms (remote, paper mode only, no orders, no credentials used for orders): `bitbankpoloniex-paper-ab-control`
(`--min-hold-hours 72`) and `bitbankpoloniex-paper-ab-mh24` (`--min-hold-hours 24`); both `--mode paper --budget 495
--max-order 49 --slots 3 --cooldown-hours 120 --slot-top-up --cash-reserve 0.4 --halt-peak-dd 0.25
--halt-daily-loss 0.08`, state `data/paper-ab-control` / `data/paper-ab-mh24`, the guard-merged binary
`bin/bitbankpoloniex-ab` (a separate file; the live binary and unit are untouched).

Decision (fixed now): after at least 56 calendar days from the first completed cycle, compare equity from the
start. mh24 is promoted to a live proposal only if its return exceeds control's, its maximum drawdown is no higher,
and it leads on at least 60% of completed weekly (7-day) windows. Otherwise it stays rejected. A live change would
still need the repo's guard-style qualification and an authenticated deploy. An interim look before 56 days is
descriptive only. Paper fills use visible quotes, so this tests the rule, not execution.

## Deployed

2026-10-01 14:46Z on the remote: binary `bin/bitbankpoloniex-ab` (sha256 `ed2bb2fb…`, built from commit 62a9565 which adds
`--min-hold-hours`, default 72 = unchanged), states `data/paper-ab-control` and `data/paper-ab-mh24` initialised at 495 USDT cash,
units `deploy/remote/bitbankpoloniex-paper-ab-{control,mh24}.service` installed to /etc/systemd/system and started. Both
completed cycles in paper mode with no pending intent; the live service and binary (`4cc91224…`) were not touched. Stop and
remove: `systemctl disable --now bitbankpoloniex-paper-ab-{control,mh24}`; their state dirs can be deleted freely.
