"""Summarise hourly-cadence k-fold arms vs the daily incumbent.
usage: evaluate.py <rp-root> --base inc --arms a1 a2 ... [--seeds 1 2 3] [--fees 0.0014 0.0033] [--md out.md]
Run dirs: <rp>/<arm>_b<seed>[_xzec]. Metrics per (arm, univ, fee) averaged over book seeds; paired diffs over folds x seeds."""
import argparse, importlib.util, json
from pathlib import Path
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def load(d, fee):
    c = pd.read_csv(d/'curves.csv'); res = [json.loads(l) for l in open(d/'results.jsonl')]
    c = c[np.isclose(c.fee, fee)].copy(); res = [r for r in res if np.isclose(r['Fee'], fee)]
    if not res: return None
    starts = {r['Fold']: r['Start'] for r in res}
    c['fold'] = c.fold.map(lambda k: str(pd.Timestamp(starts[k]-3600, unit='s').date()))
    r = G.score_frame(c[['fold', 'ts', 'equity']], 35.0); ag = r['aggregate']; f = r['folds']
    keys = sorted(f); ret = np.array([f[k]['return_pct'] for k in keys]); mdd = np.array([f[k].get('calendar_month_dd', np.nan) for k in keys])
    sc = ag['score'] if ag['status'] == 'PASS' else ag.get('score_unbounded', float('nan'))
    return dict(keys=keys, ret=ret, mean=ret.mean(), med=float(np.median(ret)), worst=ret.min(), good=sc, caldd=ag['max_calendar_month_dd'],
                fills=sum(x['Report']['Fills'] for x in res), pos=int((ret > 0).sum()))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('--base', default='inc'); ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3]); ap.add_argument('--fees', nargs='+', type=float, default=[0.0014, 0.0033])
    ap.add_argument('--univ', nargs='+', default=['', '_xzec']); ap.add_argument('--md', type=Path); ap.add_argument('--folds', default='', help='lo:hi fold slice'); ap.add_argument('--since', default='', help='only folds starting >= YYYY-MM-DD')
    a = ap.parse_args(); L = []; p = L.append
    sl = slice(*[int(x) if x else None for x in a.folds.split(':')]) if a.folds else slice(None)
    def get(arm, u, fee):
        out = []
        for s in a.seeds:
            d = a.root/f'{arm}_b{s}{u}'
            if not (d/'run.log').exists() or 'PASS' not in (d/'run.log').read_text(): return None
            r = load(d, fee)
            if r is None: return None
            r = dict(r); k = np.array(r['keys']); m = np.zeros(len(k), bool); m[sl] = True; m &= k >= a.since; r['keys'] = list(k[m]); r['ret'] = r['ret'][m]; r['mean'] = r['ret'].mean(); r['worst'] = r['ret'].min(); r['pos'] = int((r['ret'] > 0).sum()); r['med'] = float(np.median(r['ret']))
            out.append(r)
        return out
    p(f"seeds {a.seeds}; folds {a.folds or 'all'}; paired = arm - {a.base}, t over folds x seeds; per-seed mean range\n")
    p('| arm | univ | fee bps | mean %/fold | seed range | median | worst | pos | goodness | max cal-month DD | fills | d vs base (t) | wins |')
    p('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
    for u in a.univ:
        for fee in a.fees:
            base = get(a.base, u, fee)
            for arm in [a.base]+a.arms:
                rs = get(arm, u, fee)
                if rs is None: continue
                m = {k: float(np.mean([r[k] for r in rs])) for k in ('mean', 'med', 'worst', 'good', 'caldd', 'fills', 'pos')}
                dv = ''
                if base is not None and arm != a.base:
                    d = np.concatenate([r['ret'][np.isin(r['keys'], b['keys'])]-b['ret'][np.isin(b['keys'], r['keys'])] for r, b in zip(rs, base)]); t = d.mean()/(d.std(ddof=1)/np.sqrt(len(d))) if d.std() > 0 else 0
                    dv = f"{d.mean():+.2f} ({t:+.1f}) | {(d > 0).sum()}/{len(d)}"
                else: dv = '- | -'
                p(f"| {arm} | {u or '8p'} | {fee*1e4:.0f} | {m['mean']:+.2f} | {min(r['mean'] for r in rs):+.2f}..{max(r['mean'] for r in rs):+.2f} | {m['med']:+.2f} | {m['worst']:.2f} | {m['pos']:.0f} | {m['good']:.2f} | {m['caldd']:.1f} | {m['fills']:.0f} | {dv} |")
    txt = '\n'.join(L); print(txt)
    if a.md: a.md.write_text(txt+'\n')


if __name__ == '__main__':
    main()
