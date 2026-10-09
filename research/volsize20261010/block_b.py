"""Block B (replication): bitbankgo forecast-quality Binance-majors archive + its deployed-recipe walk-forward
scores (fq-out/B/base_D.npz, refit 28 d from day 90) -> panel.npz / scores.npz for make_fixture.py and candles.
usage: python3 -I block_b.py <archive-dir> <base_D.npz> <out-dir>"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
arch, sc, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]); out.mkdir(parents=True, exist_ok=True)
pairs = sorted(json.loads((arch/'manifest.json').read_text())['files'])
fr = [pd.read_csv(arch/f'{p}.csv') for p in pairs]
ts = pd.to_datetime(fr[0].timestamp, utc=True); assert all(f.timestamp.equals(fr[0].timestamp) for f in fr)
H = (ts.astype('int64')//3_600_000_000_000).to_numpy(); assert np.all(np.diff(H) == 1)
D = np.stack([f[['open', 'high', 'low', 'close', 'quote_volume']].to_numpy(float) for f in fr], axis=1)
S = np.load(sc)['scores']; starts = np.arange(360, len(D)-23, 24); assert len(starts) == len(S) and H[starts[0]] % 24 == 0
begin, refit = 90, 28
blk = np.array([starts[begin+refit*((k-begin)//refit)] if k >= begin else starts[begin] for k in range(len(S))])
names = [p[:-4] for p in pairs]
np.savez(out/'panel.npz', hours=H, data=D, pairs=np.array(names), filled=np.zeros(D.shape[:2], bool))
np.savez(out/'scores.npz', issued=H[starts], raw=S, model=H[blk]-1, pairs=np.array(names))
print(len(H), len(S), names)
