# Quote-aware entry selection: fixed research treatment

The preceding four 01:56–01:59 UTC observations are discovery data. They show
that two of three desired new entries can fail actual quote constraints. This
experiment changes selection of unheld targets and keeps sizing unchanged.

Control: current native rotation, top-ups enabled, 495-USDT flat paper budget,
49-USDT order cap, three slots, 40% cash reserve, twelve orders per UTC day,
120-hour post-sale cooldown, existing 72-hour rotation hold and 10% trailing
stop. Peak/day halt bands remain 25%/8%. Run fees of 30, 40 and 60 bps per side.

Treatment: rank the same eligible markets with the existing deterministic tie
break. Walk the ranking until three names have qualified. Held names qualify
without applying a new-buy quote test. Unheld names require a current book and
successful native `BuildOrder` for a 49-USDT allowance using the existing
spread, freshness, depth, tick, lot and minimum/maximum size rules. Quotes are
checked again by the ordinary trade path; preselection does not authorize a
fill, bypass cooldown or reserve cash. Do not combine this treatment with the
25% slot-target deadband. Neither scores nor training/augmentation change.

The private research flag defaults off and is restricted to paper rotation.
The production worktree implementation, binary and service are unchanged.

Before any future trial: require default-off native suite compatibility,
adversarial eligibility/retention checks and complete native-cycle checks for
new entries, held-target retention, cooldown/order/cash limits, expired ranks,
incomplete valuation and protective exits. Reuse all five recorded discovery
captures for a fixed paired execution diagnostic, preserving every cost arm.
Require exact default-off control ledgers against the unmodified engine.
This short replay demonstrates behavior, not independent PnL evidence.

Any prospective account experiment must freeze source/configuration before its
future observations, use actual available receipts without filling past gaps,
preserve every account path, and explicitly distinguish paper execution from
proven exchange fills. A seven-day diagnostic cannot establish 28-day risk.
Promotion still requires higher PnL under paired realistic costs, sufficient
future observations, source/live parity and the owner's 35% rolling-28-day /
40% full-window drawdown limits. No tighter fleet risk limit is introduced.
