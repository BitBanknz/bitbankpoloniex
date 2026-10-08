"""Passive baselines on the same 28-day folds as a fixture: equal-weight buy-and-hold of the tradable pairs
(bought at the fold's first open, sold at its last open, cost per side), and 60%-invested (reserve 0.4) version."""
import json, sys
import numpy as np
fx = json.load(open(sys.argv[1])); cost = float(sys.argv[2]) if len(sys.argv) > 2 else .0019
O = np.array([h['Open'] for h in fx['Hours']])
r = []
for a, b in fx['Folds']:
    g = O[b-1]/O[a]*(1-cost)**2
    r.append(100*(g.mean()-1))
r = np.array(r)
print(f"{sys.argv[1].split('/')[-1]} cost {cost*1e4:.0f}bps folds {len(r)}: EW B&H mean {r.mean():+.2f} median {np.median(r):+.2f} worst {r.min():+.2f} pos {(r>0).sum()}; at 60% invested mean {0.6*r.mean():+.2f}")
