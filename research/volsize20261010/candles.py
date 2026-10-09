"""Hourly OHLC sidecar for the vol-sizing replay's /candles endpoint, from the 10-07 panel (full history, so
the first fold has 168 h of prior bars). usage: python3 -I candles.py <panel.npz> <out.json.gz>"""
import gzip, json, sys
import numpy as np
z = np.load(sys.argv[1]); H, D = z['hours'], z['data']
assert np.all(np.diff(H) == 1)
out = dict(TS0=int(H[0])*3600, Pairs=[p+'USDT' for p in z['pairs']], OHLC=np.round(D[:, :, :4], 12).tolist())
with gzip.open(sys.argv[2], 'wt') as f: json.dump(out, f, separators=(',', ':'))
print(len(H), out['Pairs'])
