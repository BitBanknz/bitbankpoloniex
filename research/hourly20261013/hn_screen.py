"""Screen hourly-native configs in the fast simulator (prereg grid). usage: hn_screen.py panel.npz preds.npz halfspread_json [--drop ZEC]"""
import argparse, itertools, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__)); from hn_sim import run, folds
ap = argparse.ArgumentParser(); ap.add_argument('panel'); ap.add_argument('preds'); ap.add_argument('hs'); ap.add_argument('--drop', default=''); ap.add_argument('--split', action='store_true', help='print pre-2024 mean/worst and 2024+ mean/worst')
a = ap.parse_args()
z = np.load(a.panel); allp = list(z['pairs']); H = z['hours']; H0 = int(H[0])
s = np.load(a.preds); pairs = list(s['pairs']); I, Pr, M = s['issued'], s['pred'], s['model']
D = z['data'][:, [allp.index(p) for p in pairs]]; op = D[:, :, 0].copy()
for j in range(op.shape[1]):  # forward fill gaps
    c = op[:, j]; bad = ~np.isfinite(c); idx = np.where(~bad, np.arange(len(c)), 0); np.maximum.accumulate(idx, out=idx); op[:, j] = c[idx]
sig = np.full(op.shape, np.nan); ii = I-H0+1; ok = ii < len(sig); sig[ii[ok]] = Pr[ok]
keep = [j for j, p in enumerate(pairs) if p != a.drop]; op, sig = op[:, keep], sig[:, keep]
hs = np.array([json.loads(a.hs)[pairs[j]] for j in keep])/1e4
F = folds(H, sorted(set(M.tolist()))); y24 = np.array([V for _, _, V in F]) >= 473352  # 2024-01-01
xs = 'xs24' in a.preds
for th_in, th_out, mh, k in itertools.product((0., .005, .01), (0., -.005), (24, 72), (3, 5)):
    row = []
    for fee in (.0014, .0033):
        r = 100*np.array([run(op, sig, hs, fee, a0, b0, slots=k, th_in=th_in, th_out=th_out, min_hold=mh)[-1]-1 for a0, b0, _ in F])
        row.append(f'{r.mean():+.2f}/{r.min():+.1f}/{r[y24].mean():+.2f}' if not a.split else f'{r[~y24].mean():+.3f}/{r[~y24].min():+.2f}/{r[y24].mean():+.3f}/{r[y24].min():+.2f}')
    print(f'{os.path.basename(a.preds)[:-4]} {a.drop or "8p"} in{th_in*1e4:.0f} out{th_out*1e4:.0f} mh{mh} k{k} | 14: {row[0]} | 33: {row[1]}', flush=True)
