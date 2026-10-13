"""Evaluate the hourly A/B paper arms (pre-registered rules, docs/2026-10-14-hourly-ridge-paper-ab-prereg.md).
For each arm, from its state.json: hourly marked equity (8p) and ex-ZEC equity = equity - (ZEC qty x ZEC hourly close)
- cumulative ZEC cash flows (sell +amount-fee, buy -amount-fee), i.e. all ZEC P&L removed. Prints return, max marked DD and
weekly windows led vs control, from the first hour at which every arm has an equity mark.
usage (on the host): python3 hab_eval.py data/paper-hab-control data/paper-hab-hema data/paper-hab-ridge"""
import json, sys, urllib.request
from datetime import datetime, timezone


def ts(s): return int(datetime.fromisoformat(s[:19]).replace(tzinfo=timezone.utc).timestamp())


def zec_closes(h0, h1):
    out = {}
    for a in range(h0, h1 + 1, 500):
        b = min(a + 500, h1 + 1)
        url = f'https://api.poloniex.com/markets/ZEC_USDT/candles?interval=HOUR_1&startTime={a*3600000}&endTime={b*3600000-1}&limit=500'
        for r in json.load(urllib.request.urlopen(url, timeout=30)): out[int(r[12]) // 3600000] = float(r[3])
    return out


def curves(path, zec, hours):
    s = json.load(open(f'{path}/state.json')); budget = float(s['Budget'])
    eq = {ts(p['At']) // 3600: float(p['Value']) for p in (s.get('Equity') or [])}
    fills = sorted(((ts(f['At']), f) for f in (s.get('Fills') or []) if f['Order']['symbol'] == 'ZEC_USDT'), key=lambda x: x[0])
    x = {}
    for h in hours:
        v = eq[h]
        q = c = 0.
        for t, f in fills:
            if t // 3600 >= h: break  # equity mark at hour h precedes fills inside hour h
            a, fee, qty = float(f['Amount']), float(f['Fee']), float(f['Quantity'])
            if f['Order']['side'] == 'BUY': q += qty; c -= a + fee
            else: q -= qty; c += a - fee
        px = zec.get(h - 1) or zec.get(h)
        x[h] = v - (q * px if q else 0.) - c
    return budget, eq, x


def stats(budget, eq, hours):
    v = [budget] + [eq[h] for h in hours]; peak, dd = v[0], 0.
    for e in v: peak = max(peak, e); dd = max(dd, 1 - e / peak)
    return v[-1] / budget - 1, dd


def main():
    arms = sys.argv[1:]; data = {}
    allh = None
    for a in arms:
        s = json.load(open(f'{a}/state.json')); hs = {ts(p['At']) // 3600 for p in (s.get('Equity') or [])}; allh = hs if allh is None else allh & hs
    hours = sorted(allh); zec = zec_closes(hours[0] - 2, hours[-1]) if hours else {}
    for a in arms: data[a] = curves(a, zec, hours)
    print(f'common hours {len(hours)} ({hours[0] if hours else "-"}..{hours[-1] if hours else "-"})')
    for name, k in (('8p', 1), ('exZEC', 2)):
        res = {a: stats(data[a][0], data[a][k], hours) for a in arms}
        weeks = [hours[i:i + 168] for i in range(0, len(hours) - 167, 168)]
        for a in arms:
            lead = sum(1 for w in weeks if (data[a][k][w[-1]] - data[a][k][w[0]]) > (data[arms[0]][k][w[-1]] - data[arms[0]][k][w[0]])) if a != arms[0] else '-'
            print(f'{name:6s} {a:32s} return {100*res[a][0]:+7.2f}%  maxDD {100*res[a][1]:6.2f}%  weeks led vs {arms[0].split("/")[-1]}: {lead}/{len(weeks)}')


if __name__ == '__main__':
    main()
