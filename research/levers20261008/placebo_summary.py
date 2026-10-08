"""Incumbent vs placebo distribution: per-arm mean 28d fold return, worst fold, fleet-v1 goodness, per fee.
usage: placebo_summary.py <rp-root> <real-arm> <placebo-glob-prefix>   e.g. . inc_e2306 plc (arms plc1..plcN, suffix via --suffix)"""
import argparse, importlib.util, json, glob, os
from pathlib import Path
import numpy as np, pandas as pd
spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def arm(root, a, fee):
    res = [json.loads(l) for l in open(root/a/'results.jsonl')]
    res = [r for r in res if np.isclose(r['Fee'], fee)]
    c = pd.read_csv(root/a/'curves.csv'); c = c[np.isclose(c.fee, fee)]
    ag = G.score_frame(c[['fold', 'ts', 'equity']].astype({'fold': str}))['aggregate']
    r = np.array([x['LiqReturnPct'] for x in res])
    return r, ag


ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('real'); ap.add_argument('prefix'); ap.add_argument('--suffix', default=''); ap.add_argument('--fees', default='0.0014,0.003')
a = ap.parse_args()
pl = sorted([os.path.basename(p) for p in glob.glob(str(a.root/f'{a.prefix}[0-9]*{a.suffix}')) if (a.suffix or not os.path.basename(p).endswith('_xzec')) and os.path.exists(os.path.join(p, 'run.log')) and 'PASS' in open(os.path.join(p, 'run.log')).read()])
for fee in [float(x) for x in a.fees.split(',')]:
    r0, g0 = arm(a.root, a.real, fee)
    M, W, S = [], [], []
    for p in pl:
        r, g = arm(a.root, p, fee); M.append(r.mean()); W.append(r.min()); S.append(g['score'])
    M, W, S = map(np.array, (M, W, S))
    print(f"fee {fee*1e4:.0f}+5 bps | {a.real}: mean {r0.mean():+.2f} worst {r0.min():+.2f} goodness {g0['score']:+.2f} | placebo n={len(M)}: mean {M.mean():+.2f} (sd {M.std(ddof=1):.2f}, min {M.min():+.2f}, max {M.max():+.2f}) worst {W.mean():+.2f} goodness {S.mean():+.2f} (max {S.max():+.2f}) | real rank: mean beats {int((r0.mean()>M).sum())}/{len(M)}, goodness beats {int((g0['score']>S).sum())}/{len(S)}, z {(r0.mean()-M.mean())/M.std(ddof=1):+.2f}")
