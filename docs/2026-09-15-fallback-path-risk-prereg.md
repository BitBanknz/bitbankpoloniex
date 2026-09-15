# Fallback validation must observe the holding path

Register before changing model training or evaluating new market-model returns.
`Train` currently updates fold equity, peak and maximum drawdown only at each
24-hour trade exit. A profitable exit can conceal a large completed-hour loss
during the hold. The 15% model-acceptance gate therefore needs a path audit.

Construct a deterministic rising-price history whose fixed target is above
the unchanged 60bps round-trip hurdle. In the final fold's first simulated
hold, add one completed-hour close 40% below the price trend, followed by
recovery before its scheduled exit. Keep all training data before that fold
and that trade's entry/exit opens unchanged. The validator must record the
large intermediate loss and reject the model even when terminal trade returns
remain positive. Preserve original source/hash and the failing test result.

If reproduced, retain targets, features, fitted ensembles, fold boundaries,
decision rules, fees and terminal equity. During an entered hold, value at
each completed hourly close and then the scheduled exit open. Reserve the
existing fixed round-trip cost from the entry onward. Include entry cost,
intrahold peaks and the exit in peak/drawdown accounting. Do not use future
holding-path values to alter an earlier prediction. Finite risk statistics
are mandatory for acceptance. Version the validation contract so old
exit-only receipts cannot satisfy the repaired risk gate.

Tests must preserve terminal returns and fitted predictions while detecting
the transient loss, reject nonfinite risk receipts and old validation schema,
and leave the existing chronological and execution tests passing. Before any
remote deployment, audit current fallback artifacts and compare the same
retained public history under the old and corrected validators. Preserve live
state and credentials. Poloniex trading and authenticated API calls remain on
the remote machine. This is a validation defect audit, not a PnL improvement
or permission to loosen the drawdown gate.

Before paired historical results, freeze the last 3,000 completed hours from
every available `data/archive-hourly/*/candles.csv`, with an as-of boundary of
2026-09-15T00:00:00Z. Retain failures for short, nonfinite or noncontiguous
histories; do not search for a better segment. Run identical input JSON through
the preserved old and corrected Go validators. Require byte-identical fitted
ensembles and exact fold terminal returns, trade counts, errors and boundaries.
Corrected drawdown must never decrease; a formerly rejected model must never
become accepted through this change. Record all acceptance changes. This is
paired validation-accounting evidence on an existing selected archive.
