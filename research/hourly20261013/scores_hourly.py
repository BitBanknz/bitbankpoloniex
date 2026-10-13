"""Causal HOURLY raw rank scores on the production refit grid (valid_from phase 2026-09-23, 28-day blocks).
Training per refit V: panel slice [start, V-1), origins with hour <= V-5d (fit_refresh purge), stride 24
(--origins daily, = production) or 1 (--origins hourly, 24x phase-pooled). Inference at EVERY hour h of the
block from the 337 completed hours before h (features_at(D,[h]) uses bars < h only).
Check: --origins daily at h%24==0 reproduces longkfold20261007 scores (max diff printed)."""
import argparse, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, os.environ.get('BITBANKGO_SCRIPTS', '/vfast/data/code/bitbankgo/scripts'))
from poloniex_rank_models import RankModel, features_at, rank_features  # noqa: E402

ANCHOR, PERIOD = 497256, 28*24
PARAMS = dict(n_estimators=70, num_leaves=5, max_depth=2, reg_lambda=20)


def all_features(D, cache):
    if cache and cache.exists():
        z = np.load(cache); return z['x']
    n = len(D); x = np.full((n, D.shape[1], 38), np.nan, dtype=np.float64)
    idx = np.arange(337, n+1 if False else n)
    for k in range(0, len(idx), 2000):
        f, _ = features_at(D, idx[k:k+2000]); x[idx[k:k+2000]] = np.concatenate([f, rank_features(f)], axis=-1)
    if cache: np.savez(cache, x=x)
    return x


def targets(D, horizon=72):
    n = len(D); y = np.full((n, D.shape[1]), np.nan)
    for i in range(n-horizon+1):
        path = D[i:i+horizon, :, 3]/D[i, :, 0]
        peak = np.maximum.accumulate(np.vstack([np.ones((1, D.shape[1])), path]), axis=0)[1:]
        y[i] = path[-1]-1-.005-.5*(1-path/peak).max(axis=0)
    return y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start', default='2023-06-01'); ap.add_argument('--origins', choices=['daily', 'hourly'], default='daily')
    ap.add_argument('--cache', type=Path); ap.add_argument('--check', type=Path)
    ap.add_argument('--params', default='{}', help='json overrides of PARAMS (hourly-origin model)')
    ap.add_argument('--chronos', type=Path, help='chronos_feats.py output: adds q50@24h, q50@72h, (q90-q10)@72h raw + same-hour ranks')
    a = ap.parse_args()
    z = np.load(a.panel); H, D = z['hours'], z['data']; H0 = int(H[0])
    X = all_features(D, a.cache); Y = targets(D)
    if a.chronos:
        q = np.load(a.chronos)['q']  # (n+1, P, 2, 3) returns; row h uses bars < h
        e = np.stack([q[:len(D), :, 0, 1], q[:len(D), :, 1, 1], q[:len(D), :, 1, 2]-q[:len(D), :, 1, 0]], axis=-1).astype(np.float64)
        ok = np.isfinite(e).all(axis=(1, 2)); r = np.full_like(e, np.nan); r[ok] = rank_features(e[ok])
        X = np.concatenate([X, e, r], axis=-1)
        Xlast = np.concatenate([q[len(D), :, 0, 1], q[len(D), :, 1, 1], q[len(D), :, 1, 2]-q[len(D), :, 1, 0]]).reshape(3, -1).T[None]
        chron_last = np.concatenate([Xlast, rank_features(Xlast)], axis=-1)
    start_h = int(pd.Timestamp(a.start, tz='UTC').value//3600_000_000_000)
    last_issue = int(H[-1])+1
    grid = ANCHOR+PERIOD*np.arange(-60, 3); grid = grid[(grid > H0+400) & (grid <= last_issue)]
    params = {**PARAMS, **json.loads(a.params)}
    issued, raw, model_of, rec = [], [], [], []
    for V in grid:
        lo = max(start_h, H0); lo += (-lo) % 24
        n = V-1-lo
        if n <= 0: continue
        rel = np.arange(360, n-71, 24 if a.origins == 'daily' else 1)
        g = lo-H0+rel; g = g[H[g] <= V-5*24]
        if a.chronos: g = g[np.isfinite(X[g]).all(axis=(1, 2))]
        if len(g) < 40*(1 if a.origins == 'daily' else 24): continue
        m = RankModel('lgbm_rank', params).fit(X[g], Y[g])
        hrs = np.arange(V, min(V+PERIOD, last_issue+1)); idx = hrs-H0
        xi = X[idx] if idx[-1] < len(X) else None
        if xi is None:
            f, _ = features_at(D, idx); xi = np.concatenate([f, rank_features(f)], axis=-1)
            if a.chronos:
                xe = np.concatenate([X[idx[:-1], :, 38:], chron_last], axis=0); xi = np.concatenate([xi, xe], axis=-1)
        p = np.asarray(m.predict(xi), float)
        issued.append(hrs); raw.append(p); model_of.append(np.full(len(hrs), V))
        rec.append(dict(valid_from=int(V), origins=int(len(g)), last_origin=int(H[g[-1]])))
        print('refit', pd.Timestamp(V*3600, unit='s').date(), 'origins', len(g), flush=True)
    issued, raw, model_of = map(np.concatenate, (issued, raw, model_of))
    if a.check:
        c = np.load(a.check); pos = {int(h): k for k, h in enumerate(issued)}
        k = np.array([pos[int(h)] for h in c['issued']]); print('check max |diff| vs', a.check.name, float(np.abs(raw[k]-c['raw']).max()), 'n', len(k))
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, issued=issued, raw=raw, model=model_of, pairs=z['pairs'])
    a.out.with_suffix('.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, refits=rec), indent=1))


if __name__ == '__main__':
    main()
