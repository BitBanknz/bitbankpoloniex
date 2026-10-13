# Forward paper A/B of hourly-EMA ranks (daily execution): pre-registration — 2026-10-14

Why: in the 10-14 hourly study (`failedexperiments/2026-10-14-hourly-cadence.md`), `d_hema` was the only near miss.
It is an hourly inference of the production bundle, smoothed by a continuous hourly EMA (alpha .0178, the same
half-life as the daily .35 EMA). It is sampled at 00:00 and traded in the normal 01:00 window. In replay it is
+0.72 pp/28d ex-ZEC (t 2.3) but -0.55 on 8 pairs, and it fails G1. Forward data is the only clean evidence.
The owner also wants bitbankgo to publish ranks every hour; this provides that without touching the live consumer.

Components (remote, all new, paper only; no existing unit, binary, ledger or bundle is modified or restarted):
- `bitbankgo-rotation-hourly.{service,timer}`, at :02:30 UTC each hour. It runs bitbankgo
  `scripts/rotation_hourly_inference.py` (copied to `data/rotation/runtime/`) on the production bundle. It writes only
  `data/rotation/hourly-state/forecast-hourly.json`, seeded once from the production `forecast.json`.
  Parity: it equals the research hourly scores/EMA exactly (`research/hourly20261013/parity_hourly_job.py`:
  raw diff 0, EMA diff 5e-15).
- `bitbankpoloniex-hema-signal` on 127.0.0.1:18748 (`research/forward/hourly_sidecar.py`). It serves the daily schema with
  the 00:00 snapshot for the unchanged daily consumer, and `/api/trading-bot/rotation-signals-hourly` with
  always-current hourly ranks.
- `bitbankpoloniex-paper-hab-control` (production ranks, 8745) and `bitbankpoloniex-paper-hab-hema` (sidecar). Both use
  `bin/bitbankpoloniex-hab`, a byte copy of the live Go binary (6f4efd98), with the live profile in paper mode,
  495 USDT each, started the same day.

Decision (fixed now): after at least 56 days, from the first completed cycle of both arms, hema becomes a live
proposal only if all three hold:
- its return exceeds control's;
- its max drawdown is no higher;
- it leads on at least 60% of completed 7-day windows.

Otherwise it is rejected. A live switch would point the live unit's `--predictions` at the sidecar, with no binary change.
That needs the guarded switch pattern of `switch_live_to_sidecar.py` and the owner's go-ahead.
The hema snapshot is not ready until the first 00:00 hourly issue after deploy. Until then the hema arm pauses entries (503) and only
runs protective exits, so both arms count from the first day on which both completed a 01:00 window.

Stop/remove: `sudo systemctl disable --now bitbankgo-rotation-hourly.timer bitbankpoloniex-paper-hab-{control,hema} bitbankpoloniex-hema-signal`;
delete `data/rotation/hourly-state`, `data/paper-hab-*`, `bin/bitbankpoloniex-hab`, `bin/hourly_sidecar.py`.
