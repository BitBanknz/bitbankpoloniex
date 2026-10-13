"""Wide hourly panel on the longkfold20261007 grid (2023-06-01 .. 2026-10-06 21:00) for universe extension.
Existing 8 pairs are copied from the 8-pair panel; others are fetched from Poloniex public candles. Hours with no
venue candle are NaN (pre-listing) or flagged gaps (inside history). usage: build_wide_panel.py panel8.npz out.npz SYM..."""
import json, sys, time, urllib.request
import numpy as np
z = np.load(sys.argv[1]); H, D8, P8 = z['hours'], z['data'], list(z['pairs']); out = sys.argv[2]; syms = sys.argv[3:]
h0, h1 = int(H[0]), int(H[-1])+1
data = np.full((len(H), len(syms), 5), np.nan)
for j, s in enumerate(syms):
    if s in P8: data[:, j] = D8[:, P8.index(s)]; continue
    rows, h = {}, h0
    while h < h1:
        e = min(h+500, h1)
        for k in range(5):
            try: rs = json.load(urllib.request.urlopen(f'https://api.poloniex.com/markets/{s}_USDT/candles?interval=HOUR_1&startTime={h*3600000}&endTime={e*3600000-1}&limit=500', timeout=30)); break
            except Exception: time.sleep(2)
        for r in rs: rows[int(r[12])//3600000] = [float(r[i]) for i in (2, 1, 0, 3, 4)]
        h = e; time.sleep(.15)
    for hh, v in rows.items():
        if h0 <= hh < h1: data[hh-h0, j] = v
    print(s, len(rows), flush=True)
np.savez_compressed(out, hours=H, data=data, pairs=np.array(syms))
