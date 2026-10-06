"""Fleet goodness (dashboard-finance research/goodness/goodness.py) per arm/fee plus paired per-fold tables.

usage: summarize.py <rp-root> <arm> [<arm> ...] [--from DATE] [--md out.md]
Writes <rp-root>/<arm>/curves_fee<fee>.csv (fold,ts,equity; fold = fold start date) for the goodness CLI."""
import argparse, importlib.util, json, math
from pathlib import Path
import numpy as np, pandas as pd

spec = importlib.util.spec_from_file_location('goodness', Path.home()/'code/dashboard-finance/research/goodness/goodness.py')
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)


def load(root, arm, fee, since=None):
    d = root/arm; c = pd.read_csv(d/'curves.csv'); res = [json.loads(l) for l in open(d/'results.jsonl')]
    c = c[np.isclose(c.fee, fee)].copy(); starts = {r['Fold']: r['Start'] for r in res if np.isclose(r['Fee'], fee)}
    c['fold'] = c.fold.map(lambda k: str(pd.Timestamp(starts[k]-3600, unit='s').date()))
    if since: c = c[c.fold >= since]
    out = d/f'curves_fee{fee}.csv'
    if not since: c[['fold', 'ts', 'equity']].to_csv(out, index=False)
    halts = {str(pd.Timestamp(r['Start']-3600, unit='s').date()): r['Halted'] for r in res if np.isclose(r['Fee'], fee)}
    return c[['fold', 'ts', 'equity']], halts


def score(c):
    r = G.score_frame(c); return r['aggregate'], r['folds']


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('arms', nargs='+')
    ap.add_argument('--from', dest='since'); ap.add_argument('--fees', default='0.003,0.004'); a = ap.parse_args()
    fees = [float(f) for f in a.fees.split(',')]
    for fee in fees:
        aggs, folds, halts = {}, {}, {}
        for arm in a.arms:
            c, h = load(a.root, arm, fee, a.since); aggs[arm], folds[arm] = score(c); halts[arm] = h
        common = sorted(set.intersection(*[set(f) for f in folds.values()]))
        print(f'\n### fee {fee*1e4:.0f} bps (+5 bps proxy half-spread), folds from {common[0]} ({len(common)} common folds)\n')
        print('| arm | goodness | status | mean ret % | median | worst | pos | mean mlog | max cal-month DD | max marked DD | mean fold score | worst fold score | halts |')
        print('|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for arm in a.arms:
            sub = {k: folds[arm][k] for k in common}; ag = G.aggregate(sub); r = np.array([f['return_pct'] for f in sub.values()])
            nh = sum(1 for k in common if halts[arm].get(k))
            sc = ag['score'] if ag['status'] == 'PASS' else ag.get('score_unbounded', float('nan'))
            print(f"| {arm} | {sc:+.2f} | {ag['status']} | {r.mean():+.2f} | {np.median(r):+.2f} | {r.min():+.2f} | {(r>0).sum()}/{len(r)} | {ag['mean_monthly_log_growth']:+.2f} | {ag['max_calendar_month_dd']:.1f} | {ag['max_marked_dd']:.1f} | {ag['mean_fold_score']:+.2f} | {ag['worst_fold_score']:+.2f} | {nh} |")
        base = a.arms[0]
        if len(a.arms) > 1:
            print(f'\npaired vs {base}: wins = folds with higher return; d = mean return diff (pp); dscore = mean fold-score diff\n')
            for arm in a.arms[1:]:
                d = np.array([folds[arm][k]['return_pct']-folds[base][k]['return_pct'] for k in common])
                ds = np.array([folds[arm][k]['score']-folds[base][k]['score'] for k in common])
                se = d.std(ddof=1)/math.sqrt(len(d)) if len(d) > 1 else float('nan')
                print(f'- {arm}: wins {(d>0).sum()}/{len(d)}, d {d.mean():+.2f} pp (se {se:.2f}, t {d.mean()/se if se else float("nan"):+.2f}), dscore {ds.mean():+.2f}')
        print('\n| fold | ' + ' | '.join(f'{arm} ret/calDD' for arm in a.arms) + ' |')
        print('|---|' + '---|'*len(a.arms))
        for k in common:
            print(f'| {k} | ' + ' | '.join(f"{folds[arm][k]['return_pct']:+.2f}/{folds[arm][k]['calendar_month_dd']:.1f}{'H' if halts[arm].get(k) else ''}" for arm in a.arms) + ' |')


if __name__ == '__main__':
    main()
