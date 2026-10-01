# Exit-rule sweep: pre-registration

Untested hardcoded exit knobs in `internal/bot/engine.go`: trailing stop 0.90 of peak bid
(`stopFraction`) and 72h minimum hold before a non-target holding is rotated out. One-at-a-time
variants against the live profile (slots 3 / 120h / reserve 0.4 / halts 25-8), frozen fixture,
fees 30/40 bps, continuous / 28d / 56d, harness `research/sweep20260930/prepare_exit.py`:
stop 0.85, 0.93, 0.95; minimum hold 24h, 48h, 120h (six runs; baseline `s3_c120_r0.4_h25_8`).
Promotion rule identical to `2026-09-30-config-sweep-prereg.md` (all six mean cells beaten, worst
fold within 2 pts, positive folds >= baseline, DD <= 25%, >= 6/9 paired 28d wins at 40 bps). A
combination of two passing singles would be registered separately before running.
A BTC 50d/200d regime gate was built and dropped before any run: BTC was below one of the two
averages on 222 of 244 days of the fixture window, so the gate reduces to holding cash and carries
no information about forward regimes. Live change, if any, needs a build-time engine patch as for
the stop guard, so a winner would also need its own qualification package.
