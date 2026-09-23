# Slot top-up re-tested at measured live cost — deployed 24 September 2026

The 2026-09-18 replay rejected slot top-up because it lost the 60 bps/side
continuous cell; that rule assumed 30 bps real cost. Measured on all 18 live
fills (2026-09-11→09-19): fee 14 bps when paid in TRX (20 bps before), and fill
versus the Poloniex hourly open ~4 bps mean excluding one 2.4 USDT fallback sell
(476 bps); real cost ≈ 18–20 bps/side. The engine's fee floor is 30 bps, so the
same frozen replay (`research/topup20260924/`, identical to 20260918 except the
fee arms 30/40 bps = measured cost rounded up / doubled) was re-run:

| geometry | fee | legacy mean / worst / max DD / positive | top-up r0.4, halts 25/8 |
|---|---:|---|---|
| continuous | 30 | +7.60 / — / 9.0 | +13.14 / — / 15.5 |
| continuous | 40 | +6.48 / — / 9.2 | +7.25 / — / 15.8 |
| 28-day (9) | 30 | +1.12 / −7.3 / 8.2 / 7 | +2.74 / −12.7 / 14.3 / 7 |
| 28-day (9) | 40 | +0.98 / −7.6 / 8.4 / 7 | +2.05 / −13.1 / 14.6 / 6 |
| 56-day (5) | 30 | +2.13 / −5.2 / 9.0 / 3 | +5.99 / −8.4 / 15.5 / 3 |
| 56-day (5) | 40 | +1.90 / −5.6 / 9.2 / 3 | +4.85 / −10.7 / 15.8 / 3 |

Top-up wins every mean at both realistic costs; worst 28-day DD 14.6% is far
inside the 30–40% fleet budget. The only regression is one fewer positive
28-day fold at doubled real cost (6 vs 7 of 9). Deployed the exact tested
profile: `--slot-top-up --cash-reserve 0.4 --halt-peak-dd 0.25 --halt-daily-loss 0.08`
(unit `deploy/remote/bitbankpoloniex-live.service`, binary unchanged
`eb9a2d10…`), 2026-09-23T15:28Z. Rollback: remote
`data/release-topup-20260924/unit.before` → `/etc/systemd/system/`,
daemon-reload, restart. Judge by the live report after several 01:00Z windows.
