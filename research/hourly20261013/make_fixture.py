"""Hourly-cadence Go replay fixture: same hours/books/folds as longkfold20261007/make_fixture.py, ranks keyed by EVERY
issued hour (features from bars < issue hour). --smooth: ema:<a> (continuous hourly EMA of raw), anchored (.35*raw_h +
.65*previous day's 00:00 daily EMA, = incumbent at 00:00), raw. --daily-from: daily EMA .35 of 00:00 raw (sanity)."""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd


def smooth(I, R, how):
    if how == 'raw': return R.copy()
    if how.startswith('ema:'):
        a = float(how[4:]); e = R.copy()
        for k in range(1, len(e)): e[k] = a*R[k]+(1-a)*e[k-1]
        return e
    if how == 'anchored':
        d = I % 24 == 0; dr = R[d]; de = dr.copy()
        for k in range(1, len(de)): de[k] = .35*dr[k]+.65*de[k-1]
        di = np.cumsum(d)-1; out = R.copy(); m = di > 0
        out[m] = .35*R[m]+.65*de[di[m]-1]
        return out
    raise ValueError(how)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--scores', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--smooth', default='ema:0.0178'); ap.add_argument('--drop', nargs='*', default=[])
    a = ap.parse_args()
    z = np.load(a.panel); H, D, pairs = z['hours'], z['data'], list(z['pairs'])
    s = np.load(a.scores); I, raw, model = s['issued'], s['raw'], s['model']
    assert np.all(np.diff(I) == 1) and list(s['pairs']) == pairs and I[0] % 24 == 0
    S = smooth(I, raw, a.smooth)
    keep = [j for j, p in enumerate(pairs) if p not in a.drop]
    H0 = int(H[0]); blocks = sorted(set(model.tolist()))
    first, last = blocks[0]+1, int(H[-1])
    hrs = np.arange(first, last+1); idx = hrs-H0
    vol = D[:, :, 4]; c24 = np.cumsum(np.vstack([np.zeros((1, vol.shape[1])), vol]), axis=0)
    hours = [dict(TS=int(h*3600), Open=D[i, keep, 0].tolist(), PriorTurnover=vol[i-1, keep].tolist(), Volume24=(c24[i, keep]-c24[i-24, keep]).tolist()) for h, i in zip(hrs, idx)]
    folds = []
    for v in blocks:
        a0 = v+1-first; b0 = min(v+28*24+1-first, len(hrs))
        if b0-a0 >= 7*24: folds.append([int(a0), int(b0)])
    ranks = {str(int(h*3600)): S[k, keep].tolist() for k, h in enumerate(I)}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(Pairs=[pairs[j]+'USDT' for j in keep], Hours=hours, Ranks=ranks, Folds=folds, Cadence='hourly'), separators=(',', ':')))
    print(json.dumps(dict(out=str(a.out), hours=len(hours), folds=len(folds), ranks=len(ranks), smooth=a.smooth, pairs=len(keep))))


if __name__ == '__main__':
    main()
