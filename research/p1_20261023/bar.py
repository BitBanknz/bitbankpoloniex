"""P1 registered bar extras: per-seed fold means vs inc, fold-clustered paired t (seed-mean per fold), recent folds (>= 2025-10-22),
worst of the seed-mean fold returns. Fold returns from evaluate.py (goodness score_frame, same as earlier rounds).
usage: bar.py <rp-root> --arms a b ... [--seeds 1..6]"""
import argparse, importlib.util
from pathlib import Path
import numpy as np

spec = importlib.util.spec_from_file_location('ev', Path(__file__).resolve().parents[1]/'hourly20261013/evaluate.py')
E = importlib.util.module_from_spec(spec); spec.loader.exec_module(E)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('root', type=Path); ap.add_argument('--base', default='inc'); ap.add_argument('--arms', nargs='+', required=True)
    ap.add_argument('--seeds', nargs='+', type=int, default=[1, 2, 3, 4, 5, 6]); ap.add_argument('--recent', default='2025-10-22'); a = ap.parse_args()
    print('| arm | univ | fee | seed-mean fold mean | d | clustered t | per-seed wins vs inc | worst seed-mean fold (inc) | recent d |')
    print('|---|---|---|---|---|---|---|---|---|')
    for u in ('', '_xzec'):
        for fee in (0.0014, 0.0033):
            B = [E.load(a.root/f'{a.base}_b{s}{u}', fee) for s in a.seeds]; keys = np.array(B[0]['keys'])
            bm = np.mean([b['ret'] for b in B], axis=0)
            for arm in a.arms:
                try: A = [E.load(a.root/f'{arm}_b{s}{u}', fee) for s in a.seeds]
                except FileNotFoundError: continue
                assert all(r['keys'] == list(keys) for r in A)
                am = np.mean([r['ret'] for r in A], axis=0); d = am-bm; t = d.mean()/(d.std(ddof=1)/np.sqrt(len(d)))
                ps = sum(r['ret'].mean() > b['ret'].mean() for r, b in zip(A, B)); rec = keys >= a.recent
                print(f"| {arm} | {u or '8p'} | {fee*1e4:.0f} | {am.mean():+.2f} (inc {bm.mean():+.2f}) | {d.mean():+.2f} | {t:+.2f} | {ps}/{len(A)} | {am.min():.2f} ({bm.min():.2f}) | {d[rec].mean():+.2f} |")


if __name__ == '__main__':
    main()
