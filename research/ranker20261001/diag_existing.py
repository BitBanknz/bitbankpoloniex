"""Descriptive: how good are the fixture's existing rank scores (8 live pairs) as a next-day ranker?"""
import json, numpy as np, pandas as pd
from scipy.stats import spearmanr
from feats import *
m = load(); days, f, y, liq = daily_panel(m)
fx = json.load(open(ROOT/'data/frontier_20260912/ledger/fixture.json'))
pairs = [p[:-4] for p in fx['Pairs']]
rows = []
for ts, sc in fx['Ranks'].items():
    d = pd.Timestamp(int(ts), unit='s', tz='UTC')
    if d not in y.index: continue
    yy = y.loc[d, pairs].values.astype(float)
    if not np.isfinite(yy).all(): continue
    rows.append((d, np.array(sc), yy))
ic = np.array([spearmanr(s, yy)[0] for _, s, yy in rows])
top3 = np.array([yy[np.argsort(-s)[:3]].mean() - yy.mean() for _, s, yy in rows])
top1 = np.array([yy[np.argmax(s)] - yy.mean() for _, s, yy in rows])
print('days', len(rows), rows[0][0].date(), rows[-1][0].date())
print('IC mean %.4f  t=%.2f' % (ic.mean(), ic.mean() / ic.std() * np.sqrt(len(ic))))
print('top3-excess mean %.4f%%/day  t=%.2f ; top1 %.4f%%' % (top3.mean()*100, top3.mean()/top3.std()*np.sqrt(len(top3)), top1.mean()*100))
mom = [(spearmanr(f['ret30'].loc[d, pairs].values, yy)[0]) for d, _, yy in rows if np.isfinite(f['ret30'].loc[d, pairs].values.astype(float)).all()]
print('ref: ret30 IC %.4f' % np.nanmean(mom))
