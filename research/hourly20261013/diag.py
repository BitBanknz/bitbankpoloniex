"""IC / top-3 excess of hourly signal variants vs forward returns from the next hour's open (1h delay).
usage: diag.py <panel.npz> <scores.npz> [--drop ZEC]"""
import argparse
import numpy as np
from scipy.stats import rankdata

ap = argparse.ArgumentParser(); ap.add_argument('panel'); ap.add_argument('scores'); ap.add_argument('--drop', default=''); ap.add_argument('--h', type=int, nargs='*', default=[24, 72])
a = ap.parse_args()
z = np.load(a.panel); H, D, pairs = z['hours'], z['data'], list(z['pairs']); H0 = int(H[0])
s = np.load(a.scores); I, R = s['issued'], s['raw']
keep = [j for j, p in enumerate(pairs) if p != a.drop]
op = D[:, :, 0]


def variants(I, R):
    d = I % 24 == 0; out = {}
    # incumbent: daily EMA .35 of 00:00 raw, held all day
    dr = R[d]; de = dr.copy()
    for k in range(1, len(de)): de[k] = .35*dr[k]+.65*de[k-1]
    di = np.cumsum(d)-1; out['daily_ema35'] = de[di]
    # anchored: today's term refreshed hourly against yesterday's EMA
    prev = np.vstack([de[:1]*0+dr[:1], de[:-1]])[di]; prev[di == 0] = R[di == 0]
    out['anchored'] = .35*R+.65*prev
    out['raw_hourly'] = R
    for al in (.0178, .05, .1, .25):
        e = R.copy()
        for k in range(1, len(e)): e[k] = al*R[k]+(1-al)*e[k-1]
        out[f'ema_h{al}'] = e
    return out


V = variants(I, R)
idx = I-H0
for h in a.h:
    ok = idx+1+h < len(D)
    fwd = op[idx[ok]+1+h]/op[idx[ok]+1]-1
    print(f'horizon {h}h, n={ok.sum()} hours, pairs={len(keep)}')
    for name, S in V.items():
        x = S[ok][:, keep]; y = fwd[:, keep]
        rx = np.apply_along_axis(rankdata, 1, x); ry = np.apply_along_axis(rankdata, 1, y)
        rx -= rx.mean(1, keepdims=True); ry -= ry.mean(1, keepdims=True)
        ic = (rx*ry).sum(1)/np.sqrt((rx**2).sum(1)*(ry**2).sum(1))
        top = np.argsort(-x, axis=1)[:, :3]; ex = np.take_along_axis(y, top, 1).mean(1)-y.mean(1)
        flips = (np.argsort(-x, 1)[:, :3][1:, None, :] == np.argsort(-x, 1)[:, :3][:-1, :, None]).any(1).sum(1)
        print(f'  {name:14s} IC {ic.mean():+.4f} (t {ic.mean()/ic.std()*np.sqrt(len(ic)/h):+.2f})  top3x {1e4*ex.mean():+6.1f}bp  top3 changes/day {24*(3-flips.mean()):.2f}')
