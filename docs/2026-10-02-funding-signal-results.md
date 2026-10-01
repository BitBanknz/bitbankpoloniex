# Perp funding add-on: not promoted, no replay run

Registered in `2026-10-02-funding-signal-prereg.md`; code `research/ranker20261001/{fetch_funding,funding_ic,make_fixture_funding}.py`.

Stage 1 (window A, 2023-05-05..2025-12-31 because PEPE/SUI perps start May 2023; 968 days): IC of -F3 (72h mean funding, cross-sectional
over the 8 live pairs) = 0.0264, t = 2.07 (1-day variant 0.0291, t = 2.25; days are autocorrelated so t is generous). The registered
bar (t > 2) was met only just.

Stage 2 precondition (2026 fixture window, 236 days): production smoothed-score IC 0.0857 (t=3.00); the registered blend
(0.75 raw production + 0.25 funding z, EMA 0.35) IC 0.0771 (t=2.66); funding alone IC 0.0144 (t=0.55). The blend is below production,
which the registration treats as a failure, so no replay was run and nothing is promoted. Funding adds no usable information beyond what the
production model already captures; the weak window-A edge did not persist into 2026.

Tested this session without a passing result (all on the same 236-day fixture or its ranks): config grid, ranker (+universe), stops, minimum hold,
EMA constant, funding add-on. Open evidence sources: the forward collector and the paper A/B (`2026-10-02-forward-ab-prereg.md`).
