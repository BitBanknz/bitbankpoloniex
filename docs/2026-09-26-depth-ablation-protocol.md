# Isolate displayed depth in the recorded-book account simulator

The sealed exit-reserve study found a coverage mismatch: all 135 historical
accounts stayed at or below eight daily orders, whereas the recorded-book
baseline used twelve buys on September25. Test the depth assumption directly
before changing any strategy. This is a simulation diagnostic on reused data,
not a new alpha candidate or a promotion screen.

Use exactly the authenticated public prefix78–3297 and the native binary from
the sealed exit-reserve study. Keep its guarded baseline, cap9 and reserve3
policies, three fees (30/40/60 bps), initial495 USDT, order49, all signals,
marks, market contracts, spreads, prices, receipt clocks and freshness rules.
Reuse the fully reconciled observed-depth accounts as the matched references.
No future capture, later book, price resampling, forecast retiming or stale
quote repair is permitted.

The one counterfactual replaces only positive displayed quantities on valid,
fresh, uncrossed, ordered books. Each positive quantity becomes the greater of
its original value and ceil(1000 *49 / minimum price across that book's two
sides), in base units. Zero quantities stay zero. All prices, level counts,
timestamps, status codes and other response fields are byte-value unchanged.
Invalid, stale, unavailable or entirely zero-size sides are not repaired.
This makes liquidity deliberately abundant relative to a49-USDT order while
preserving the native order price calculation. It is not a calibrated liquidity
model, an estimate of executable volume, or a plausible execution guarantee.

Validate adapter immutability, identity mode, numeric/ordering failures,
freshness boundaries, zero size, price-level projection and abundant capacity.
Replay all256 sealed full-cycle fixtures under identity and abundant-depth
inputs; independently reconcile money, exact clocks and both daily budgets.
Repeat the abundant-depth outputs under the existing race binary. Identity must
match every original full output and request path. No native engine change or
new build is needed; authenticate the prior native suite/race/vet evidence.

Run all three policies at all three fees through all3220 captures with their
own continuing account state: 28,980 new native cycles. Preserve every source
hash and adapter decision, native/accounting path, final state, missing mark,
fee, fill, turnover and drawdown. Independently reconcile each transition.
Do not select a fee or policy after the result. Compare the full nine-account
matrix against the sealed observed-depth matrix, including first differing
fills, daily order-count distributions, days reaching nine/twelve orders,
entry-window executable-depth limitations, and return/drawdown changes.

Separately test whether the native order-budget policies differ under each
depth model. Record equality as nonactivation, not improvement. Check that the
price/clock projection matches every source packet and that the quantity floor
does not introduce future information. Sampled drawdown remains a diagnostic;
no live-risk certification follows from a two-day reused prefix. Sequential
snapshots, hypothetical full IOC fills, unobserved queue position and market
impact remain limitations. A displayed book is not proof of actual fills.

Create reusable coverage output that makes absence of policy activation explicit
for later account-model comparisons. Keep the earlier historical/observed
studies sealed. Do not modify production, existing paper workers or recorders.
