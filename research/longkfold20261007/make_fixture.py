"""Go replay fixture for one score arm: hourly proxy books from the panel, EMA-smoothed daily
ranks (continuous EMA as rotation_forecast.issue), and folds = the arm's 28-day refit blocks."""
import argparse, json
from pathlib import Path
import numpy as np, pandas as pd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--scores', type=Path, required=True); ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--alpha', type=float, default=.35); ap.add_argument('--drop', nargs='*', default=[]); ap.add_argument('--from-date', default=None)
    a = ap.parse_args()
    z = np.load(a.panel); H, D, pairs = z['hours'], z['data'], list(z['pairs'])
    s = np.load(a.scores); issued, raw, model = s['issued'], s['raw'], s['model']
    assert np.all(np.diff(issued) == 24) and list(s['pairs']) == pairs
    ema = raw.copy()
    for i in range(1, len(ema)): ema[i] = a.alpha*raw[i]+(1-a.alpha)*ema[i-1]
    keep = [j for j, p in enumerate(pairs) if p not in a.drop]
    H0 = int(H[0]); blocks = sorted(set(model.tolist()))
    if a.from_date: blocks = [v for v in blocks if v >= pd.Timestamp(a.from_date, tz='UTC').value//3600_000_000_000]
    first, last = blocks[0]+1, int(H[-1])
    hrs = np.arange(first, last+1); idx = hrs-H0
    vol = D[:, :, 4]; c24 = np.cumsum(np.vstack([np.zeros((1, vol.shape[1])), vol]), axis=0)
    hours = [dict(TS=int(h*3600), Open=D[i, keep, 0].tolist(), PriorTurnover=vol[i-1, keep].tolist(), Volume24=(c24[i, keep]-c24[i-24, keep]).tolist()) for h, i in zip(hrs, idx)]
    folds = []
    for v in blocks:
        a0 = v+1-first; b0 = min(v+28*24+1-first, len(hrs))
        if b0-a0 >= 7*24: folds.append([int(a0), int(b0)])
    ranks = {str(int(h*3600)): ema[k, keep].tolist() for k, h in enumerate(issued) if h >= blocks[0]}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(dict(Pairs=[pairs[j]+'USDT' for j in keep], Hours=hours, Ranks=ranks, Folds=folds), separators=(',', ':')))
    print(json.dumps(dict(out=str(a.out), hours=len(hours), folds=len(folds), first=str(pd.Timestamp(first*3600, unit='s')), last=str(pd.Timestamp(last*3600, unit='s')), pairs=len(keep))))


if __name__ == '__main__':
    main()
