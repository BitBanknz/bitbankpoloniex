# BitBank Poloniex

Standalone Go bot consuming BitBank's Poloniex rotation ranks, with paper execution,
read-only account diagnostics, a separately enabled live executor, and an independent
native Go boosted-tree fallback. The default mode is **paper**. No live orders have
been submitted during development.

## Quick start

```sh
make test
make build
./bin/bitbankpoloniex --command doctor
./bin/bitbankpoloniex --command coverage
./bin/bitbankpoloniex --command init       # once; refuses existing state
./bin/bitbankpoloniex --command train --markets 0
./bin/bitbankpoloniex --command run
```

Run from this project directory. Existing `.env` is preserved and excluded from Git;
its `POLONIEX_API_KEY` and `POLONIEX_SECRET_KEY` are read together, taking precedence
over inherited credentials. No dotenv content is executed as shell. Public data,
training, and paper trading do not need private account access. `doctor` only reads
balances, margin, borrowed amounts, and open orders. A successful diagnostic does
not establish write permission.

`data/paper/state.json` is the durable paper ledger. `--command status` prints it.
`data/paper/validation.json` contains all attempted-market validation results;
`models.json` retains rejected as well as accepted models. Training is independent
of the state lock so refresh can run alongside the trader. Files are atomically
replaced and fsynced; separate process locks protect trading and training.

## What the strategy does

The primary URL is `https://bitbank.nz/api/trading-bot/rotation-signals`. The consumer
checks the venue, rank schema, individual scores, issuance and execution clocks.
It waits until the declared execution hour and accepts the forecast only during
that hour. Scores are cross-asset ranks. A named adapter
selects up to four available ranked USDT markets.

Market discovery uses exchange metadata and 24-hour quote volume, with a default
100,000 USDT volume floor. Paused/post-only markets, stale/invalid books, wide
spreads, invalid exchange precision and sizes are excluded. Dynamic market
availability does not mean BitBank predicts every market: the primary currently
covers eight pairs. `coverage` reports the actual intersection.

If the primary request fails or its data expires, only fresh, accepted fallback
models may supply signals. Missing predictions do not imply sell signals. When
neither source is usable, new entries pause; tracked positions still receive
stop checks when market data is available. Outages can prevent exits too.

Defaults, denominated in the explicitly assigned bot budget:

- 1,000 USDT **simulated** starting cash; 25 USDT maximum notional per order.
- At most four tracked positions, one entry per position, 40% cash reserve.
- 72-hour minimum hold for rotation; 10% trailing bid trigger; 72-hour cooldown
  after a position is completely exited. No shorting or borrowing.
- 12 order attempts per UTC day, at most 10% of displayed depth within 10 bps of the best quote, 30-bps
  maximum spread, and a conservative 30-bps paper fee per side.
- A 10% peak-equity loss or 3% UTC-day loss halts the ledger for operator review.
  This halts all new submissions, including exits; it is not a guaranteed stop loss.
- Per-order/day limits also apply to exits. A partial exit may span multiple cycles;
  the bot does not promise immediate liquidation during a fast market.

Paper fills are modeled at the visible bid/ask subject to the depth cap; they are
not proof of exchange fills, latency, profitability, or future executable volume.
By default external holdings are not adopted. The explicit `init-account` command
allocates priced, tradable spot inventory to its own ledger; funding conversions
then sell only that adopted inventory, within the order/day limits. Unpriced,
locked and sub-minimum dust balances are reported and excluded.

## Independent fallback validation

The fallback is a native Go gradient-boosted regressor with 32 depth-one trees,
fixed 0.05 learning rate and six past-only features. It is **not** an XGBoost or
LightGBM library/weight loader. Production BitBank's separate rank model is LightGBM.

Training requests 3,000 contiguous completed hourly candles per market. Four
expanding chronological folds purge training labels before each test boundary.
Test labels stay inside their fold, and 24-hour returns use the next candle open
as entry. Evaluation samples do not overlap. The model is not tuned against the
fold results. The acceptance gate requires:

- At least three profitable folds after 60-bps modeled round-trip cost.
- At least 12 held-out trades in total and positive combined fold returns.
- Every fold below 15% drawdown and prediction MSE below a zero-return baseline.

Models expire seven days after their last training observation; a complete JSON
checksum detects accidental modification. This is not a cryptographic trust
signature. Accepted flags alone cannot bypass recomputed metric gates. No model
is activated merely because training finished.

These are signal-level research checks, not independent proof that the full
72-hour rotation/stop portfolio is profitable. There is no separate final holdout
or live-profit evidence, and historical market coverage has survivorship bias.
See `data/paper/validation.json` for actual results rather than assuming acceptance.
The full September 10 run evaluated all 75 liquid markets: 56 had enough history
to train, 19 were rejected for insufficient history, and **zero models passed**.
Consequently no fallback is currently eligible to activate. The daily refresh
reevaluates the full current liquid universe without weakening the gates.

## Live executor (operator launch only)

The implemented live path has been tested with a mock exchange. It was not started
against the real account. The verified account has ETH and effectively no USDT. Collateral value and cash
remain distinct; account adoption makes that ETH available for planned conversions.
The `init-account` path now supports explicitly adopting existing ETH and other
priced spot holdings, and converting them through reconciled fills. A separate
margin planner and paper margin ledger support collateral-backed borrowing research.
The live executor still refuses borrowing and existing margin debt; live margin
execution is not implemented by these paper commands.

Live use requires a separate state directory, an explicit budget, and an explicit
CLI switch on **every** invocation. There is no environment variable that silently
turns paper mode into live mode. Example command structure (replace the budget and
order amount after your review, do not copy placeholders literally):

```sh
./bin/bitbankpoloniex --command init --mode live --state data/live \
  --budget YOUR_USDT_BUDGET --max-order YOUR_ORDER_LIMIT --enable-live-orders
./bin/bitbankpoloniex --command run --mode live --state data/live \
  --budget YOUR_USDT_BUDGET --max-order YOUR_ORDER_LIMIT --enable-live-orders
```

Train separately with `--state data/live` if using fallback models for that ledger.
The paper model file is not silently reused. There is no live systemd service.

The executor uses modern HMAC-SHA256 signing, decimal order quantities, LIMIT IOC
orders and `allowBorrow=false`. It rejects used margin, borrowed balances, negative
balances, and existing open orders. Only bot-tracked inventory can be sold. Existing
ETH can be explicitly adopted with `init-account`; ordinary `init` uses cash only. Unrelated manual trading in the same account can
make reconciliation fail; use an isolated allocation/account where possible.

Before each submission, a deterministic client order ID and pending intent are
persisted. Ambiguous writes are **never retried**. The next cycle queries by client
ID and reconciles terminal order totals with individual exchange trades and fees.
Base/quote fees and partial fills are accounted for; a third-currency fee stops
reconciliation for review. Missing orders, incomplete trade records, nonterminal
orders and identity mismatches block further orders. A 404 is not permission to
resubmit. The initial safe behavior for unresolved orders is to stop and investigate.

Do not delete state, clear pending intents, reset drawdown flags, or create a fresh
live directory to get past an error without comparing the exchange order/trade
history and bot ledger. State is the duplicate-submission and inventory boundary.

## Operation and services

This workspace has a user service `bitbankpoloniex-paper.service` and a daily
`bitbankpoloniex-train.timer`. The templates in `deploy/` use `%h/bitbankpoloniex`;
substitute the actual project path when installing elsewhere. Only paper mode is
installed. User-service survival after logout/reboot depends on user-manager
configuration; this workspace has `Linger=yes`. Check
`loginctl show-user "$USER" -p Linger` on another deployment host.

```sh
systemctl --user status bitbankpoloniex-paper.service
journalctl --user -u bitbankpoloniex-paper.service -n 30
systemctl --user list-timers bitbankpoloniex-train.timer
# Stop processing; does not cancel any preexisting exchange orders:
touch data/paper/STOP
systemctl --user stop bitbankpoloniex-paper.service
```

Five consecutive failed cycles open the circuit and exit. The supplied service
waits five minutes before restarting and limits repeated starts. The persistent
STOP file and ledger halt survive restarts. Review errors before restarting;
removing STOP is an operator action. Back up the private `data/` directory securely.

## API references

- [Authentication](https://api-docs.poloniex.com/spot/api/)
- [Accounts](https://api-docs.poloniex.com/spot/api/private/account)
- [Margin](https://api-docs.poloniex.com/spot/api/private/margin)
- [Markets and precision](https://api-docs.poloniex.com/spot/api/public/reference-data)
- [Market data](https://api-docs.poloniex.com/spot/api/public/market-data)
- [Orders](https://api-docs.poloniex.com/spot/api/private/order)
- [Trade and fee reconciliation](https://api-docs.poloniex.com/spot/api/private/trade)


## Existing assets, margin and expanded research (September 10 update)

```sh
# All three account calls below make only read requests to the exchange:
./bin/bitbankpoloniex --command account-plan --funding convert
./bin/bitbankpoloniex --command account-plan --funding margin --symbol ETH_USDT
./bin/bitbankpoloniex --command init-account --state data/new-account-paper
# Uses the imported inventory; does not pretend ETH is already USDT:
./bin/bitbankpoloniex --command run --state data/new-account-paper --experimental-fallback

# Isolated simulated collateral/debt ledger. Both commands are paper only:
./bin/bitbankpoloniex --command margin-paper --state data/new-margin-paper --symbol ETH_USDT
./bin/bitbankpoloniex --command margin-paper-close --state data/new-margin-paper --symbol ETH_USDT
```

For live **spot** account adoption, `init-account` also requires the same explicit
live mode, budget, separate directory and live switch described above. No live
account ledger was created here. Imported holdings are limited to the requested
budget, retain their actual units, and are valued at executable bids. The ledger's
assigned starting value is recorded in state. Conversion trades remain capped;
funding a cash reserve can take several cycles or days. Unpriced assets cannot
silently fund orders. Legacy margin and spot are presented through the modern
SPOT account API; separate futures wallets are not supported by this executor.

Margin plans query current collateral haircuts, free margin, maximum buy size,
and borrowing rates. The planned order is bounded by 25% of reported free margin
and free priced equity. The simulated margin ledger limits gross leverage to 1.25,
retains original collateral, accrues USDT interest, and repays debt from closing
proceeds. Losses/fees can leave residual debt after an overlay closes; no fictitious
repayment or automatic sale of collateral is used to hide it. Current fee/rate
snapshots are not historical borrowing evidence.

`--experimental-fallback` is a paper-only opt-in. It uses the exploratory
trend20/top3/BTC-regime candidate documented in [the research report](research/REPORT.md).
Its daily signals are cached until the next UTC day. The flag is rejected in live
mode and does not override native boosted-model acceptance. Ordinary paper/live
runs retain the existing fail-closed fallback behavior. Primary BitBank ranks still
take precedence. The runtime uses operational sizing, gradual funding conversions,
stops and hold limits; it is not an exact replay of the weekly-weight backtest.
No published historical return is attributed to this new forward paper account.

```sh
# Resumable archives, all history returned by the current API, frozen universe:
./bin/bitbankpoloniex --command archive --markets 0 --archive data/archive-daily
./bin/bitbankpoloniex --command archive --markets 0 --archive data/archive-hourly --candle-interval HOUR_1
# Python is confined to offline research; the bot, collector and paper ledgers are Go.
python research/evaluate_v1.py --archive data/archive-daily --out data/new-v1
python research/evaluate.py --archive data/archive-daily --out data/new-v2
python research/matrix.py --archive data/archive-daily --out data/new-matrix.json
python research/robustness.py --archive data/archive-daily --out data/new-robustness.json
```

Use the pinned packages in `research/requirements.txt`. Each research output directory
must be new. Raw hourly/daily pages, CSV hashes, archive manifests and quarantined
malformed rows are retained. Missing observations are never forward-filled for
trades. Current-listed market selection still has survivorship bias; these archives
cannot recover delisted assets, historical order books, or borrowing availability
that the API does not supply. Python's final-year v2/matrix results explicitly mark
that year as reused after the first study. Tests cover both temporal accounting and
failure behavior; they do not validate profitability.
