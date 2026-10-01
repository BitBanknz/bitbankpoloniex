"""Rebuild production daily raw/EMA scores from public candles and the two bundle models; validate against the remote's current state."""
import json, numpy as np, pandas as pd
from pathlib import Path
from poloniex_rank_models import RankModel, features_at, rank_features
ROOT = Path(__file__).resolve().parents[2]; D = ROOT/'data/ranker'
PAIRS = ['BNB','ETC','ETH','PEPE','SUI','TRX','XRP','ZEC']
raw = json.load(open(D/'prod_ohlcv.json'))
hours = sorted(set.intersection(*[set(map(int, raw[p])) for p in PAIRS]))
assert hours == list(range(hours[0], hours[-1] + 1)), 'gap in candles'
arr = np.array([[raw[p][str(h)] for p in PAIRS] for h in hours])
H0 = hours[0]
m1 = RankModel.load(D/'prodmodels/model.json'); m2 = RankModel.load(D/'prodmodels/model-497256-45213acd13a6.json')
last = [json.loads(l) for l in open(ROOT/'data/forward/scores.jsonl')][-1]
obs, issued_last = last['observations'], last['issued_hour']
def scores(issued, switch):
    i = issued - H0
    window = arr[i - 337:i]
    x, _ = features_at(window, [337])
    feats = np.concatenate([x, rank_features(x)], axis=-1)
    return np.asarray((m2 if issued >= switch else m1).predict(feats)[0], dtype=float)
first = issued_last - 24 * (obs - 1)
print('remote observations', obs, 'first issued day', pd.Timestamp(first * 3600, unit='s'), 'last', pd.Timestamp(issued_last * 3600, unit='s'), 'candle hours', pd.Timestamp(H0*3600, unit='s'), pd.Timestamp(hours[-1]*3600, unit='s'))
best = None
for switch in range(497256 - 24 * 3, 497256 + 24 * 4, 24):
    ema, rawsc = None, {}
    for h in range(first, issued_last + 1, 24):
        r = scores(h, switch); rawsc[h] = r
        ema = r if ema is None else .35 * r + .65 * ema
    err = np.abs(ema - np.array(last['smoothed_scores'])).max(); errraw = np.abs(rawsc[issued_last] - np.array(last['raw_scores'])).max()
    print('switch', switch, 'max|ema err| %.2e  max|raw err| %.2e' % (err, errraw))
    if best is None or err < best[0]: best = (err, switch, rawsc)
print('best switch', best[1], 'err %.2e' % best[0])
json.dump({str(h): list(map(float, v)) for h, v in best[2].items()}, open(D/'prod_raw_scores.json', 'w'))
