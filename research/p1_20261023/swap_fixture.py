"""Fixture for a score arm on the incumbent's exact hours/folds: copy <base fixture> and replace Ranks by the continuous
EMA(alpha) of the arm's raw daily scores, started on the base's first rank day (as make_fixture.py: ema[0] = raw[0]).
Pairs missing from the base (ex-ZEC) are dropped after smoothing. --check: rebuilding the base from its own npz must be exact.
usage: swap_fixture.py --base fx.json --scores arm.npz --out out.json [--alpha .35]"""
import argparse, json
from pathlib import Path
import numpy as np


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--base', type=Path, required=True); ap.add_argument('--scores', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True); ap.add_argument('--alpha', type=float, default=.35); a = ap.parse_args()
    f = json.loads(a.base.read_text()); s = np.load(a.scores); issued, raw = s['issued'], s['raw']; pairs = [p+'USDT' for p in s['pairs']]
    keep = [pairs.index(p) for p in f['Pairs']]; first = min(int(k)//3600 for k in f['Ranks'])
    m = issued >= first; issued, raw = issued[m], raw[m]
    assert issued[0] == first and np.all(np.diff(issued) == 24), 'arm must cover every base rank day'
    ema = raw.copy()
    for i in range(1, len(ema)): ema[i] = a.alpha*raw[i]+(1-a.alpha)*ema[i-1]
    ranks = {str(int(h*3600)): ema[k, keep].tolist() for k, h in enumerate(issued)}
    assert set(f['Ranks']) <= set(ranks), 'arm missing base rank days'
    f['Ranks'] = {k: ranks[k] for k in f['Ranks']} if set(ranks) != set(f['Ranks']) else ranks
    a.out.parent.mkdir(parents=True, exist_ok=True); a.out.write_text(json.dumps(f, separators=(',', ':')))
    print(json.dumps(dict(out=str(a.out), days=len(f['Ranks']), pairs=len(keep))))


if __name__ == '__main__':
    main()
