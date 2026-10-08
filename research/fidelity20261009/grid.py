"""Jobs for the 2026-10-09 fidelity k-fold: deployed profile at the measured 14 bps fee on archived-book
depth/spread, legacy exits vs the exit safeguard, plus the deployed knobs' immediate neighbours (safeguard on).
usage: python3 -I grid.py <rp-root> > jobs.txt"""
import json, sys
FX = '/vfast/data/code/bitbankpoloniex/data/longkfold20261007/fx/e2306{}.json'
D = dict(slots=3, hold=72, cool=120, res=0.4, topup=True)
NEIGH = [dict(slots=2), dict(slots=4), dict(hold=48), dict(hold=96), dict(cool=72), dict(cool=168), dict(res=0.3), dict(res=0.5), dict(topup=False)]
SAFE = dict(MinExit='24.5', ExitRamp=20)
SEEDS = (1, 2, 3)
FEES = [0.0014]


def name(c, safe):
    return f"s{c['slots']}_h{c['hold']}_c{c['cool']}_r{c['res']}" + ('' if c['topup'] else '_notop') + ('_safe' if safe else '_legacy')


def cfg(c, safe, seed, fees=FEES):
    x = dict(Slots=c['slots'], Cooldown=c['cool'], WindowCycles=60, Reserve=c['res'], HaltPeak=0.25, HaltDaily=0.08, TopUp=c['topup'], Budget='495', MaxOrder='49',
             Fees=fees, MinHoldH=c['hold'], Book='archive', BookSeed=seed, FollowCycles=59)
    if safe: x.update(SAFE)
    return x


def jobs(root):
    out = []
    for u in ('', '_xzec'):
        for seed in SEEDS:
            for safe in (False, True):
                out.append((FX.format(u), f'{root}/{name(D, safe)}_b{seed}{u}', cfg(D, safe, seed, [0.0014, 0.0033])))
            for n in NEIGH:
                c = {**D, **n}; out.append((FX.format(u), f'{root}/{name(c, True)}_b{seed}{u}', cfg(c, True, seed)))
    return out


if __name__ == '__main__':
    for fx, o, c in jobs(sys.argv[1]): print(f'{fx}|{o}|{json.dumps(c, separators=(",", ":"))}')
