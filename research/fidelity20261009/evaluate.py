"""Summarise the 2026-10-09 fidelity k-fold. usage: evaluate.py <rp-root> [--md out.md]"""
import argparse, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); import grid

spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def load(d, fee):
    c = pd.read_csv(d/'curves.csv'); res = [json.loads(l) for l in open(d/'results.jsonl')]
    c = c[np.isclose(c.fee, fee)].copy(); res = [r for r in res if np.isclose(r['Fee'], fee)]; starts = {r['Fold']: r['Start'] for r in res}
    c['fold'] = c.fold.map(lambda k: str(pd.Timestamp(starts[k]-3600, unit='s').date()))
    r = G.score_frame(c[['fold', 'ts', 'equity']], 35.0); ag = r['aggregate']; f = r['folds']
    keys = sorted(f); ret = np.array([f[k]['return_pct'] for k in keys])
    sc = ag['score'] if ag['status'] == 'PASS' else ag.get('score_unbounded', float('nan'))
    return dict(keys=keys, ret=ret, mean=ret.mean(), worst=ret.min(), good=sc, caldd=ag['max_calendar_month_dd'], fills=sum(x['Report']['Fills'] for x in res),
                partial=sum(x['PartialFills'] for x in res), clip=float(np.median([x['MedianClip'] for x in res if x['MedianClip'] > 0] or [0])), halts=sum(1 for x in res if x['Halted']))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('--md', type=Path); a = ap.parse_args()
    L = []; p = L.append
    def agg(n, u, fee=0.0014):
        rs = [load(a.root/f'{n}_b{s}{u}', fee) for s in grid.SEEDS]
        return rs, {k: float(np.mean([r[k] for r in rs])) for k in ('mean', 'worst', 'good', 'caldd', 'fills', 'partial', 'clip', 'halts')}
    dl, ds = grid.name(grid.D, False), grid.name(grid.D, True)
    p('Means over book seeds ' + ','.join(map(str, grid.SEEDS)) + '; fee 14 bps + archived-book spread/depth; 42 e2306 folds.\n')
    p('| config | univ | fee | mean %/fold | seed range | worst | goodness | cal DD | fills | partial | median clip |'); p('|---|---|---|---|---|---|---|---|---|---|---|')
    for n in (dl, ds):
        for u in ('', '_xzec'):
            for fee in (0.0014, 0.0033):
                rs, m = agg(n, u, fee)
                p(f"| {n} | {u or '8p'} | {fee*1e4:.0f} | {m['mean']:+.2f} | {min(r['mean'] for r in rs):+.2f}..{max(r['mean'] for r in rs):+.2f} | {m['worst']:.2f} | {m['good']:.2f} | {m['caldd']:.1f} | {m['fills']:.0f} | {m['partial']:.0f} | {m['clip']:.1f} |")
    p('\nPaired vs deployed+safeguard (same book seed, same folds): mean diff pp/fold (t over 42x3 fold-seeds), fold-seed wins /126.\n')
    p('| config | 8p mean / good | 8p d (t) / wins | xZEC mean / good | xZEC d (t) / wins | beats D both |'); p('|---|---|---|---|---|---|')
    names = [dl] + [grid.name({**grid.D, **n}, True) for n in grid.NEIGH]
    base = {u: agg(ds, u)[0] for u in ('', '_xzec')}
    for n in names:
        row = [n]; beat = True
        for u in ('', '_xzec'):
            rs, m = agg(n, u); d = np.concatenate([r['ret']-b['ret'] for r, b in zip(rs, base[u])]); t = d.mean()/(d.std(ddof=1)/np.sqrt(len(d))) if d.std() > 0 else 0
            row += [f"{m['mean']:+.2f} / {m['good']:.2f}", f"{d.mean():+.2f} ({t:+.1f}) / {(d > 0).sum()}"]; beat &= d.mean() > 0
        p('| ' + ' | '.join(row) + f" | {'YES' if beat else 'no'} |")
    txt = '\n'.join(L); print(txt)
    if a.md: a.md.write_text(txt + '\n')


if __name__ == '__main__':
    main()
