"""Fast-sim calibration on the hourly arms already run in Go: h_ema (hourly EMA .0178, hourly top-3) and h_raw."""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from hn_sim import run, folds
z = np.load('/vfast/data/code/bitbankpoloniex/data/longkfold20261007/panel.npz'); H, D = z['hours'], z['data']; H0 = int(H[0]); op = D[:, :, 0]
s = np.load('/vfast/data/trading_research_20261013/hourly/scores/m0.npz'); I, R, M = s['issued'], s['raw'], s['model']
hs = np.array([31, 32, 4, 52, 109, 13, 17, 58])/2e4
for name, al in (('h_ema', .0178), ('h_raw', 1.)):
    e = R.copy()
    for k in range(1, len(e)): e[k] = al*R[k]+(1-al)*e[k-1]
    sig = np.full(op.shape, np.nan); ii = I-H0+1; ok = ii < len(sig); sig[ii[ok]] = e[ok]
    for fee in (.0014,):
        for drop in (None, 7):
            keep = [j for j in range(8) if j != drop]
            r = 100*np.array([run(op[:, keep], sig[:, keep], hs[keep], fee, a0, b0, topk_exit=True)[-1]-1 for a0, b0, V in folds(H, sorted(set(M.tolist())))])
            print(name, fee, 'xZEC' if drop else '8p', f'mean {r.mean():+.2f} worst {r.min():+.2f}')
