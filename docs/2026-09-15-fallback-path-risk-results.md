# Fallback drawdown now includes the holding path

The old fallback validator accepted a model that experienced a 40% completed-
hour loss during a hold, recovered before exit, and reported zero drawdown.
Its final fold still returned 22.05%. The regression test reproduced that
failure before the fix. The repaired validator observes entry cost, each
completed hourly close and the scheduled exit, so the same model is rejected.

Training targets, feature values, model fitting, entry decisions, fold
boundaries and terminal return arithmetic are unchanged. The existing fixed
round-trip cost is reserved from entry onward for risk marking. The 15%
acceptance ceiling remains unchanged, and nonfinite or negative drawdown
receipts are rejected. `ValidationSchema=hourly-holding-path-dd-v1` is required;
legacy exit-only receipts cannot be presented as satisfying the corrected gate.

The [registered paired audit](2026-09-15-fallback-path-risk-prereg.md) included
56 retained histories, each with 3,000 completed hourly bars. Nineteen of the
75 archived symbols failed the predetermined data requirements and were
recorded without searching for replacement segments. All 224 fold pairs had
exactly identical terminal returns, trade counts, prediction errors and time
boundaries. All 280 retained models per arm (four fold models plus the final
model per symbol) were identical. An independent position-quantity/price/cost
oracle reproduced every corrected drawdown within 1e-12.

Drawdown increased in 44 folds, by as much as 20.23 percentage points. Three
folds crossed the existing 15% ceiling. Both validators accepted zero complete
models on this particular archive because other required gates already
failed. This fixes risk measurement; it does not establish a new profitable
fallback or an improvement in realized account PnL.

All package tests and race checks passed. Tests cover the recovered loss,
entry cost, terminal-return preservation, nonfinite risk and validation-schema
rejection. Existing chronological, model and execution checks passed as well.
Full source snapshots, failing and passing tests, public histories, overlays,
all retained models and the independent oracle results are under
`/vfast/data/trading_research_20260915/poloniex_path_risk`.
Compact evidence is in [data/path_risk_20260915](../data/path_risk_20260915).

The remote preflight at 2026-09-15T03:03:42Z found no fallback model files for
live or account-paper, and 56 legacy paper models with zero accepted models.
This records current deployment impact, not permission to assume future
receipts are safe. Completed-close drawdown still does not measure intrahour
extremes, order latency, partial fills, portfolio allocation or live capacity.
