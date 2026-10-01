import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from feats import *
m = load(); days, f, y, liq = daily_panel(m)
F3, F1 = {}, {}
for k in LIVE:
    rows = json.load(open(D/f'funding_{k}.json'))
    ts = pd.to_datetime([r[0] for r in rows], unit='ms', utc=True); v = pd.Series([r[1] for r in rows], index=ts)
    F3[k] = pd.Series({d: v[(v.index >= d - pd.Timedelta(hours=72)) & (v.index < d)].sum() / 3 for d in days if d >= v.index[0] + pd.Timedelta(hours=72)})
    F1[k] = pd.Series({d: v[(v.index >= d - pd.Timedelta(hours=24)) & (v.index < d)].sum() for d in days if d >= v.index[0] + pd.Timedelta(hours=24)})
F3, F1 = pd.DataFrame(F3), pd.DataFrame(F1)
Y = y[LIVE]
def report(name, F, lo, hi):
    ic = []
    for d in F.index:
        if d < pd.Timestamp(lo, tz='UTC') or d > pd.Timestamp(hi, tz='UTC'): continue
        a, b = F.loc[d].values.astype(float), Y.loc[d].values.astype(float)
        if np.isfinite(a).all() and np.isfinite(b).all() and np.std(a) > 0: ic.append(spearmanr(-a, b)[0])
    ic = np.array(ic)
    print('%-12s %s..%s n=%d  IC(-F) %.4f  t=%.2f' % (name, lo, hi, len(ic), ic.mean(), ic.mean() / ic.std() * np.sqrt(len(ic))))
report('F3 (prereg)', F3, '2023-05-05', '2025-12-31')
report('F1 (diag)', F1, '2023-05-05', '2025-12-31')
