"""Pair universe as a searched parameter, tuned jointly with the rotation knobs. Nested walk-forward plus PBO (CSCV).

The signal is the production rotation recipe (lgbm_rank, 38 features, 72h target), refit on the 28-day grid. It is trained
on the 24-pair U+ panel and smoothed by a daily EMA. A config trades only its allowed pairs:
- pairs whose half-spread is at most `hs_cap`;
- pairs whose median 24h quote volume over the 30 days before the fold is at least `vol_floor`;
- among those, an explicit include-mask.
Decisions are made daily at 01:00 UTC.

The fast simulator (`hn_sim.run`, about 1 pp/fold from the Go engine) is used for search only. Any winner must then pass the
Go harness and the round gates.

Usage:
- `uni_search.py sample --n N --seed S --out cfgs.json`
- `uni_search.py eval cfgs.json part nparts out.npz`
- `uni_search.py report out*.npz`"""
import json, os, sys, itertools
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../hourly20261013')); from hn_sim import run, folds  # noqa: E402

W = os.environ.get('UNI_DIR', '/vfast/data/trading_research_20261014/uni')
HS = json.load(open(os.environ.get('UNI_HS', '/vfast/data/trading_research_20261013/hourly/hn/hs_uplus.json')))
SPACE = dict(slots=[2, 3, 4], min_hold=[48, 72, 96], cool=[72, 120, 168], reserve=[.3, .4, .5], alpha=[.25, .35, .5], stop=[.1, .15],
             hs_cap=[5, 10, 20, 35, 60], vol_floor=[1e6, 3e6, 8e6])


def load():
    z = np.load(f'{W}/panel24.npz'); H, D, pairs = z['hours'], z['data'], list(z['pairs'])
    s = np.load(f'{W}/scores24.npz'); I, R, M = s['issued'], s['raw'], s['model']
    d = I % 24 == 0; return H, D, pairs, I[d], R[d], M[d]


def sample(n, seed):
    r = np.random.default_rng(seed); out = []
    for _ in range(n):
        c = {k: v[r.integers(len(v))] for k, v in SPACE.items()}
        c['include'] = [bool(x) for x in r.random(24) < r.uniform(.4, 1.)]
        out.append({k: (float(v) if isinstance(v, (np.floating,)) else int(v) if isinstance(v, np.integer) else v) for k, v in c.items()})
    # anchors: production knobs on U8 and on all-liquid pairs
    base = dict(slots=3, min_hold=72, cool=120, reserve=.4, alpha=.35, stop=.1)
    out.append({**base, 'hs_cap': 60, 'vol_floor': 1e6, 'include': [i < 8 for i in range(24)]})
    out.append({**base, 'hs_cap': 60, 'vol_floor': 1e6, 'include': [True]*24})
    return out


def evaluate(cfgs, fee=.0014):
    H, D, pairs, I, R, M = load(); H0 = int(H[0]); op = D[:, :, 0]; vol = D[:, :, 4]
    c24 = np.cumsum(np.vstack([np.zeros((1, 24)), vol]), axis=0); v24 = np.full(vol.shape, np.nan); v24[24:] = c24[24:-1]-c24[:-25]
    hs = np.array([HS[p] for p in pairs])/1e4; F = folds(H, sorted(set(M.tolist())))
    sigs = {}
    for a in SPACE['alpha']:
        e = R.copy()
        for k in range(1, len(e)): e[k] = a*R[k]+(1-a)*e[k-1]
        sig = np.full(op.shape, np.nan); ii = I-H0+1; ok = ii < len(sig); sig[ii[ok]] = e[ok]; sigs[a] = sig
    out = np.full((len(cfgs), len(F)), np.nan)
    for ci, c in enumerate(cfgs):
        for fi, (a0, b0, V) in enumerate(F):
            med = np.nanmedian(v24[max(a0-720, 24):a0], axis=0)  # liquidity known before the fold
            allow = np.array(c['include']) & (hs*1e4 <= c['hs_cap']) & (med >= c['vol_floor'])
            if allow.sum() < c['slots']+2: out[ci, fi] = np.nan; continue
            sig = sigs[c['alpha']].copy(); sig[:, ~allow] = -1e9
            eq = run(op, sig, hs, fee, a0, b0, slots=c['slots'], min_hold=c['min_hold'], cool=c['cool'], reserve=c['reserve'], stop=c['stop'], daily=True, topk_exit=True)
            out[ci, fi] = 100*(eq[-1]-1)
    return out, np.array([V for _, _, V in F])


def pbo(R, S=8):
    """CSCV probability of backtest overfitting (Bailey et al.): the share of IS/OOS splits where the IS-best config's OOS
    performance is below the OOS median."""
    T = R.shape[1]; groups = np.array_split(np.arange(T), S); lam = []
    for comb in itertools.combinations(range(S), S//2):
        isx = np.concatenate([groups[g] for g in comb]); oos = np.setdiff1d(np.arange(T), isx)
        best = np.nanargmax(np.nanmean(R[:, isx], axis=1)); o = np.nanmean(R[:, oos], axis=1)
        rank = (o < o[best]).sum()/(np.isfinite(o).sum()-1); lam.append(np.log(rank/(1-rank)) if 0 < rank < 1 else (-9 if rank <= 0 else 9))
    lam = np.array(lam); return float((lam <= 0).mean())


def report(paths):
    zs = [np.load(p, allow_pickle=True) for p in paths]
    R = np.concatenate([z['R'] for z in zs]); R33 = np.concatenate([z['R33'] for z in zs]); cfgs = sum([list(z['cfgs']) for z in zs], []); V = zs[0]['V']
    ok = np.isfinite(R).all(1); R, R33, cfgs = R[ok], R33[ok], [c for c, k in zip(cfgs, ok) if k]
    print(f'{len(cfgs)} complete configs x {R.shape[1]} folds; PBO(CSCV, S=8) = {pbo(R):.2f}')
    anchor = [i for i, c in enumerate(cfgs) if c['include'] == [i2 < 8 for i2 in range(24)] and c['slots'] == 3 and c['alpha'] == .35 and c['hs_cap'] == 60 and c['vol_floor'] == 1e6 and c['min_hold'] == 72 and c['cool'] == 120]
    a = anchor[0]
    blocks = np.array_split(np.arange(R.shape[1]), 7); oos, oos33, base, base33, picks = [], [], [], [], []
    for b in range(1, 7):
        isx = np.concatenate(blocks[:b]); score = np.nanmean(R[:, isx], 1) - 1e9*(np.nanmin(R[:, isx], 1) < -20)
        k = int(np.argmax(score)); picks.append(k)
        oos += list(R[k, blocks[b]]); oos33 += list(R33[k, blocks[b]]); base += list(R[a, blocks[b]]); base33 += list(R33[a, blocks[b]])
    oos, oos33, base, base33 = map(np.array, (oos, oos33, base, base33)); d = oos-base
    print(f'nested WF (select on all earlier 6-fold blocks, test next block), {len(oos)} OOS folds:')
    print(f'  selected  14bp mean {oos.mean():+.2f} worst {oos.min():+.2f} | 33bp mean {oos33.mean():+.2f} worst {oos33.min():+.2f}')
    print(f'  anchor U8 14bp mean {base.mean():+.2f} worst {base.min():+.2f} | 33bp mean {base33.mean():+.2f} worst {base33.min():+.2f}')
    print(f'  paired d {d.mean():+.2f} t {d.mean()/d.std(ddof=1)*np.sqrt(len(d)):+.2f} wins {(d > 0).sum()}/{len(d)}')
    for b, k in zip(range(1, 7), picks):
        c = cfgs[k]; print(f'  block {b} pick: slots {c["slots"]} hold {c["min_hold"]} cool {c["cool"]} res {c["reserve"]} a {c["alpha"]} stop {c["stop"]} hs<={c["hs_cap"]} vol>={c["vol_floor"]:.0e} n_incl {sum(c["include"])}')
    full = np.argmax(np.nanmean(R, 1)); print('full-sample best (in-sample, biased):', f'{np.nanmean(R[full]):+.2f}', cfgs[full])


if __name__ == '__main__':
    cmd = sys.argv[1]
    if cmd == 'sample':
        n, seed, out = int(sys.argv[3]), int(sys.argv[5]), sys.argv[7]; json.dump(sample(n, seed), open(out, 'w'))
    elif cmd == 'eval':
        cfgs = json.load(open(sys.argv[2])); part, nparts = int(sys.argv[3]), int(sys.argv[4]); mine = cfgs[part::nparts]
        R, V = evaluate(mine); R33, _ = evaluate(mine, .0033)
        np.savez(sys.argv[5], R=R, R33=R33, V=V, cfgs=np.array(mine, dtype=object))
    else:
        report(sys.argv[2:])
