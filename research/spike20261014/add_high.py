"""Add each hour's High (panel column 1) to a replay fixture, for resting spike-sell trade-through checks.
usage: add_high.py panel.npz in.json out.json"""
import json, sys
import numpy as np
z = np.load(sys.argv[1]); H, D, pairs = z['hours'], z['data'], list(z['pairs']); H0 = int(H[0])
f = json.load(open(sys.argv[2])); keep = [pairs.index(p[:-4]) for p in f['Pairs']]
for h in f['Hours']:
    i = h['TS']//3600-H0; h['High'] = D[i, keep, 1].tolist()
    assert np.allclose(h['Open'], D[i, keep, 0])
json.dump(f, open(sys.argv[3], 'w'), separators=(',', ':'))
print(sys.argv[3], len(f['Hours']))
