import json, sys, numpy as np, pandas as pd
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]; D = ROOT/'data/ranker'
PAIRS = ['BNB','ETC','ETH','PEPE','SUI','TRX','XRP','ZEC']
raw = json.load(open(D/'prod_ohlcv.json')); rs = json.load(open(D/'prod_raw_scores.json'))
ohlcv = {p: {int(h): v for h, v in raw[p].items()} for p in PAIRS}
days = sorted(int(h) for h in rs)
base = json.load(open(ROOT/'data/frontier_20260912/ledger/fixture.json'))
last_hour = min(max(ohlcv[p]) for p in PAIRS)
for a in (0.35, 0.25):
    ranks, ema = {}, None
    for h in days:
        r = np.array(rs[str(h)]); ema = r if ema is None else a * r + (1 - a) * ema
        ranks[str(h * 3600)] = [float(v) for v in ema]
    hours = []
    for t in range(days[0] + 1, last_hour + 1):
        hours.append(dict(TS=t * 3600, Open=[ohlcv[p][t][0] for p in PAIRS], PriorTurnover=[ohlcv[p][t - 1][4] for p in PAIRS],
                          Volume24=[sum(ohlcv[p][u][4] for u in range(t - 24, t)) for p in PAIRS]))
    g = dict(Pairs=[p + 'USDT' for p in PAIRS], Hours=hours, Ranks=ranks, archive_manifest_sha256=None, scores_sha256=None,
             limitations='OOS 2026-09-10.. rebuilt from public candles and the production bundle models; hourly-open proxy books as in the main fixture.')
    json.dump(g, open(D/f'fixture_oos_ema{int(a*100):03d}.json', 'w'))
    print('ema', a, 'days', len(days), 'hours', len(hours), pd.Timestamp(hours[0]['TS'], unit='s'), pd.Timestamp(hours[-1]['TS'], unit='s'))
if True:
    s = [json.loads(l) for l in open(ROOT/'data/forward/scores.jsonl')][-1]
    g = json.load(open(D/'fixture_oos_ema035.json')); k = str(s['issued_hour'] * 3600)
    print('final-day check vs remote smoothed: max err', np.abs(np.array(g['Ranks'][k]) - np.array(s['smoothed_scores'])).max())
