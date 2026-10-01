import json, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[2]
ARC = ROOT/'data/archive-hourly'
OUT = ROOT/'data/ranker'; OUT.mkdir(exist_ok=True)
LIVE = ['BNB','ETC','ETH','PEPE','SUI','TRX','XRP','ZEC']
cols = {}
for d in sorted(ARC.iterdir()):
    p = d/'candles.csv'
    if not p.exists() or not d.name.endswith('_USDT'): continue
    df = pd.read_csv(p, parse_dates=['timestamp']).drop_duplicates('timestamp').set_index('timestamp')
    df = df[df.index >= '2019-01-01']
    if len(df) < 24*200: continue
    cols[d.name[:-5]] = df
idx = pd.date_range(pd.Timestamp('2019-01-01', tz='UTC'), max(c.index.max() for c in cols.values()), freq='h')
def mat(k): return pd.DataFrame({n: c[k].reindex(idx).values for n, c in cols.items()}, index=idx)
o, h, l, c, v = (mat(k) for k in ('open', 'high', 'low', 'close', 'quote_volume'))
for k, m in zip(('open', 'high', 'low', 'close', 'qv'), (o, h, l, c, v)): m.to_parquet(OUT/f'{k}.parquet')
print(len(cols), 'markets', idx[0], idx[-1], [n for n in LIVE if n not in cols])
