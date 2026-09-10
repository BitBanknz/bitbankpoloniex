# BitBank Poloniex Bot

Paper-trading Go bot that follows [BitBank](https://bitbank.nz) rotation ranks on
Poloniex Spot, with a read-only account check, an opt-in live executor, and a
native Go boosted-tree fallback. **Paper mode is the default; nothing here has
submitted a live order during development.**

## Quick start

Requires Go 1.25. Run from this directory.

```sh
make build
./bin/bitbankpoloniex --command coverage   # which markets are liquid + covered by BitBank?
./bin/bitbankpoloniex --command init       # create the paper ledger (refuses to overwrite)
./bin/bitbankpoloniex --command run        # trade paper, one cycle per minute
```

No API keys needed until you touch private endpoints. Copy `.env.example` to
`.env` and fill it in when you do — `.env` is git-ignored and always wins as a
pair over inherited environment credentials. It is read, never executed.

| Command | What it does | Needs keys? |
|---|---|---|
| `status` | Print the paper ledger | no |
| `coverage` | Liquid markets vs BitBank-covered markets | no |
| `init` / `once` / `run` | Create ledger / one cycle / loop until stopped | no |
| `train` | Train fallback models for the liquid universe | no |
| `archive` | Download historical candles to `data/archive-*` | no |
| `doctor` | Read-only account check (balances, margin, orders) | yes, read |
| `account-plan` | Read-only funding plan: convert or margin | yes, read |
| `init-account` | Paper ledger mirroring your priced spot inventory | yes, read |
| `margin-paper` / `margin-paper-close` | Simulated collateral/debt ledger step / close | yes, read |
| `research-signals` | Cached daily exploratory signals (paper only) | no |

Full flags: `./bin/bitbankpoloniex --help`. State lives in `data/paper/`
(`state.json` ledger, `models.json`, `validation.json`); `run` and `train` take
separate locks so the daily refresh can run alongside the trader.

## How it picks trades

Each hour the bot fetches BitBank rotation ranks, waits for the declared
execution hour, and holds up to **3** (walk-forward validated, see bitbankgo docs/poloniex-deployed-walkforward-20260911.md) of the top-ranked liquid USDT markets
(min 100,000 USDT 24h volume, max 30bps spread, depth-capped orders).
Positions rotate on a 72-hour minimum hold with a 10% trailing stop; when
neither BitBank nor a validated fallback model is usable, entries pause but
tracked positions still get stop checks.

Simulated ledger (1000 USDT cash, 25 USDT max per order, 40% cash reserve,
12 orders/day, 30bps paper fee/side, 10% peak / 3% daily loss halt):
paper fills are modeled at visible quotes, not proof of real fills or profit.

## Fallback models

The fallback is 32 native Go gradient-boosted stumps (not XGBoost/LightGBM),
promoted only through expanding-window folds with round-trip costs, drawdown
and baseline-MSE gates. Models expire after 7 days. Latest full run: 75 liquid
markets, 56 trainable, **zero passed** — so no fallback is active. Details and
the exploratory trend20/BTC-regime study: [`research/REPORT.md`](research/REPORT.md).

## Live orders (operator launch only)

Tested against a mock exchange, not the real account. Live needs a separate
directory, explicit budget flags, **and `--enable-live-orders` on every
invocation** — no env var can silently enable it:

```sh
./bin/bitbankpoloniex --command init --mode live --state data/live \
  --budget YOUR_USDT_BUDGET --max-order YOUR_ORDER_LIMIT --enable-live-orders
./bin/bitbankpoloniex --command run --mode live --state data/live \
  --budget YOUR_USDT_BUDGET --max-order YOUR_ORDER_LIMIT --enable-live-orders
```

Safety properties: LIMIT IOC SPOT orders with `allowBorrow=false`, borrowing
and existing margin debt refused, per-order idempotency keys with persisted
pending intents (ambiguous writes are never retried; the next cycle reconciles
by client ID). The drawdown halt also blocks exits — it is an operator-review
gate, not a guaranteed stop. Never delete state or clear pending intents to
get past an error; compare the exchange order/trade history with the ledger
first. There is no live systemd unit.

## Running it

```sh
systemctl --user status bitbankpoloniex-paper.service
journalctl --user -u bitbankpoloniex-paper.service -n 30
touch data/paper/STOP   # stop processing (does not cancel exchange orders)
```

Five failed cycles in a row open the circuit and exit; the unit restarts after
5 minutes. `STOP` and halts survive restarts — review before removing. Back up
`data/` (private, git-ignored) securely. See [`deploy/`](deploy/).

## Research (offline Python)

```sh
python research/evaluate_v1.py --archive data/archive-daily --out data/new-v1
python research/matrix.py --archive data/archive-daily --out data/new-matrix.json
```

Pinned in `research/requirements.txt`. Python never touches keys, orders, or
the live ledgers. Tests: `make test` (Go, race), `python research/test_evaluate.py`.

## API references

[Auth](https://api-docs.poloniex.com/spot/api/) ·
[Accounts](https://api-docs.poloniex.com/spot/api/private/account) ·
[Margin](https://api-docs.poloniex.com/spot/api/private/margin) ·
[Markets](https://api-docs.poloniex.com/spot/api/public/reference-data) ·
[Market data](https://api-docs.poloniex.com/spot/api/public/market-data) ·
[Orders](https://api-docs.poloniex.com/spot/api/private/order) ·
[Trades](https://api-docs.poloniex.com/spot/api/private/trade)
