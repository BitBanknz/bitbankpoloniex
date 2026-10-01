import json
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
D = ROOT/'data/ranker'
LIVE = ['BNB','ETC','ETH','PEPE','SUI','TRX','XRP','ZEC']

def load():
    return {k: pd.read_parquet(D/f'{k}.parquet') for k in ('open','high','low','close','qv')}

def daily_panel(m):
    """Decision time = 00:00 UTC of day d using bars through 23:00 of d-1; execution = open of 01:00 on d."""
    o, h, l, c, qv = m['open'], m['high'], m['low'], m['close'], m['qv']
    days = c.index[c.index.hour == 0]
    f = {}
    ci = c.ffill(limit=6)
    def at(df, shift): return df.shift(shift).loc[days]
    cl = ci.shift(1)  # last closed bar close at 00:00
    for n in (1, 3, 7, 14, 30, 60, 120):
        f[f'ret{n}'] = np.log(cl.loc[days] / cl.shift(24*n).loc[days])
    r1h = np.log(ci / ci.shift(1))
    for n in (7, 30):
        f[f'vol{n}'] = r1h.shift(1).rolling(24*n, min_periods=24*n//2).std().loc[days]
    rng = ((h - l) / c).shift(1)
    f['rng7'] = rng.rolling(24*7, min_periods=24).mean().loc[days]
    dv = qv.shift(1).rolling(24, min_periods=12).sum()
    f['dv1'] = np.log1p(dv.loc[days])
    f['dv30'] = np.log1p(qv.shift(1).rolling(24*30, min_periods=24*7).sum().loc[days] / 30)
    f['dvchg'] = f['dv1'] - f['dv30']
    hi30 = h.shift(1).rolling(24*30, min_periods=24*7).max()
    lo30 = l.shift(1).rolling(24*30, min_periods=24*7).min()
    f['dist_hi30'] = np.log(cl.loc[days] / hi30.loc[days])
    f['dist_lo30'] = np.log(cl.loc[days] / lo30.loc[days])
    btc = f['ret7']['BTC'] if 'BTC' in c else None
    for n in (1, 7, 30):
        f[f'rel{n}'] = f[f'ret{n}'].sub(f[f'ret{n}']['BTC'], axis=0) if 'BTC' in c else f[f'ret{n}']
    # liquidity gate: trailing 30d mean daily quote volume
    liq = f['dv30']
    # label: open(01:00 d) -> open(01:00 d+1)
    o1 = o.shift(-1).loc[days]
    o25 = o.shift(-25).loc[days]
    y = np.log(o25 / o1)
    return days, f, y, liq

def long_form(days, f, y, liq, min_dv=np.log1p(100000)):
    names = list(f)
    arr = np.stack([f[k].values for k in names], axis=-1)  # T x N x F
    T, N, F = arr.shape
    ok = np.isfinite(arr).all(-1) & (liq.values >= min_dv)
    return names, arr, y.values, ok

def xs_rank(a, ok):
    """per-day cross-sectional rank to [-0.5,0.5] over eligible assets; nan elsewhere."""
    out = np.full(a.shape, np.nan)
    for t in range(a.shape[0]):
        m = ok[t]
        if m.sum() < 3: continue
        r = a[t, m].argsort(kind='stable').argsort(kind='stable')
        out[t, m] = r / (m.sum() - 1) - 0.5
    return out
