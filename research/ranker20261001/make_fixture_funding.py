import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from feats import *
exec(open('funding_ic.py').read().split("def report")[0])
fx = json.load(open(ROOT/'data/frontier_20260912/ledger/fixture.json'))
ks = sorted(fx['Ranks'], key=int); S = np.array([fx['Ranks'][k] for k in ks]); R = S.copy()
for t in range(1, len(S)): R[t] = (S[t] - .65 * S[t - 1]) / .35
Z = np.zeros_like(R); miss = 0
for i, k in enumerate(ks):
    d = pd.Timestamp(int(k), unit='s', tz='UTC')
    fv = F3.loc[d, [p[:-4] for p in fx['Pairs']]].values.astype(float) if d in F3.index else np.full(8, np.nan)
    if not np.isfinite(fv).all(): miss += 1; zs = np.zeros(8)
    else: s = -fv; zs = (s - s.mean()) / (s.std() or 1)
    z = .75 * R[i] + .25 * zs
    Z[i] = (z - z.mean()) / z.std()
out = np.zeros_like(Z); out[0] = Z[0]
for t in range(1, len(Z)): out[t] = .35 * Z[t] + .65 * out[t - 1]
print('days without funding:', miss)
pairs = [p[:-4] for p in fx['Pairs']]
def ic(M):
    r = []
    for i, k in enumerate(ks):
        d = pd.Timestamp(int(k), unit='s', tz='UTC'); yy = Y.loc[d, pairs].values.astype(float)
        if np.isfinite(yy).all(): r.append(spearmanr(M[i], yy)[0])
    r = np.array(r); return r.mean(), r.mean() / r.std() * np.sqrt(len(r)), len(r)
print('window B IC smoothed production %.4f (t=%.2f, n=%d)' % ic(S))
print('window B IC smoothed prod+funding %.4f (t=%.2f, n=%d)' % ic(out))
print('window B IC funding alone %.4f (t=%.2f, n=%d)' % ic(np.array([ -F3.loc[pd.Timestamp(int(k), unit='s', tz='UTC'), pairs].values.astype(float) for k in ks])))
g = dict(fx); g['Ranks'] = {k: [float(v) for v in out[i]] for i, k in enumerate(ks)}
json.dump(g, open(ROOT/'data/ranker/fixture_fund.json', 'w'))
