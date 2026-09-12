# Drawdown halt must retain protective stops

The account drawdown/daily-loss halt returned before trailing-stop checks, and
every subsequent cycle returned immediately on the persisted halt. A breached
account could therefore keep losing on existing holdings without those checks.

The repair keeps that specific automatic risk halt latched, disables signal
and entry work, and continues marking holdings and checking protective stops.
Manual STOP files and other ledger-error halts retain their existing behavior.
The trade entry path also rejects BUY requests while any halt is set. A held
market remains available for stop checks even if no market passes the entry
liquidity screen. Order limits, fee assumptions and the three-slot strategy
remain unchanged.

Regression tests fail against the archived old engine and pass after repair,
covering newly triggered and persisted risk halts plus direct entry rejection.
Full `go test -race ./...`, `go vet ./...` and the build pass. Evidence and
source/binary/state rollback copies: `data/frontier_20260912`.

Deployed at 2026-09-12 09:19:50 UTC to the two existing paper services:
`bitbankpoloniex-paper` and `bitbankpoloniex-account-paper`. Installed SHA-256:
`859cdbedeabae362bbc58b61d97177ac5c373705ddff94c58a306816a85d698a`.
Both are active with zero restarts; both completed their first cycle. The
ordinary paper service reports entries paused outside the valid forecast
window, and the experimental account-paper service reports cycle complete.
No real-order trading was enabled.

Separately, the server-recipe expanding/recent-90-day 50/50 model ensemble was
rejected. Continuous return fell from 18.3951% to 5.9337%, with DD rising from
9.3250% to 9.4214%; at doubled fees, return fell from 15.8910% to 3.3720%.
Recipe artifacts live in sibling bitbankgo `content/frontier_20260912/temporal90`.
The recipe's allocation is not the standalone engine's $25 order ledger, so
recipe returns are not claimed as standalone paper/live PnL.

The11:15UTC release supersedes this binary with stop-priority and partial-book
isolation repairs while retaining this halt behavior. See
[protective exit release](2026-09-12-protective-exit-priority.md) for the current
running hash, exact baseline parity and preserved paper accounts.
