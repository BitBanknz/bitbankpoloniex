"""Sanity: the fast simulator on the incumbent policy (daily EMA .35 ranks, 01:00 decisions, top-3, 72h hold) vs the Go harness."""
import sys, numpy as np
sys.path.insert(0, __import__('os').path.dirname(__file__)); from hn_sim import run, folds
z = np.load('/vfast/data/code/bitbankpoloniex/data/longkfold20261007/panel.npz'); H, D = z['hours'], z['data']; H0 = int(H[0]); op = D[:, :, 0]
s = np.load('/vfast/data/trading_research_20261013/hourly/scores/m0.npz'); I, R, M = s['issued'], s['raw'], s['model']
d = I % 24 == 0; dr = R[d]; de = dr.copy()
for k in range(1, len(de)): de[k] = .35*dr[k]+.65*de[k-1]
sig = np.full(op.shape, np.nan); di = I[d]-H0
for k, i in enumerate(di):
    if i+1 < len(sig): sig[i+1] = de[k]
hs = np.array([31, 32, 4, 52, 109, 13, 17, 58])/2e4
for fee in (.0014, .0033):
    for drop in (None, 7):
        keep = [j for j in range(8) if j != drop]
        r = [run(op[:, keep], sig[:, keep], hs[keep], fee, a0, b0, daily=True, topk_exit=True)[-1]-1 for a0, b0, V in folds(H, sorted(set(M.tolist())))]
        r = 100*np.array(r); y = np.array([V for _, _, V in folds(H, sorted(set(M.tolist())))]) >= 473352; print(fee, "xZEC" if drop else "8p", f"mean {r.mean():+.2f} worst {r.min():+.2f} since2024 {r[y].mean():+.2f} n {len(r)}")
