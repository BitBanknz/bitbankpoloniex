# Perpetual funding as an orthogonal add-on signal: pre-registration

Every signal tested so far uses Poloniex price/volume, as does the production forecaster. Perp funding (Binance USDT-M,
public API) is independent information; the hypothesised effect is contrarian (crowded longs, high funding, lower
forward return).

Feature, fixed now: for each of the 8 live pairs (Binance symbols BNB, ETC, ETH, 1000PEPE, SUI, TRX, XRP, ZEC USDT),
F = mean funding rate over the 72 hours before the 00:00 UTC decision, converted to a per-day cross-sectional z-score;
score s = -F. Label: next-day open(01:00)->open(01:00) return, as in the ranker study.

Stage 1 (window A, 2023-01-01..2025-12-31, no 2026 data): mean Spearman IC of s over the live 8-pair cross-section
must be positive with t > 2, otherwise the idea is dropped and nothing is replayed. A 1-day-mean funding variant is
reported as a diagnostic only.

Stage 2 (only if stage 1 passes): one replay candidate. Raw production scores (recovered by inverting the EMA in the
fixture, exact) are combined as z = 0.75*raw + 0.25*z(s), re-z-scored per day, then smoothed with the production EMA 0.35.
Same engine, profile and five-rule test as `2026-09-30-config-sweep-prereg.md`; promotion also needs window-B (2026)
IC of z not below production's 0.0857. No weight is tuned. If it passed, confirmation on 14/42/84-day folds at 30/50 bps
would follow with the same four rules and 60% pooled-wins bar as the hold-time confirmation.
