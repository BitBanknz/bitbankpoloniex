"""Binance spot hourly close/quote-volume panel aligned to the Poloniex panel grid, and the btc720 day gate.
KCB1 files from bitbankkucoin, extended from data-api.binance.vision; missing hours forward-fill close, zero volume.
usage: python3 -I binance_panel.py --kcb DIR --panel panel.npz --end-hour H --out DIR"""
import argparse, hashlib, json, time, urllib.request
from pathlib import Path
import numpy as np

SYMS = ['BNB', 'ETC', 'ETH', 'PEPE', 'SUI', 'TRX', 'XRP', 'ZEC', 'BTC']
API = 'https://data-api.binance.vision/api/v3/klines'


def kcb(path):
    b = path.read_bytes(); assert b[:4] == b'KCB1'
    a = np.frombuffer(b[4:], dtype=np.dtype([('ts', '<i8')]+[(k, '<f8') for k in ('o', 'h', 'l', 'c', 'v', 'q')]))
    return {int(r['ts'])//3600: (float(r['c']), float(r['q'])) for r in a}


def fetch(sym, first, end):
    rows = {}
    while first < end:
        url = f'{API}?symbol={sym}USDT&interval=1h&startTime={first*3600000}&endTime={end*3600000-1}&limit=1000'
        with urllib.request.urlopen(url, timeout=30) as r:
            batch = json.load(r)
        if not batch: break
        for k in batch:
            if int(k[6]) < time.time()*1000: rows[int(k[0])//3600000] = (float(k[4]), float(k[7]))
        first = int(batch[-1][0])//3600000+1; time.sleep(.2)
    return rows


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--kcb', type=Path, required=True); ap.add_argument('--panel', type=Path, required=True)
    ap.add_argument('--end-hour', type=int, required=True); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args()
    H = np.load(a.panel)['hours']; start = int(H[0])-720; grid = np.arange(start, a.end_hour)
    close = np.full((len(grid), len(SYMS)), np.nan); qv = np.zeros_like(close); filled = np.zeros(close.shape, bool); meta = {}
    for j, s in enumerate(SYMS):
        rows = kcb(a.kcb/f'{s}USDT.bin'); last = max(rows); n0 = len(rows)
        if last+1 < a.end_hour: rows.update(fetch(s, last+1, a.end_hour))
        meta[s] = dict(kcb_rows=n0, kcb_last_hour=last, fetched=len(rows)-n0)
        for i, h in enumerate(grid):
            if h in rows: close[i, j], qv[i, j] = rows[h]
            else: filled[i, j] = True
        first = np.flatnonzero(~np.isnan(close[:, j]))[0]; meta[s]['first_hour'] = int(grid[first]); meta[s]['missing'] = int(filled[first:, j].sum())
        for i in range(first+1, len(grid)):
            if np.isnan(close[i, j]): close[i, j] = close[i-1, j]
    a.out.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out/'binance.npz', hours=grid, close=close, qv=qv, filled=filled, syms=np.array(SYMS))
    btc = close[:, -1]; gate = {}
    for d in range((int(H[0])+24*30)//24, a.end_hour//24+1):
        i = d*24-1-start
        if i < 719 or i >= len(grid): continue
        gate[str(d)] = bool(btc[i] >= btc[i-719:i+1].mean())
    (a.out/'gate_btc720.json').write_text(json.dumps(gate, separators=(',', ':')))
    meta['gate_days'] = len(gate); meta['gate_on_frac'] = float(np.mean(list(gate.values())))
    meta['sha256'] = {f: hashlib.sha256((a.out/f).read_bytes()).hexdigest() for f in ('binance.npz', 'gate_btc720.json')}
    (a.out/'binance_meta.json').write_text(json.dumps(meta, indent=1)); print(json.dumps(meta))


if __name__ == '__main__':
    main()
