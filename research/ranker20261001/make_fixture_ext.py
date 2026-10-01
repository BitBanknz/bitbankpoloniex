import json, sys, numpy as np, pandas as pd
from feats import *
MODEL = sys.argv[1]; MINDV = float(sys.argv[2]) if len(sys.argv) > 2 else 1e6
z = np.load(D/'wf_scores.npz', allow_pickle=True)
dates = pd.DatetimeIndex(z['dates'], tz='UTC'); cols = list(z['cols']); S = z[MODEL]
fx = json.load(open(ROOT/'data/frontier_20260912/ledger/fixture.json'))
mk = {m['symbol'] for m in json.load(open(ROOT/'data/frontier_20260912/ledger/markets.json'))}
o = pd.read_parquet(D/'open.parquet'); qv = pd.read_parquet(D/'qv.parquet')
ts = [pd.Timestamp(h['TS'], unit='s', tz='UTC') for h in fx['Hours']]
t0, t1 = ts[0], ts[-1]
ref = pd.Timestamp('2026-01-13', tz='UTC')
dv30 = qv.loc[ref - pd.Timedelta(days=30):ref - pd.Timedelta(hours=1)].sum() / 30
pairs = []
for c in o.columns:
    if f'{c}_USDT' not in mk or not dv30.get(c, 0) >= MINDV: continue
    win = o.loc[t0 - pd.Timedelta(hours=25):t1, c]
    if win.isna().any() or (qv.loc[t0 - pd.Timedelta(hours=25):t1, c].isna().any()): continue
    pairs.append(c)
print(len(pairs), 'pairs', pairs)
Hrs = []
for t in ts:
    prev = t - pd.Timedelta(hours=1)
    Hrs.append(dict(TS=int(t.timestamp()), Open=[float(o.loc[t, c]) for c in pairs], PriorTurnover=[float(qv.loc[prev, c]) for c in pairs],
                    Volume24=[float(qv.loc[t - pd.Timedelta(hours=24):prev, c].sum()) for c in pairs]))
ci = [cols.index(c) for c in pairs]; R = {}
for k in fx['Ranks']:
    d = pd.Timestamp(int(k), unit='s', tz='UTC'); s = S[dates.get_loc(d), ci]
    R[k] = [float(v) if np.isfinite(v) else -99.0 for v in s]
g = dict(fx); g['Pairs'] = [c + 'USDT' for c in pairs]; g['Hours'] = Hrs; g['Ranks'] = R
json.dump(g, open(D/'fixture_r3.json', 'w'))
