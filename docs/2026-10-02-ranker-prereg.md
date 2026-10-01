# Walk-forward cross-sectional ranker: pre-registration

Question: can a ranker trained on the local 56-market hourly archive (2019-2026-09-10) beat the
production rank scores on the frozen 8-pair replay? Production scores (fixture, 236 days
2026-01-14..2026-09-06) have IC 0.0857 (t=3.0) and top-3 excess +0.152%/day vs next-day
open(01:00)->open(01:00) returns; 30d momentum IC is -0.004.

Data/features (`research/ranker20261001/feats.py`): daily decision at 00:00 UTC from bars through
23:00; returns 1/3/7/14/30/60/120d, vol 7/30d, range, dollar volume level/change, distance to 30d
hi/lo, returns relative to BTC; per-day cross-sectional rank normalisation over assets with trailing
30d mean daily quote volume >= 100k USDT. Label: next-day log return open(01:00) to open(01:00 +24h),
cross-sectionally ranked. Training uses only days whose label closed before the decision day;
refit every 30 days, expanding window from 2020-01-01.

Window A (tuning, 2023-01-01..2025-12-31, walk-forward OOS) selects the model among a frozen family:
ridge (alpha 1,10,100), LightGBM (3 configs: leaves 7/15/31, 200 trees, lr 0.03, min_data 200),
MLP on GPU (2 configs: 64x2 and 128x2, dropout 0.2, 8 seeds averaged). Metric: mean IC over the 8 live
pairs, ties broken by top-3 excess. Window B (2026-01-14..2026-09-06) is touched only after the
selection is frozen, once.

Replay candidates (only two, so selection bias stays small): (R1) selected model scores alone;
(R2) 50/50 average of per-day ranks of the selected model and the production scores (weight fixed a
priori; production scores do not exist before 2026 so it cannot be tuned). Same engine, deployed
profile (slots 3, 120h, reserve 0.4, halts 25/8), fees 30/40 bps, geometries continuous/28d/56d.

Promotion: same five-rule test as `2026-09-30-config-sweep-prereg.md` against the production-score
baseline, plus window-A IC > 0.03 for the selected model (otherwise no replay). Deployment would
additionally need a safe path to feed the scores to the live bot; otherwise recommendation only.
