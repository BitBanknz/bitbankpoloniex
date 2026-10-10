"""Paired gates on seed-mean equity curves, using poloniexmojo/research/study.py metrics/aggregate/compare.
usage: python3 -I evaluate.py --rp DIR --stage dev --arms a b ... [--suffix _xzec] [--fold-offset 30] --out out.json"""
import argparse, csv, hashlib, importlib.util, json
from pathlib import Path

STUDY = Path('/vfast/data/code/poloniexmojo/research/study.py')
STUDY_SHA = '3a64a76bec296e99aba0638897f8322c876ba8104c6566a61dbb9494040487bb'
SEEDS = (1, 2, 3)


def load_study():
    assert hashlib.sha256(STUDY.read_bytes()).hexdigest() == STUDY_SHA
    spec = importlib.util.spec_from_file_location('study', STUDY); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


def seed_mean(paths):
    per = []
    for p in paths:
        g = {}
        with open(p) as fh:
            for r in csv.DictReader(fh):
                g.setdefault((float(r['fee']), int(r['fold'])), []).append((int(r['ts']), float(r['equity'])))
        per.append(g)
    assert all(set(g) == set(per[0]) for g in per)
    out = {}
    for k in per[0]:
        ts = [t for t, _ in per[0][k]]
        assert all([t for t, _ in g[k]] == ts for g in per), k
        out[k] = [(t, sum(g[k][i][1] for g in per)/len(per)) for i, t in enumerate(ts)]
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--rp', type=Path, required=True); ap.add_argument('--stage', required=True)
    ap.add_argument('--arms', nargs='+', required=True); ap.add_argument('--suffix', default=''); ap.add_argument('--fold-offset', type=int, default=0)
    ap.add_argument('--base', default='incumbent'); ap.add_argument('--out', type=Path, required=True); a = ap.parse_args()
    st = load_study(); res = {}
    curves = {arm: seed_mean([a.rp/a.stage/f'{arm}_b{s}{a.suffix}'/'curves.csv' for s in SEEDS]) for arm in [a.base, *a.arms]}
    for fee in sorted({k[0] for k in curves[a.base]}):
        m = {arm: {k[1]+a.fold_offset: st.metrics(v) for k, v in c.items() if k[0] == fee} for arm, c in curves.items()}
        res[str(fee)] = {arm: {kk: vv for kk, vv in st.compare(m[a.base], m[arm]).items()} for arm in a.arms}
        res[str(fee)]['_folds'] = {arm: {f: round(r['return_pct'], 4) for f, r in m[arm].items()} for arm in m}
    a.out.write_text(json.dumps(res, indent=1, default=float))
    for fee, r in res.items():
        b = next(iter(v for k, v in r.items() if k != '_folds'))['baseline']
        print(f"fee={fee} base mean={b['mean_return_pct']:.3f} med={b['median_return_pct']:.3f} worst={b['worst_return_pct']:.3f} sortino={b['daily_sortino']:.3f} calDD={b['max_calendar_month_dd']:.2f} r30DD={b['max_rolling_30d_dd']:.2f}")
        for arm in a.arms:
            c = r[arm]; x = c['candidate']
            print(f"  {arm}: pass={c['pass_gate']} mean={x['mean_return_pct']:.3f} med={x['median_return_pct']:.3f} worst={x['worst_return_pct']:.3f} sortino={x['daily_sortino'] if x['daily_sortino'] is None else round(x['daily_sortino'],3)} calDD={x['max_calendar_month_dd']:.2f} r30DD={x['max_rolling_30d_dd']:.2f} wins={c['paired_wins']}/{c['paired_folds']} d={c['paired_mean_delta_pct']:.3f}±{c['paired_standard_error']:.3f} {','.join(c['reasons'])}")


if __name__ == '__main__':
    main()
