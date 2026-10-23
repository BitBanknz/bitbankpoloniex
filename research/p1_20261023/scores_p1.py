"""P1 2026-10-23 refit-cadence / refit-phase arms of the production lambdarank recipe (fit_refresh, unchanged).
Grid = ANCHOR + phase_days*24 + period_days*24*k (ANCHOR = production valid_from 2026-09-23 00:00 UTC); each refit trains on the
expanding panel from --start to valid_from-1 (exclusive), exactly as longkfold20261007/scores.py, and issues daily 00:00 scores
for [valid_from, valid_from+period). --period-days 28 --phase-days 0 reproduces e2306.npz exactly.
usage: scores_p1.py --panel P --out O.npz [--period-days 28] [--phase-days 0] [--start 2023-06-01] [--jobs 8]
       scores_p1.py --bag O.npz A.npz B.npz ...   (mean of per-day cross-sectional z-scores over the phases that cover each day)"""
import argparse, hashlib, json, os, sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'longkfold20261007'))
from scores import ANCHOR, fit_refresh, features_at, rank_features  # noqa: E402

D = H = None


def init(panel):
    global D, H
    z = np.load(panel); H, D = z['hours'], z['data']


def one(args):
    V, start_h, period, last_issue = args
    H0 = int(H[0]); lo = max(start_h, H0); lo += (-lo) % 24
    sl = slice(lo-H0, V-1-H0); data, hours = D[sl], H[sl]
    try: model, x, rec = fit_refresh(data, hours, V)
    except ValueError as e:
        if 'insufficient' in str(e): return None
        raise
    rec.update(valid_from=int(V), data_first_hour=int(hours[0]), data_last_hour=int(hours[-1]), training_data_sha256=hashlib.sha256(data.tobytes()).hexdigest())
    days = np.arange(V, min(V+period, last_issue+1), 24); idx = days-H0
    f, _ = features_at(D, idx); x = np.concatenate([f, rank_features(f)], axis=-1)
    return days, np.asarray(model.predict(x), float), rec


def bag(out, ins):
    zs = {}
    for p in ins:
        s = np.load(p)
        for d, r in zip(s['issued'], s['raw']): zs.setdefault(int(d), []).append((r-r.mean())/max(r.std(), 1e-6))
        pairs = s['pairs']
    days = np.array(sorted(zs)); raw = np.stack([np.mean(zs[d], axis=0) for d in days]); n = np.array([len(zs[d]) for d in days])
    np.savez_compressed(out, issued=days, raw=raw, model=n, pairs=pairs)
    print(json.dumps(dict(out=str(out), days=len(days), phases_min=int(n.min()), first_full=int(days[n == len(ins)][0]))))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--panel', type=Path); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start', default='2023-06-01'); ap.add_argument('--period-days', type=int, default=28); ap.add_argument('--phase-days', type=int, default=0)
    ap.add_argument('--jobs', type=int, default=8); ap.add_argument('--bag', nargs='+', type=Path)
    a = ap.parse_args()
    if a.bag: return bag(a.out, a.bag)
    init(a.panel); H0 = int(H[0]); last_issue = int(H[-1])+1; period = a.period_days*24
    start_h = int(pd.Timestamp(a.start, tz='UTC').value//3600_000_000_000)
    base = ANCHOR+a.phase_days*24; grid = base+period*np.arange(-60*28//a.period_days-2, 3*28//a.period_days+2)
    grid = grid[(grid > H0+400) & (grid <= last_issue)]
    os.environ.setdefault('OMP_NUM_THREADS', '2')
    with ProcessPoolExecutor(a.jobs, initializer=init, initargs=(a.panel,)) as ex:
        res = list(ex.map(one, [(int(V), start_h, period, last_issue) for V in grid]))
    res = [r for r in res if r is not None]
    issued = np.concatenate([r[0] for r in res]); raw = np.concatenate([r[1] for r in res]); model = np.concatenate([np.full(len(r[0]), r[2]['valid_from']) for r in res])
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, issued=issued, raw=raw, model=model, pairs=np.load(a.panel)['pairs'])
    a.out.with_suffix('.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, refits=[r[2] for r in res]), indent=1))
    print(json.dumps(dict(out=str(a.out), refits=len(res), days=len(issued), first=str(pd.Timestamp(int(issued[0])*3600, unit='s')))))


if __name__ == '__main__':
    main()
