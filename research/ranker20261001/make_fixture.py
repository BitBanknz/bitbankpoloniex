import json, sys, numpy as np, pandas as pd
from scipy.stats import spearmanr
from feats import *
MODEL = sys.argv[1]
z = np.load(D/'wf_scores.npz', allow_pickle=True)
dates = pd.DatetimeIndex(z['dates'], tz='UTC'); cols = list(z['cols']); S = z[MODEL]
fx = json.load(open(ROOT/'data/frontier_20260912/ledger/fixture.json'))
pairs = [p[:-4] for p in fx['Pairs']]; idx = [cols.index(p) for p in pairs]
m = load(); days, f, y, liq = daily_panel(m); Y = y.values[:, [list(y.columns).index(p) for p in pairs]]
def rk(a): return a.argsort().argsort().astype(float)
r1, r2, miss = {}, {}, 0
ic = {'prod': [], 'new': [], 'blend': []}
for ts, prod in fx['Ranks'].items():
    d = pd.Timestamp(int(ts), unit='s', tz='UTC'); t = dates.get_loc(d) if d in dates else None
    prod = np.array(prod)
    s = S[t, idx] if t is not None else None
    if s is None or not np.isfinite(s).all(): miss += 1; r1[ts] = list(prod); r2[ts] = list(prod); continue
    bl = rk(s) + rk(prod) + 1e-6 * s
    r1[ts] = [float(v) for v in s]; r2[ts] = [float(v) for v in bl]
    yy = Y[days.get_loc(d)]
    if np.isfinite(yy).all():
        ic['prod'].append(spearmanr(prod, yy)[0]); ic['new'].append(spearmanr(s, yy)[0]); ic['blend'].append(spearmanr(bl, yy)[0])
print('missing days (fell back to production):', miss, 'of', len(fx['Ranks']))
for k, v in ic.items(): v = np.array(v); print('window B IC %-6s n=%d %.4f (t=%.2f)' % (k, len(v), v.mean(), v.mean() / v.std() * np.sqrt(len(v))))
print('corr(new,prod) mean daily spearman: %.3f' % np.mean([spearmanr(np.array(r1[k]), np.array(fx['Ranks'][k]))[0] for k in r1]))
for name, r in (('r1', r1), ('r2', r2)):
    g = dict(fx); g['Ranks'] = r
    out = ROOT/f'data/ranker/fixture_{name}.json'; json.dump(g, open(out, 'w'))
