"""Apply the pre-registered pass rule (docs/2026-10-08-knob-grid-measured-cost-prereg.md) to the knob grid.
usage: evaluate.py <rp-root> [--md out.md]"""
import argparse, importlib.util, json, math, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); import grid

spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
FEES = grid.FEES; SPLIT = '2025-03-01'


def load(d, fee):
    c = pd.read_csv(d/'curves.csv'); res = [json.loads(l) for l in open(d/'results.jsonl')]
    c = c[np.isclose(c.fee, fee)].copy(); starts = {r['Fold']: r['Start'] for r in res if np.isclose(r['Fee'], fee)}
    c['fold'] = c.fold.map(lambda k: str(pd.Timestamp(starts[k]-3600, unit='s').date()))
    r = G.score_frame(c[['fold', 'ts', 'equity']], 35.0); ag = r['aggregate']; f = r['folds']
    keys = sorted(f); ret = np.array([f[k]['return_pct'] for k in keys])
    fills = sum(x['Report']['Fills'] for x in res if np.isclose(x['Fee'], fee)); halts = sum(1 for x in res if np.isclose(x['Fee'], fee) and x['Halted'])
    sc = ag['score'] if ag['status'] == 'PASS' else ag.get('score_unbounded', float('nan'))
    return dict(keys=keys, ret=ret, mean=ret.mean(), worst=ret.min(), good=sc, status=ag['status'], caldd=ag['max_calendar_month_dd'], mdd=ag['max_marked_dd'], fills=fills, halts=halts)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('--md', type=Path); a = ap.parse_args()
    cfgs = grid.configs(); dn = grid.name(grid.D)
    R = {(n, u, fee): load(a.root/(n+u), fee) for n in cfgs for u in ('', '_xzec') for fee in FEES}
    def diff(n, u, fee, sel=None):
        x, b = R[(n, u, fee)], R[(dn, u, fee)]; assert x['keys'] == b['keys']; d = x['ret']-b['ret']
        if sel is not None: m = np.array([sel(k) for k in x['keys']]); d = d[m]
        return d
    beats12 = {n: R[(n, '', FEES[0])]['mean'] > R[(dn, '', FEES[0])]['mean'] and R[(n, '_xzec', FEES[0])]['mean'] > R[(dn, '_xzec', FEES[0])]['mean'] for n in cfgs}
    def neighbours(c):
        out = []
        for ax, vals in grid.AXES.items():
            if c[ax] == grid.D[ax] or ax == 'topup': continue
            i = vals.index(c[ax])
            for j in (i-1, i+1):
                if 0 <= j < len(vals): nc = dict(c); nc[ax] = vals[j]; out.append(nc)
        names = [grid.name(x) for x in out]; return [m for m in names if m in cfgs and m != dn]
    L = []; p = L.append; b0 = lambda u, f: R[(dn, u, f)]
    p('| config | 19bps mean / xZEC / good / xZEC good | worst | calDD max (4 cells) | wins 8p / xZEC | 38bps mean / xZEC / good | d old / new (8p) | d old / new (xZEC) | fills 19 | rules failed |')
    p('|---|---|---|---|---|---|---|---|---|---|')
    passers = []
    for n, c in cfgs.items():
        x = {k: R[(n,)+k] for k in [('', FEES[0]), ('_xzec', FEES[0]), ('', FEES[1]), ('_xzec', FEES[1])]}
        w8 = (diff(n, '', FEES[0]) > 0).sum(); wx = (diff(n, '_xzec', FEES[0]) > 0).sum()
        old = lambda k: k < SPLIT; new = lambda k: k >= SPLIT
        do8, dn8 = diff(n, '', FEES[0], old).mean(), diff(n, '', FEES[0], new).mean(); dox, dnx = diff(n, '_xzec', FEES[0], old).mean(), diff(n, '_xzec', FEES[0], new).mean()
        caldd = max(v['caldd'] for v in x.values()); fail = []
        if n != dn:
            if not x[('', FEES[0])]['mean'] > b0('', FEES[0])['mean']: fail.append('1')
            if not x[('_xzec', FEES[0])]['mean'] > b0('_xzec', FEES[0])['mean']: fail.append('2')
            if not (x[('', FEES[0])]['good'] > b0('', FEES[0])['good'] and x[('_xzec', FEES[0])]['good'] > b0('_xzec', FEES[0])['good']): fail.append('3')
            if not (caldd <= 35 and all(v['status'] == 'PASS' for v in x.values())): fail.append('4')
            if not (w8 >= 21 and wx >= 21 and x[('', FEES[0])]['worst'] >= b0('', FEES[0])['worst']-2): fail.append('5')
            if not (x[('', FEES[1])]['mean'] > b0('', FEES[1])['mean'] and x[('_xzec', FEES[1])]['mean'] > b0('_xzec', FEES[1])['mean'] and x[('', FEES[1])]['good'] > b0('', FEES[1])['good']): fail.append('6')
            nb = neighbours(c)
            if c['topup'] != grid.D['topup'] and all(c[k] == grid.D[k] for k in ('slots', 'hold', 'cool', 'res')): pass
            elif not nb or not all(beats12[m] for m in nb): fail.append('7')
            if not (do8 > 0 and dn8 > 0 and dox > 0 and dnx > 0): fail.append('8')
            if not fail: passers.append((min(diff(n, u, f).mean() for u in ('', '_xzec') for f in FEES), n))
        f19, x19, f38, x38 = x[('', FEES[0])], x[('_xzec', FEES[0])], x[('', FEES[1])], x[('_xzec', FEES[1])]
        p(f"| {'**'+n+'** (D)' if n == dn else n} | {f19['mean']:+.2f} / {x19['mean']:+.2f} / {f19['good']:+.2f} / {x19['good']:+.2f} | {f19['worst']:+.2f} | {caldd:.1f} | {w8} / {wx} | {f38['mean']:+.2f} / {x38['mean']:+.2f} / {f38['good']:+.2f} | {do8:+.2f} / {dn8:+.2f} | {dox:+.2f} / {dnx:+.2f} | {f19['fills']} | {','.join(fail) if n != dn else '-'} |")
    p(''); p(f'halts in any cell: {sum(v["halts"] for v in R.values())}')
    p('passers: ' + (', '.join(f'{n} (min d {m:+.2f})' for m, n in sorted(passers, reverse=True)) if passers else 'none'))
    txt = '\n'.join(L); print(txt)
    if a.md: a.md.write_text(txt+'\n')


if __name__ == '__main__':
    main()
