"""Hourly-native edge predictions (prereg docs/2026-10-14-hourly-native-prereg.md). Hourly origins, production 28-day refit grid,
expanding from 2023-06-01, origins <= valid_from-5d (and the 24h target fully matured before valid_from-1).
--target abs24: open(h+25)/open(h+1)-1-rt_cost(pair); xs24: 24h return minus same-hour cross-sectional mean.
usage: hn_scores.py --panel wide.npz --pairs A B .. --cost-bp '{"A":40,..}' --target abs24 --learner gbdt --out x.npz"""
import argparse, json, os, sys
from pathlib import Path
import numpy as np
sys.path.insert(0, '/vfast/data/code/bitbankgo/scripts')
from poloniex_rank_models import features_at, rank_features  # noqa: E402
ANCHOR, PERIOD = 497256, 28*24


def ffill(D):
    D = D.copy()
    for j in range(D.shape[1]):
        c = D[:, j, 3]; bad = ~np.isfinite(c)
        if bad.any():
            idx = np.where(~bad, np.arange(len(c)), 0); np.maximum.accumulate(idx, out=idx)
            for k in range(4): D[:, j, k] = np.where(bad, c[idx], D[:, j, k])
            D[bad, j, 4] = 0
    return D


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--pairs', nargs='+', required=True)
    ap.add_argument('--cost-bp', required=True); ap.add_argument('--target', choices=['abs24', 'xs24'], required=True)
    ap.add_argument('--learner', choices=['gbdt', 'ridge'], required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--cache', type=Path); ap.add_argument('--threads', type=int, default=4)
    a = ap.parse_args()
    z = np.load(a.panel); allp = list(z['pairs']); sel = [allp.index(p) for p in a.pairs]
    H = z['hours']; D = ffill(z['data'][:, sel]); H0 = int(H[0]); n, P = len(H), len(sel)
    assert np.isfinite(D[:, :, :4]).all(), 'pair not listed for the whole grid'
    cost = np.array([json.loads(a.cost_bp)[p] for p in a.pairs])/1e4
    if a.cache and a.cache.exists(): X = np.load(a.cache)['x']
    else:
        X = np.full((n+1, P, 38), np.nan); idx = np.arange(337, n+1)
        for k in range(0, len(idx), 2000):
            f, _ = features_at(D, idx[k:k+2000]); X[idx[k:k+2000]] = np.concatenate([f, rank_features(f)], axis=-1)
        if a.cache: np.savez(a.cache, x=X)
    op = D[:, :, 0]; Y = np.full((n, P), np.nan); r = op[25:]/op[1:-24]-1; Y[:n-25] = r
    Y = Y-cost if a.target == 'abs24' else Y-np.nanmean(Y, axis=1, keepdims=True)
    grid = ANCHOR+PERIOD*np.arange(-60, 3); grid = grid[(grid > H0+400) & (grid <= int(H[-1])+1)]
    out_h, out_p, out_m = [], [], []
    for V in grid:
        g = np.arange(360, V-H0-1-26); g = g[H[g] <= V-5*24]
        if len(g) < 40*24: continue
        x = X[g].reshape(-1, 38); y = Y[g].reshape(-1); ok = np.isfinite(x).all(1) & np.isfinite(y)
        mu, sd = x[ok].mean(0), np.maximum(x[ok].std(0), 1e-9); xz = np.clip((x[ok]-mu)/sd, -10, 10); yc = np.clip(y[ok], -.5, .5)
        hrs = np.arange(V, min(V+PERIOD, int(H[-1])+2)); xi = np.clip((X[hrs-H0].reshape(-1, 38)-mu)/sd, -10, 10)
        if a.learner == 'gbdt':
            import lightgbm as lgb
            m = lgb.LGBMRegressor(n_estimators=200, max_depth=3, num_leaves=7, learning_rate=.03, min_child_samples=200, reg_lambda=10,
                                  subsample=.5, subsample_freq=1, random_state=20261014, n_jobs=a.threads, verbosity=-1, deterministic=True, force_col_wise=True).fit(xz, yc)
            p = m.predict(xi, num_threads=a.threads)
        else:
            A = np.c_[xz, np.ones(len(xz))]; w = np.linalg.solve(A.T@A+10*len(xz)/1e4*np.eye(A.shape[1]), A.T@yc); p = np.c_[xi, np.ones(len(xi))]@w
        out_h.append(hrs); out_p.append(p.reshape(len(hrs), P)); out_m.append(np.full(len(hrs), V))
        print('refit', V, 'rows', int(ok.sum()), flush=True)
    np.savez_compressed(a.out, issued=np.concatenate(out_h), pred=np.concatenate(out_p), model=np.concatenate(out_m), pairs=np.array(a.pairs), cost=cost)


if __name__ == '__main__':
    main()
