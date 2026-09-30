# Prevent a stopped holding from being topped back up

The complete native synthetic reproduction sells part of a stopped holding,
then buys it back in the entry pass. The existing per-hour stop decision ID
prevents another reduction in the following minute. This is reproduced in both
the incumbent rotation and quote-aware candidate, not observed in the live ledger.

Apply one correction: skip a symbol in the entry pass when its observed holding
is below its protective stop in the current cycle. This also prevents increasing
that holding when its sell is blocked by price/size checks or a processed ID.
Keep the existing sell cap, decision IDs, daily order cap, reserve, cooldown,
stop threshold, forecast and sizing rules. Do not add repeated same-hour sells
or a new latched-exit policy in this change.

Require full native/race/vet checks, complete-cycle regression tests covering
the capped stop, the following minute, blocked stops, ordinary entries and
protective exits, and exact unchanged controls wherever the new condition does
not apply. For historical compatibility use the existing corrected 120-hour
cooldown / 60 entry-hour-cycle matrix: incumbent top-ups, all three 30/40/60-bps
fees, continuous / 28-day / 56-day accounts, including all retained tails.
Compare all 45 complete ledgers to the previous native results. Do not omit a
changed account or call a reused historical interval fresh validation.

This restores the intended direction of a protective reduction. It is not a
claim of newly discovered alpha or a guaranteed future PnL gain. A live change
also requires exact current source/configuration identity and pending-order
checks, a tested build, preserved state, and a verified rollback artifact.
The separate quote-aware future study remains frozen until an explicitly
recorded continuation is qualified; do not silently edit its running binary.
