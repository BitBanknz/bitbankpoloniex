"""Summarise the 2026-10-10 vol-sizing k-fold, paired vs the incumbent on the same book seed and folds.
usage: evaluate.py <rp-root> [--md out.md] [--arms a,b] [--parity <fidelity rp-root>]"""
import argparse, filecmp, importlib.util, json, sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).parent)); import grid

spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
FEES = (0.0014, 0.0033)


def load(d, fee):
    c = pd.read_csv(d/'curves.csv'); res = [json.loads(l) for l in open(d/'results.jsonl')]
    c = c[np.isclose(c.fee, fee)].copy(); res = [r for r in res if np.isclose(r['Fee'], fee)]; starts = {r['Fold']: r['Start'] for r in res}
    c['fold'] = c.fold.map(lambda k: str(pd.Timestamp(starts[k]-3600, unit='s').date()))
    r = G.score_frame(c[['fold', 'ts', 'equity']], 35.0); ag = r['aggregate']; f = r['folds']
    keys = sorted(f); ret = np.array([f[k]['return_pct'] for k in keys])
    sc = ag['score'] if ag['status'] == 'PASS' else ag.get('score_unbounded', float('nan'))
    return dict(keys=keys, ret=ret, mean=ret.mean(), worst=ret.min(), good=sc, caldd=ag['max_calendar_month_dd'], status=ag['status'],
                fills=sum(x['Report']['Fills'] for x in res), halts=sum(1 for x in res if x['Halted']))


def tstat(d): return d.mean()/(d.std(ddof=1)/np.sqrt(len(d))) if d.std() > 0 else 0.


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('--md', type=Path); ap.add_argument('--arms'); ap.add_argument('--parity', type=Path); ap.add_argument('--block-b', type=Path); ap.add_argument('--fees', default='0.0014,0.0033')
    a = ap.parse_args(); global FEES; FEES = tuple(float(x) for x in a.fees.split(',')); arms = a.arms.split(',') if a.arms else list(grid.ARMS)
    L = []; p = L.append
    if a.parity:
        ok = [filecmp.cmp(a.root/f'inc_b{s}{u}/curves.csv', a.parity/f's3_h72_c120_r0.4_safe_b{s}{u}/curves.csv', shallow=False) for u in grid.UNIV for s in grid.SEEDS]
        p(f'Parity: inc curves.csv byte-identical to the 10-09 fidelity safeguard runs in {sum(ok)}/{len(ok)} seed x universe cells.\n')
    data = {(n, u, fee): [load(a.root/f'{n}_b{s}{u}', fee) for s in grid.SEEDS] for n in arms for u in grid.UNIV for fee in FEES}
    p('Means over book seeds 1-3; 42 e2306 folds; archived books; paired = same seed and fold vs inc (t over 126 fold-seeds; wins /126).\n')
    for fee in FEES:
        p(f'\n### fee {fee*1e4:.0f} bps + book spread\n')
        p('| arm | 8p mean | worst | goodness | cal DD | d vs inc (t) / wins | 1st half d (t) | 2nd half d (t) | xZEC mean | worst | goodness | cal DD | d (t) / wins | 1st half d | 2nd half d | fills 8p |')
        p('|' + '---|'*16)
        for n in arms:
            row = [n]
            for u in grid.UNIV:
                rs = data[(n, u, fee)]; bs = data[('inc', u, fee)]
                m = {k: float(np.mean([r[k] for r in rs])) for k in ('mean', 'worst', 'good', 'caldd', 'fills')}
                D = np.array([r['ret']-b['ret'] for r, b in zip(rs, bs)]); h = D.shape[1]//2
                d, d1, d2 = D.ravel(), D[:, :h].ravel(), D[:, h:].ravel()
                row += [f"{m['mean']:+.2f}", f"{m['worst']:.2f}", f"{m['good']:.2f}", f"{m['caldd']:.1f}", f"{d.mean():+.2f} ({tstat(d):+.1f}) / {(d > 0).sum()}",
                        f"{d1.mean():+.2f} ({tstat(d1):+.1f})", f"{d2.mean():+.2f} ({tstat(d2):+.1f})"]
                if u == '': fills = m['fills']
            row.append(f'{fills:.0f}')
            p('| ' + ' | '.join(row) + ' |')
    p('\n### Per-fold attribution, 8 pairs, 14 bps (seed-mean %; top-5 incumbent folds and worst-5)\n')
    keys = data[('inc', '', 0.0014)][0]['keys']; inc = np.mean([r['ret'] for r in data[('inc', '', 0.0014)]], axis=0)
    order = list(np.argsort(-inc)[:5]) + list(np.argsort(inc)[:5]) if len(inc) > 20 else list(range(len(inc)))
    p('| fold | inc | ' + ' | '.join(arms[1:]) + ' |'); p('|' + '---|'*(len(arms)+1))
    for i in order:
        p(f'| {keys[i]} | {inc[i]:+.2f} | ' + ' | '.join(f"{np.mean([r['ret'][i] for r in data[(n, '', 0.0014)]]):+.2f}" for n in arms[1:]) + ' |')
    if a.block_b:
        for fee in FEES:
            p(f'\n### Block B (Binance majors, 49 folds 2022-04..2025-12, proxy books), fee {fee*1e4:.0f} bps + 5 bps half-spread\n')
            p('| arm | mean | worst | goodness | cal DD | d vs inc (t) / wins |'); p('|---|---|---|---|---|---|')
            b = load(a.block_b/'inc_b0', fee)
            for n in arms:
                if not (a.block_b/f'{n}_b0/results.jsonl').exists(): continue
                r = load(a.block_b/f'{n}_b0', fee); d = r['ret']-b['ret']
                p(f"| {n} | {r['mean']:+.2f} | {r['worst']:.2f} | {r['good']:.2f} | {r['caldd']:.1f} | {d.mean():+.2f} ({tstat(d):+.1f}) / {(d > 0).sum()} |")
    txt = '\n'.join(L); print(txt)
    if a.md: a.md.write_text(txt + '\n')


if __name__ == '__main__':
    main()
