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

## Third arm: EMA 0.25 (added 2026-10-01 15:05Z)

Motivation: the 21 unseen days (`2026-10-02-oos-weeks-prereg.md`) favoured EMA 0.25 (+2.2 points, lower drawdown, fewer fills) and counted against the
24h hold, while the 14/42/84-day confirmation of 0.25 had been negative, so the evidence is mixed and needs forward data.
Implementation without touching the production forecast job or the bot: `research/forward/ema_sidecar.py`, a read-only localhost sidecar
(`bitbankpoloniex-ema25-signal.service`, port 18746; 8746 is taken by another service) that proxies the real rank endpoint's availability and shape and
replaces `rank_scores` with an EMA(0.25) of the production `raw_scores`, starting from the production smoothed scores on its first day. Offline test:
`research/forward/test_ema_sidecar.py`. Arm: `bitbankpoloniex-paper-ab-ema25` (state `data/paper-ab-ema25`, hold 72h, otherwise identical to control).
Same decision rule as above, evaluated against control after >= 56 days: higher return, no-higher max drawdown, and ahead on >= 60% of weekly windows. If it passed, the
live route is the same sidecar (change the live unit's `--predictions` URL) with no new trading binary. Stop: `systemctl disable --now bitbankpoloniex-paper-ab-ema25 bitbankpoloniex-ema25-signal`.

Prepared, not executed: `research/forward/switch_live_to_sidecar.py` (run on the remote) changes only the live unit's `--predictions` URL to the sidecar. Dry run by default; with
`--execute` it requires an unchanged unit hash, the running binary `4cc91224…` with the exact expected arguments, no pending intent, and a sidecar state file for the current forecast
day (proof it served an in-window request); it backs up the unit and the live state, restarts the service, requires two completed cycles with state continuity, and on any failure restores the
old unit and re-verifies. It is run only on an explicit instruction from the user or after the registered forward rule is met.
