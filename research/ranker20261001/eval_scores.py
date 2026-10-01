import sys, numpy as np, pandas as pd
from scipy.stats import spearmanr
from feats import *
win = sys.argv[1]
lo, hi = {'A': ('2023-01-01', '2025-12-31'), 'B': ('2026-01-14', '2026-09-06')}[win]
z = np.load(D/'wf_scores.npz', allow_pickle=True)
dates = pd.DatetimeIndex(z['dates'], tz='UTC'); cols = list(z['cols'])
m = load(); days, f, y, liq = daily_panel(m)
idx = [cols.index(p) for p in LIVE]
sel = (dates >= pd.Timestamp(lo, tz='UTC')) & (dates <= pd.Timestamp(hi, tz='UTC'))
Y = y.values[:, idx]
for k in [k for k in z.files if k not in ('dates', 'cols')]:
    S = z[k][:, idx]; ic = []; ex = []
    for t in np.where(sel)[0]:
        s, yy = S[t], Y[t]
        if not (np.isfinite(s).all() and np.isfinite(yy).all()): continue
        ic.append(spearmanr(s, yy)[0]); ex.append(yy[np.argsort(-s)[:3]].mean() - yy.mean())
    ic, ex = np.array(ic), np.array(ex)
    print('%-10s n=%d IC %.4f (t=%.2f) top3ex %.4f%%/day (t=%.2f)' % (k, len(ic), ic.mean(), ic.mean()/ic.std()*np.sqrt(len(ic)), ex.mean()*100, ex.mean()/ex.std()*np.sqrt(len(ex))))
