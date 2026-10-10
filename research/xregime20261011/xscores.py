"""Causal daily raw scores: the production refit recipe (longkfold20261007/scores.py grid, fit_refresh model)
with optional Binance features appended before ranking. --control omits them and must reproduce e2306.npz.
usage: python3 -I xscores.py --panel panel.npz --binance binance.npz --out x.npz [--control] [--start 2023-06-01]"""
import argparse, hashlib, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, os.environ.get('BITBANKGO_SCRIPTS', '/vfast/data/code/bitbankgo/scripts'))
from poloniex_rank_models import RankModel, features_at, rank_features  # noqa: E402

ANCHOR, PERIOD = 497256, 28*24


class XFeat:
    def __init__(self, D, H, B):
        self.D, self.H0 = D, int(H[0]); bh = B['hours']; self.B0 = int(bh[0])
        assert np.all(np.diff(bh) == 1) and [str(s) for s in B['syms'][:8]] == ['BNB', 'ETC', 'ETH', 'PEPE', 'SUI', 'TRX', 'XRP', 'ZEC']
        self.c, self.q = B['close'][:, :8], B['qv'][:, :8]

    def at(self, hours):
        out = []
        for h in hours:
            b = h-self.B0; p = h-self.H0
            c, q = self.c[b-336:b], self.q[b-336:b]; pc, pq = self.D[p-168:p, :, 3], self.D[p-168:p, :, 4]
            assert b >= 336 and p >= 168 and np.isfinite(c).all()
            basis = np.log(pc[-24:]/c[-24:])
            share = lambda n: np.log((pq[-n:].sum(axis=0)+1)/(q[-n:].sum(axis=0)+1))
            out.append(np.stack([np.log(c[-1]/c[-25]), np.log(c[-1]/c[-169]), basis[-1], basis.mean(axis=0), share(24)-share(168),
                                 np.log(q[-24:].mean(axis=0)+1)-np.log(q.mean(axis=0)+1)], axis=-1))
        x = np.asarray(out)
        if not np.isfinite(x).all(): raise ValueError('nonfinite binance features')
        return x


def design(D, data_or_full, hours, idx, xf):
    raw, _ = features_at(data_or_full, idx)
    if xf is not None: raw = np.concatenate([raw, xf.at(hours)], axis=-1)
    return np.concatenate([raw, rank_features(raw)], axis=-1)


def fit(D, data, hours, valid_from, xf):
    starts = np.arange(360, len(data)-71, 24); starts = starts[hours[starts] <= valid_from-5*24]
    if len(starts) < 40 or not np.all(np.diff(hours) == 1): raise ValueError('insufficient or noncontiguous training data')
    x = design(D, data, hours[starts], starts, xf); targets = []
    for i in starts:
        path = data[i:i+72, :, 3]/data[i, :, 0]
        peak = np.maximum.accumulate(np.vstack([np.ones((1, data.shape[1])), path]), axis=0)[1:]
        targets.append(path[-1]-1-.005-.5*(1-path/peak).max(axis=0))
    model = RankModel('lgbm_rank', dict(n_estimators=70, num_leaves=5, max_depth=2, reg_lambda=20)).fit(x, np.asarray(targets))
    return model, dict(train_last_origin_hour=int(hours[starts[-1]]), training_origins=len(starts))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--binance', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start', default='2023-06-01'); ap.add_argument('--control', action='store_true'); ap.add_argument('--last-issue', type=int, default=0)
    a = ap.parse_args()
    z = np.load(a.panel); H, D = z['hours'], z['data']; H0 = int(H[0])
    xf = None if a.control else XFeat(D, H, np.load(a.binance))
    start_h = int(pd.Timestamp(a.start, tz='UTC').value//3600_000_000_000)
    last_issue = a.last_issue or int(H[-1])+1
    grid = ANCHOR+PERIOD*np.arange(-60, 3); grid = grid[(grid > H0+400) & (grid <= last_issue)]
    issued, raw, model_of, receipts = [], [], [], []
    for V in grid:
        lo = max(start_h, H0); lo += (-lo) % 24
        sl = slice(lo-H0, V-1-H0); data, hours = D[sl], H[sl]
        try:
            model, rec = fit(D, data, hours, V, xf)
        except ValueError as e:
            if 'insufficient' in str(e): continue
            raise
        rec.update(valid_from=int(V), data_first_hour=int(hours[0]), data_last_hour=int(hours[-1]), training_data_sha256=hashlib.sha256(data.tobytes()).hexdigest())
        days = np.arange(V, min(V+PERIOD, last_issue+1), 24); idx = days-H0
        p = np.asarray(model.predict(design(D, D, days, idx, xf)), float)
        issued.append(days); raw.append(p); model_of.append(np.full(len(days), V)); receipts.append(rec)
        print('refit', pd.Timestamp(V*3600, unit='s').date(), 'origins', rec['training_origins'], 'days', len(days), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, issued=np.concatenate(issued), raw=np.concatenate(raw), model=np.concatenate(model_of), pairs=z['pairs'])
    a.out.with_suffix('.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, refits=receipts), indent=1))


if __name__ == '__main__':
    main()
