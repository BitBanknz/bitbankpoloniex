# Failed experiments

Rejected ideas with evidence; check here (and docs/*-results.md) before re-running anything.

- 2026-10-14 [hourly rotation decisions](2026-10-14-hourly-cadence.md): hourly cadence, 0h delay, exit debounce, hourly-origin training, Chronos-2 features: all lose to the daily window; near miss d_hema (hourly-EMA ranks, daily execution) fails G1.
- 2026-10-14 [hourly-native cost-aware ridge + wider universe](2026-10-14-hourly-native.md): best arm hn_xs_m24 beats incumbent on mean/worst/DD in all cells but paired wins 51-54% < 55% gate; U+ (24 pairs) does not replicate. Near miss, not deployed.
- 2026-10-23 [P1 ranker refit cadence / phase bag / label horizon + DD weight](2026-10-23-p1-ranker-refit-label.md): all 7 arms fail G1; the deployed 28 d / 72 h / DD .5 recipe is a local optimum on 8p.
