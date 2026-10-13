"""Parity: bitbankgo scripts/rotation_ridge_hourly.py (paper A/B job) fit+predict vs research hn_scores ridge xs24 predictions
for the last two refit blocks. usage: parity_ridge_job.py panel.npz hn/u8_xs24_ridge.npz"""
import sys
import numpy as np
sys.path.insert(0, '/vfast/data/code/bitbankgo/scripts')
import rotation_ridge_hourly as R
z = np.load(sys.argv[1]); H, D = z['hours'], z['data']; H0 = int(H[0]); assert H0 == R.START_HOUR
s = np.load(sys.argv[2]); I, P = s['issued'], s['pred']; pos = {int(h): k for k, h in enumerate(I)}
for V in (R.ANCHOR-R.PERIOD, R.ANCHOR):
    w = R.fit(H, D, V); worst = 0.
    for h in range(V, min(V+R.PERIOD, int(H[-1])+1)):
        p = R.predict(w, D[h-337-H0:h-H0]); worst = max(worst, float(np.abs(p-P[pos[h]]).max()))
    print('refit', V, 'rows', w['training_rows'], 'max |pred diff|', worst)
st = None
for h in range(R.ANCHOR, R.ANCHOR+6):
    hist = dict(pairs=R.PAIRS, hours=list(range(h-337, h)), ohlcv=D[h-337-H0:h-H0].tolist())
    st = R.issue(w, hist, st, issued_hour=h, now_hour=h)
print('state issues', [i['issued_hour'] for i in st['issues']], 'latest edges diff', float(np.abs(np.array(st['issues'][-1]['edges'])-P[pos[R.ANCHOR+5]]).max()))
