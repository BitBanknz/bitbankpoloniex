"""mopt objective (stream mode). Runs the fast simulator over the 42 production refit folds and prints one JSON row per fold:
{"fold", "ret" (14 bps), "ret33", "mdd" (max marked drawdown in the fold, %), "n_allowed"}.

The universe comes from --universe (comma-separated, chosen by mopt). It is further limited by the liquidity constraints
--hs-cap (pair half-spread in bps) and --vol-floor (median 24h quote volume over the 30 days before the fold).

usage: uni_obj.py --universe BTC,ETH,... --slots 3 --min-hold 72 --cool 120 --reserve 0.4 --alpha 0.35 --stop 0.1 --hs-cap 60 --vol-floor 1e6 [--folds 0,1,..]"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../hourly20261013'))
from hn_sim import run, folds  # noqa: E402
from uni_search import load, HS  # noqa: E402

ap = argparse.ArgumentParser()
for k, t, d in (('universe', str, ''), ('slots', int, 3), ('min-hold', int, 72), ('cool', int, 120), ('reserve', float, .4), ('alpha', float, .35),
                ('stop', float, .1), ('hs-cap', float, 60), ('vol-floor', float, 1e6), ('folds', str, '')):
    ap.add_argument('--'+k, type=t, default=d)
a = ap.parse_args()
H, D, pairs, I, R, M = load(); H0 = int(H[0]); op = D[:, :, 0]; vol = D[:, :, 4]
c24 = np.cumsum(np.vstack([np.zeros((1, len(pairs))), vol]), axis=0); v24 = np.full(vol.shape, np.nan); v24[24:] = c24[24:-1]-c24[:-25]
hs = np.array([HS[p] for p in pairs])/1e4
F = folds(H, sorted(set(M.tolist())))
e = R.copy()
for k in range(1, len(e)): e[k] = a.alpha*R[k]+(1-a.alpha)*e[k-1]
sig0 = np.full(op.shape, np.nan); ii = I-H0+1; ok = ii < len(sig0); sig0[ii[ok]] = e[ok]
uni = set(a.universe.split(',')) if a.universe else set(pairs)
want = [int(x) for x in a.folds.split(',')] if a.folds else range(len(F))
for fi in want:
    a0, b0, V = F[fi]
    med = np.nanmedian(v24[max(a0-720, 24):a0], axis=0)
    allow = np.array([p in uni for p in pairs]) & (hs*1e4 <= a.hs_cap) & (med >= a.vol_floor)
    row = dict(fold=fi, n_allowed=int(allow.sum()), idle=0)
    if allow.sum() < a.slots+1:
        row.update(ret=0.0, ret33=0.0, mdd=0.0, idle=1)  # nothing tradable: the bot stays in cash
    else:
        sig = sig0.copy(); sig[:, ~allow] = -1e9
        for fee, key in ((.0014, 'ret'), (.0033, 'ret33')):
            eq = run(op, sig, hs, fee, a0, b0, slots=a.slots, min_hold=a.min_hold, cool=a.cool, reserve=a.reserve, stop=a.stop, daily=True, topk_exit=True)
            row[key] = float(100*(eq[-1]-1))
            if key == 'ret': row['mdd'] = float(100*(1-eq/np.maximum.accumulate(eq)).max())
    print(json.dumps(row), flush=True)
