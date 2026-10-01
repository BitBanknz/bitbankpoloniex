# Out-of-sample check on 2026-09-10..10-01 (descriptive): pre-registration

Production daily scores for 2026-09-10 (EMA cold start) .. 2026-10-01 were rebuilt from public Poloniex candles, the two bundle models and the
production feature code (`research/ranker20261001/reproduce_prod.py`). Validation: raw scores equal the remote's current raw scores with max error
0.0, and the full 22-day EMA chain equals the remote's current `smoothed_scores` with max error 0.0 at the manifest's model switch (hour 497256).
These days postdate every tuning step in this study.

Replay arms on this 3-week fixture (same engine, live profile slots 3 / reserve 0.4 / halts 25-8 / cooldown 120h, fees 30 and 50 bps, continuous and 14-day folds):
(A) live: EMA 0.35, hold 72h; (B) hold 24h; (C) EMA 0.25. Three weeks is under one fold of the earlier geometries, so this is a falsification
check, not a confirmation: no deployment follows from it. Reading rule fixed now: an arm that does not beat A on continuous return at both fees counts
against that near miss; an arm that does is mild support only. The paper A/B and forward collector remain the decision path.

## Result (2026-09-10..10-01, 21 days; `research/ranker20261001/oos_weeks_results.txt`)

Continuous return / max DD at 30 and 50 bps: (A) live +4.08/4.9 and +3.41/5.1; (B) 24h hold +3.61/4.7 and +2.88/4.9;
(C) EMA 0.25 +6.26/3.3 and +5.70/3.3 (fills 24 vs 29 for A). Under the reading rule fixed above, B does not beat A at either fee (counts against the
24h hold) and C beats A at both (mild support for EMA 0.25, lower drawdown and lower turnover). 14-day folds: A 5.97 and 0.23 (30 bps), C 5.97 and 0.51, B 5.38 and -0.79.
Three weeks is less than one fold of the earlier geometries, and EMA 0.25 earlier failed the 14/42/84-day confirmation (38% pooled wins), so the evidence on it is mixed, not confirmed.
Nothing is deployed to the live account on this basis; EMA 0.25 is added as a third paper arm (see `2026-10-02-forward-ab-prereg.md`).
