"""Causal daily raw rank scores from the production refit recipe (rotation_refresh.fit_refresh).

Refit grid is phase-locked to production (valid_from 2026-09-23 00:00 UTC, 28-day
validity); at each refit the training data is the panel from the arm's start to the
refresh hour (valid_from-1, exclusive), exactly what load_extended hands fit_refresh.
Daily issuance at 00:00 UTC from the 337 completed hours before it, as rotation_forecast.issue."""
import argparse, hashlib, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, os.environ.get('BITBANKGO_SCRIPTS', '/vfast/data/code/bitbankgo/scripts'))
from rotation_refresh import fit_refresh  # noqa: E402
from poloniex_rank_models import RankModel, features_at, rank_features  # noqa: E402

ANCHOR, PERIOD = 497256, 28 * 24
PARAMS = dict(n_estimators=70, num_leaves=5, max_depth=2, reg_lambda=20)


def targets(data, starts):
    out = []
    for i in starts:
        path = data[i:i+72, :, 3]/data[i, :, 0]
        peak = np.maximum.accumulate(np.vstack([np.ones((1, data.shape[1])), path]), axis=0)[1:]
        out.append(path[-1]-1-.005-.5*(1-path/peak).max(axis=0))
    return np.asarray(out)


class Bag:
    """M lgbm_rank members, row/column subsample 0.8, mean of per-day standardised predictions."""
    def __init__(self, members, seed=20261007):
        self.members, self.seed = members, seed

    def fit(self, data, hours, valid_from):
        import lightgbm as lgb
        starts = np.arange(360, len(data)-71, 24); starts = starts[hours[starts] <= valid_from-5*24]
        if len(starts) < 40: raise ValueError('insufficient or noncontiguous training data')
        raw, _ = features_at(data, starts); x = np.concatenate([raw, rank_features(raw)], axis=-1); y = targets(data, starts)
        self.mean = x.mean(axis=(0, 1)); self.scale = np.maximum(x.std(axis=(0, 1)), 1e-6)
        z = np.clip((x-self.mean)/self.scale, -10, 10).astype('float32')
        labels = np.stack([pd.Series(v).rank(method='average').to_numpy()-1 for v in y]).astype(int)
        self.models = []
        for m in range(self.members):
            s = dict(objective='lambdarank', n_estimators=70, num_leaves=5, max_depth=2, min_child_samples=24, learning_rate=.03,
                     reg_lambda=20, reg_alpha=1, random_state=self.seed+7919*m, n_jobs=2, verbosity=-1, deterministic=True, force_col_wise=True,
                     subsample=.8, subsample_freq=1, colsample_bytree=.8)
            self.models.append(lgb.LGBMRanker(**s).fit(z.reshape(-1, z.shape[-1]), labels.ravel(), group=[z.shape[1]]*len(z)))
        return self, x, dict(train_last_origin_hour=int(hours[starts[-1]]), training_origins=len(starts))

    def predict(self, x):
        z = np.clip((x-self.mean)/self.scale, -10, 10).astype('float32')
        ps = []
        for mdl in self.models:
            p = mdl.booster_.predict(z.reshape(-1, z.shape[-1]), num_threads=2).reshape(z.shape[:2])
            ps.append((p-p.mean(axis=1, keepdims=True))/np.maximum(p.std(axis=1, keepdims=True), 1e-6))
        p = np.mean(ps, axis=0)
        return (p-p.mean(axis=1, keepdims=True))/np.maximum(p.std(axis=1, keepdims=True), 1e-6)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--start', default='2023-06-01', help='expanding-window training start (UTC date)')
    ap.add_argument('--rolling-days', type=int, default=0, help='>0: training data = last N days before the refresh hour')
    ap.add_argument('--bag', type=int, default=0); ap.add_argument('--verify-prod', type=Path, help='production bundle dir to check bit-exactness against')
    a = ap.parse_args()
    z = np.load(a.panel); H, D = z['hours'], z['data']; H0 = int(H[0])
    start_h = int(pd.Timestamp(a.start, tz='UTC').value//3600_000_000_000)
    last_issue = int(H[-1])+1
    grid = ANCHOR + PERIOD*np.arange(-60, 3); grid = grid[(grid > H0+400) & (grid <= last_issue)]
    issued, raw, model_of, receipts = [], [], [], []
    for V in grid:
        lo = max(start_h, H0, V-a.rolling_days*24 if a.rolling_days else H0)
        lo += (-lo) % 24
        sl = slice(lo-H0, V-1-H0); data, hours = D[sl], H[sl]
        try:
            if a.bag: model, x, rec = Bag(a.bag).fit(data, hours, V)
            else: model, x, rec = fit_refresh(data, hours, V)
        except ValueError as e:
            if 'insufficient' in str(e): continue
            raise
        rec.update(valid_from=int(V), data_first_hour=int(hours[0]), data_last_hour=int(hours[-1]), training_data_sha256=hashlib.sha256(data.tobytes()).hexdigest())
        days = np.arange(V, min(V+PERIOD, last_issue+1), 24); idx = days-H0
        f, _ = features_at(D, idx); x = np.concatenate([f, rank_features(f)], axis=-1)
        p = np.asarray(model.predict(x), float)
        if a.verify_prod is not None and V == ANCHOR and not a.bag:
            man = json.loads((a.verify_prod/'manifest.json').read_text()); prod = RankModel.load(a.verify_prod/man['model'])
            rec['prod_check'] = dict(sha_match=rec['training_data_sha256'] == man['training_data_sha256'],
                                     origins_match=rec['training_origins'] == man['training_origins'] and rec['train_last_origin_hour'] == man['train_last_origin_hour'],
                                     max_abs_pred_diff=float(np.abs(prod.predict(x)-p).max()))
            print('prod check', rec['prod_check'], flush=True)
        issued.append(days); raw.append(p); model_of.append(np.full(len(days), V)); receipts.append(rec)
        print('refit', pd.Timestamp(V*3600, unit='s').date(), 'origins', rec['training_origins'], 'days', len(days), flush=True)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, issued=np.concatenate(issued), raw=np.concatenate(raw), model=np.concatenate(model_of), pairs=z['pairs'])
    a.out.with_suffix('.json').write_text(json.dumps(dict(args={k: str(v) for k, v in vars(a).items()}, refits=receipts), indent=1))


if __name__ == '__main__':
    main()
