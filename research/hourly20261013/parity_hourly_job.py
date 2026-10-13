"""Parity: bitbankgo scripts/rotation_hourly_inference.issue_hourly (the paper A/B job) vs the research hourly scores/EMA
on the 2026-09-23 refit block (model = fit_refresh on the panel, which reproduces the live bundle). usage: parity_hourly_job.py panel.npz m0.npz"""
import sys
import numpy as np
sys.path.insert(0, '/vfast/data/code/bitbankgo/scripts')
from rotation_refresh import fit_refresh
from rotation_hourly_inference import issue_hourly
z = np.load(sys.argv[1]); H, D, pairs = z['hours'], z['data'], [p+'USDT' for p in z['pairs']]; H0 = int(H[0])
s = np.load(sys.argv[2]); I, R = s['issued'], s['raw']
V = 497256; lo = H0+(-H0) % 24
model, _, rec = fit_refresh(D[lo-H0:V-1-H0], H[lo-H0:V-1-H0], V)
man = dict(schema='rotation-rank-bundle-v1', live_enabled=False, pairs=pairs, files={'m': 'x'}, valid_from_hour=V, valid_until_hour=V+672, train_last_origin_hour=rec['train_last_origin_hour'])
pos = {int(h): k for k, h in enumerate(I)}; st = None; maxd = 0; ema = None; a = .0178
for h in range(V, int(H[-1])+1):
    hist = dict(pairs=pairs, hours=list(range(h-337, h)), ohlcv=D[h-337-H0:h-H0].tolist())
    st = issue_hourly(man, model, hist, st, issued_hour=h, now_hour=h)
    r = R[pos[h]]; maxd = max(maxd, float(np.abs(np.array(st['raw_scores'])-r).max()))
    ema = r if ema is None else a*r+(1-a)*ema
print('hours', h-V+1, 'max |raw diff|', maxd, 'max |ema diff|', float(np.abs(np.array(st['smoothed_scores'])-ema).max()), 'daily', [d['issued_hour'] for d in st['daily']])
