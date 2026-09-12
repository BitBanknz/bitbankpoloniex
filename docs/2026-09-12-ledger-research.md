# Standalone execution replay: retain the incumbent

Neither fixed incumbent-rank preference nor dust-slot allocation passes every
predeclared return/worst-fold/drawdown gate. They remain research overlays;
no strategy change or real trading activation follows. The separately deployed
protective-halt repair is documented in `2026-09-12-protective-halt.md`.

## Execution contract and provenance

The harness runs the actual paper Engine, order builder, decimal account,
fees, daily order quota, $25 allocation ceiling,40% cash reserve,72-hour hold
and cooldown,10% individual/account drawdown protection and3% daily loss limit.
A deterministic fake clock replays5,664 hours from2026-01-14T01Z through
2026-09-07T00Z, with daily decisions at01UTC. The frozen model archive uses
Poloniex public candles, not another exchange's candles. Causal expanding
refits and EMA0.35 are retained. Eight pairs are BNB,ETC,ETH,PEPE,SUI,TRX,XRP,ZEC.

Historical books are unavailable. The replay explicitly uses hourly-open
bid/ask proxies at5bps half-spread and1% of prior-hour turnover as fill capacity.
It retains a snapshot of current market contracts, rather than claiming
historical depth or point-in-time membership. The $1,000 account is a simulation
budget; no real funds moved. Server signal-recipe and server paper-ledger
returns are different accounting contracts and are not standalone bot PnL.

Research-only Go overlays replace the wall clock and public HTTP host; the
loopback server rejects order writes. Actual Save/Load accounting and order
rounding remain active. Complete-cell resumes moved temporary ledger writes
to RAM without replacing the persistence logic. Original stopped-run logs,
results, source overlays and resume receipts are retained, not discarded.

## Fixed +0.4 incumbent rank preference

| Surface | Baseline return/mean, worst, maximum DD | Candidate return/mean, worst, maximum DD |
| --- | --- | --- |
| Continuous30bps |-1.1050%,-1.1050%,2.2945%|-0.1277%,-0.1277%,2.1671%|
| Continuous60bps |-1.5150%,-1.5150%,2.4404%|-0.4652%,-0.4652%,2.2834%|
| 9×28days30bps |0.2421%,-1.8539%,2.0818%|0.3829%,-1.7277%,1.9557%|
| 5×56days30bps |0.1625%,-1.4374%,2.2945%|0.8221%,-1.4602%,2.1671%|
| 5×56days60bps |0.0489%,-1.7258%,2.4404%|0.7147%,-1.6883%,2.2834%|
| 3×84days30bps |0.2629%,-0.7686%,2.2945%|1.2925%,-0.0047%,2.1671%|
| 3×84days60bps |0.0872%,-1.0811%,2.4404%|1.1315%,-0.2408%,2.2834%|

The continuous and28-day tests pass at both costs. The subsequent56-day
ordinary-cost worst fold worsens by0.02273 percentage points. That small,
real failure rejects promotion under the locked rule; it is not rounded away.
All40 initial and32 extended rows are complete. No threshold search follows.

## Dust allocation

The baseline finishes with tiny ETH and SUI remnants occupying two full slots;
its last fill isJune6, followed by no new fill throughSeptember7. A separate
candidate keeps every residual unit but counts a holding toward active slots
only when its rounded quantity/notional can meet current minimum order rules.
Selected dust may be rebuilt only to the existing $25 allocation ceiling,
subtracting marked residual value from new spending. No combination with the
rank preference was tested. A regression verifies retained units and allocation.

| Surface | Baseline return/mean, maximum DD | Dust candidate return/mean, maximum DD |
| --- | --- | --- |
| Continuous30bps |-1.1050%,2.2945%|1.8877%,2.2945%|
| Continuous60bps |-1.5150%,2.4404%|1.0442%,2.4404%|
| 9×28days30bps |0.2421%,2.0818%|0.2247%,2.0818%|
| 9×28days60bps |0.1585%,2.2276%|0.1188%,2.2276%|

Continuous fills rise63 to130, but fold mean falls at both costs. Worst-fold
return and maximumDD are unchanged. All40 rows complete; the failed first
screen stops progression to56/84-day studies. No dust is deleted and no budget
is increased in production.

## Reproduction

`research/ledger_20260912/` contains the exporter-overlay preparation,
actual-Engine replay test, guarded resume and complete-result summarizer.
Frozen inputs, source snapshots, logs, ledgers and comparison arrays live in
`data/frontier_20260912/ledger`, `ledger_extended` and `ledger_dust`.
Fixture SHA256:
`54b9544e9fd40a5cec398b1ca8e82d437c37d6be12cb4b2df3e69a213dfca074`.
Each comparison checks all required cells and records input/result hashes.
These are already-examined-history screens with proxy execution, not fresh
holdouts or estimates of live performance.
