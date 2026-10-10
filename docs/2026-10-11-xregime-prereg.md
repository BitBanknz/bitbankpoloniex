# Cross-exchange ranker, BTC regime gate and entry execution — preregistration 2026-10-11

Written and pushed before any candidate result exists. Research only; live units unchanged.
Inputs are reused (2023-06..2026-10 panel, e2306 causal scores, archived book shapes); this is
not fresh untouched out-of-sample data, and every fold below was already examined by earlier
studies with other candidates.

## Simulator (incumbent = live release)

- Engine: commit `f3aa665` (live binary `6b10fdb6`) behind the loopback mock-HTTP fidelity
  harness of `research/fidelity20261009`, extended only by default-off research hooks. With
  hooks off the build must reproduce the 10-09 `s3_h72_c120_r0.4_safe` seed-1 results and curves
  byte-for-byte, or the study stops.
- Production argv: budget 495, max order 49, 3 slots, cooldown 120h, min hold 72h, top-up,
  reserve 0.4, halts 0.25 peak / 0.08 daily, min-exit 24.5, exit-ramp 20; harness WindowCycles 60,
  FollowCycles 59, Book `archive`, book seeds 1, 2, 3.
- Costs: FeeRate 0.0014 (measured) and 0.0040 (stress), each plus archived-book spread/depth.
- Folds: `e2306` 42 refit blocks (2023-08-02..2026-10-06). Development = folds 0-29;
  confirmation = folds 30-41. Universe 8 pairs; ex-ZEC universe for confirmation.
- Fold metrics are computed on the seed-mean hourly equity curve (mean of the 3 seeds at each
  timestamp, start point = budget, last point = liquidation net of fee), with
  `poloniexmojo/research/study.py` `metrics`/`aggregate`/`compare` (sha256 3a64a76b…).

## Fixed candidate set (no additions after any result)

1. `xr_feat`: production ranker recipe (`fit_refresh` features + ranks, lgbm_rank 70/5/2/λ20,
   same refit grid, 5-day purge, EMA 0.35) plus six Binance spot features per pair from
   completed hours only: 24h and 168h Binance log return; Poloniex/Binance log close basis
   (last hour, 24h mean); Poloniex/Binance quote-volume share log change (24h minus 168h);
   Binance quote-volume surge log(24h mean / 336h mean); plus their same-timestamp ranks.
   Binance hourly data: `bitbankkucoin/data/binance/1h` (KCB1) extended from
   `data-api.binance.vision`; missing hours forward-fill close with zero volume.
   A control rebuild without the six features must reproduce `e2306.npz` raw scores within
   1e-12, else the arm is void.
2. `btc720_entry`: incumbent scores; no new entries or top-ups on a UTC day when Binance
   BTCUSDT's last close at or before 00:00 is below the mean of its last 720 hourly closes.
   Stops, ramps and rotation exits unchanged.
3. `btc720_flat`: as 2, and on gated days the target set is empty, so rotation exits
   (after the 72h minimum hold) move to cash.
4. `xr_feat_btc720`: arms 1 and 2 combined.
5. `exec_buy`: incumbent signals; BUY orders use a 0.3% band above the ask and 25% participation
   of in-band depth (live: 0.1%, 10%). Spread gate, sells and all limits unchanged.

## Gates, in order, never weakened

1. Development (folds 0-29), separately at 0.0014 and 0.0040: mean fold return and daily
   Sortino strictly above the incumbent, paired fold wins >= 18/30, worst fold no worse,
   calendar-month and rolling-30-day drawdown <= 30% (35% absolute ceiling).
2. Freeze at most one finalist: largest 0.0040 mean improvement among arms passing gate 1.
   No passing arm means stop; confirmation results are not inspected to rescue an arm.
3. Confirmation (folds 30-41): the same gates (wins >= 8/12) at both costs, in the 8-pair and
   the ex-ZEC universe.
4. 84-day scale-up: 14 continuous windows of 3 consecutive folds (no reset inside a window),
   same gates (wins >= 9/14) at both costs. For a ranker finalist also: trained from 2023-06
   versus from 2024-10 on common windows, the longer history must win mean and Sortino without
   a worse worst window.
5. Only then: full-data fit of the frozen recipe through the last completed hour, holding out
   the final 7 days as a validation slice (sanity only, never promotion evidence), with all
   source, config and data hashed.
6. Live change additionally requires a forward paper A/B against the incumbent on the same
   host. Nothing in this study changes a live unit.
