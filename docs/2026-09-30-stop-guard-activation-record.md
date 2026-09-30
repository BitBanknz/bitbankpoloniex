# Stop/top-up guard activated 2026-09-30

Candidate `4cc91224…` (protocol: `2026-09-29-stop-guard-activation-protocol.md`) is live on
`bitbankpoloniex-live.service` as of 10:12Z; unit and arguments unchanged (unit sha `9f3af984…`),
old binary `eb9a2d10…` kept at `data/release-stop-guard-20260930_v3/installed_before`.
Post-start: 2 completed cycles, 0 restarts, doctor passed, no pending intent, budget 489.1312417736,
fills 41 preserved, holdings BNB/ETH/TRX unchanged, no manual orders.

Earlier attempts (2026-09-28, and v2 today) installed the candidate, passed every state/doctor check,
then rolled back cleanly (verified, no fills lost) because of a verifier bug, not a candidate fault:
the journal check matched `m=='cycle complete'`/`startswith('cycle paused:')`, but log lines carry a
timestamp prefix, so it could never match. `deploy_remote_v3.py` matches on the suffix/substring;
everything else is identical to `deploy_remote.py`.

Operational note: "cycle paused: BitBank unavailable and no accepted fallback; entries paused" outside
the 01:00-01:59Z execution hour is the normal state (the forecast is only valid in that hour), not an
outage. Live entered BNB at 01:15-01:16Z today. First true test of the guard on entries is the
2026-10-01 01:00Z window; roll back per the protocol if a completed cycle blocks or a fill is lost.
