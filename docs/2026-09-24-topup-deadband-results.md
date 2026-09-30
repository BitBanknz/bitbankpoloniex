# Corrected Poloniex replay: promising deadband, incomplete qualification

The fixed 25% slot-target deadband passes **7 of 9** registered comparison
groups, including every 28-day and 56-day reset comparison. It does not qualify
under the complete screen: continuous return falls slightly at 40-bps fees,
and continuous drawdown increases slightly at 40 and 60 bps. No live binary,
configuration, model or order was changed by this study.

## A material correction to the prior benchmark

The retained September 24 deployment replay used a **72-hour cooldown** through
`DefaultConfig`, while the remote live service explicitly uses **120 hours**.
Its generated test never overrode that default. Source and fixture hashes still
match the retained inputs, so this is a verified discrepancy in the original
experiment, not an inference from later source edits. The earlier report's
description of an exact tested live profile is unsupported.

The new benchmark explicitly uses 120 hours and 60 minute-spaced cycles during
the 01:00–02:00 UTC entry hour. Other hours still have one protective observation
and every intrahour cycle shares the same synthetic hourly book. This corrects
entry cadence; it is not full minute-market or live-execution parity.

Before any corrected candidate account, all four old continuous 72-hour,
12-cycle ledgers at 30/40-bps fees reproduced **byte for byte**. The independent
Decimal reference also reconstructed these original accounts. The original
benchmark, its results and the original deployment report remain preserved.

## Fixed comparison

The complete new matrix has **135 accounts**: legacy sizing, the incumbent
top-up policy and the candidate; fees of 30/40/60 bps per side; continuous,
28-day and 56-day resets. Reset geometries include the original 12-day tail
(eight full 28-day or four full 56-day windows). Results are arithmetic means
within each geometry, not annualized returns or independent observations.

Every account starts flat with 495 USDT. Order cap is 49, three slots, 40% cash
reserve and 12 orders/day. Incumbent and candidate retain the 25%/8% latched
halts. The sole candidate change is the minimum gap for topping up a held
rotation position: max(existing 25% of order cap, 25% of slot target), which
raises the threshold from **12.25 to 24.75 USDT** at this reset size. The initially
considered 10% slot threshold would have been inert and was discarded before
implementation or market testing. No threshold sweep followed the results.

| Geometry | Fee/side | Incumbent return | Candidate return | Incumbent max DD | Candidate max DD | Strict screen |
|---|---:|---:|---:|---:|---:|---|
| Continuous | 30 bps | 8.8520% | 18.8118% | 12.9798% | 11.9766% | Pass |
| Continuous | 40 bps | 18.3502% | 18.2041% | 13.3214% | 13.4286% | Fail |
| Continuous | 60 bps | 13.8338% | 16.0280% | 13.7985% | 13.9599% | Fail |
| 28-day mean | 30 bps | 2.2516% | 2.3166% | 12.3826% | 11.9766% | Pass |
| 28-day mean | 40 bps | 1.7462% | 1.8144% | 12.6542% | 12.2309% | Pass |
| 28-day mean | 60 bps | 1.5376% | 1.6123% | 13.1936% | 12.7343% | Pass |
| 56-day mean | 30 bps | 3.9021% | 3.9783% | 12.6470% | 12.6470% | Pass |
| 56-day mean | 40 bps | 2.8886% | 2.9685% | 16.0483% | 16.0483% | Pass |
| 56-day mean | 60 bps | 2.8172% | 2.9051% | 13.3582% | 13.3582% | Pass |

The legacy continuous returns are 5.9215%, 4.9272% and 2.9387% at the same fee
levels, with lower drawdowns of 7.0733%, 7.5096% and 8.9641%. Top-up policies
change exposure as well as trading frequency; these are not new forecast models.

All candidate hourly drawdowns remain within the owner's 35%/40% risk budget
on these simulated paths. The additional relative-DD checks belong to this
study's strict comparison; they are not replacement fleet limits. Even without
those relative-DD checks, the 40-bps continuous return regression remains.
Reused history and execution gaps independently prevent deployment qualification.

## What the result suggests

At 30 bps, top-ups fall from 62 to 52 and total fills from 212 to 199. Fee savings
are only **0.7176 USDT**, versus a **49.3011-USDT** final-equity improvement.
Fees alone therefore do not explain the gain. At 40 bps, the candidate makes
fewer top-ups but pays more total fees. Small changes to costs and sizing change
the subsequent position path; a lower-fee run need not have the higher final
return when orders depend on cash and holdings.

The consistently improved reset windows justify keeping the fixed candidate
for future confirmation, without selecting a favorable cost or dropping the
continuous comparison. Reset folds alone would miss the two strict failures.
The current result supplies no untouched holdout or live profit estimate.

## Verification and limits

- Full native suite and race suite: **108 checks each**, zero skips; vet passed.
- Four complete original ledgers matched byte for byte before the new matrix.
- Independent Decimal audit: **135 accounts, 152,928 hourly marks, 5,076 fills,
  180,243 comparisons**. Cash, quantities, fees and marks match exactly; reported
  return and drawdown also match at their emitted decimal precision.
- The audit checks lot/tick rules, synthetic depth and order caps, daily order
  counts, cash reserve, entry eligibility, top-up gaps, cooldown deadlines,
  holdings/peaks, pending state and all **128 dust removals**. Recorded intents
  are inputs; completeness of every possible strategy intent is not proved.
- Ten independent-reference tests pass, including corrupted fees, prices,
  clocks, marks and holdings, omitted cost groups, and tail/cost regressions.

The first independent reference incorrectly assumed every protective order ID
used the current hour. At 00:00, an available forecast can supply the upcoming
01:00 execution-hour ID even before entries are ready. The original failure
and source remain retained; reference v2 reconstructs this existing convention.
No native policy or result was changed to make that audit pass.

Execution remains an hourly-open proxy with a 5-bps half-spread, tick rounding,
synthetic depth and current contracts. The fee ladder is additional to those
book-price effects. Quotes are reused within the entry hour, protective checks
outside that hour are hourly, and private fill arrival is not established.
The eight-symbol forecast fixture is reused history. The actual live ledger
retains an imported **489.1312417736-USDT** budget and inherited positions;
flat 495-USDT resets are not that live account. Installed-binary/source parity
and future outcomes remain separate requirements.

Read-only remote checks found the live service active with zero restarts,
no pending order or halt, and identical mapped/installed executable SHA256
`eb9a2d1008c9b7c30d7b011e852e994e75fce44f0a255d65f4765b18f14740ec`.

Evidence root:
`/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/`.

- [Protocol](2026-09-24-topup-deadband-prereg.md)
- [Complete summary](/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/summary.json)
- [Independent verification](/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/verification.json)
- [Original-ledger parity](/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/parity.json)
- [Reviewable isolated patch](/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/native.patch)
- [Remote operating snapshot](/vfast/data/trading_research_20260924/poloniex_topup_deadband_v1/live_health.json)
