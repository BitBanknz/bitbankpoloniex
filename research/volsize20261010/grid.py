"""Jobs for the 2026-10-10 vol-sizing k-fold: deployed+safeguard profile (14 bps, archived books, 42 e2306 folds,
3 book seeds, 8 pairs and ex-ZEC) vs vol-scaled slot targets. usage: python3 -I grid.py <rp-root> > jobs.txt"""
import json, sys
FX = '/vfast/data/code/bitbankpoloniex/data/longkfold20261007/fx/e2306{}.json'
BASE = dict(Slots=3, Cooldown=120, WindowCycles=60, Reserve=0.4, HaltPeak=0.25, HaltDaily=0.08, TopUp=True, Budget='495', MaxOrder='49',
            Fees=[0.0014, 0.0033], MinHoldH=72, Book='archive', FollowCycles=59, MinExit='24.5', ExitRamp=20)
ARMS = {'inc': {}}
for vt in (0.5, 0.8, 1.2):
    for w in (1.0, 1.5): ARMS[f'vt{vt}_w{w}'] = dict(VolTarget=vt, VolMax=w)
ARMS['vt0.8_w1.5_v168'] = dict(VolTarget=0.8, VolMax=1.5, VolMode='168')
ARMS['ddt0.2'] = dict(DDT=0.2, DDF=0.25)
EXTRA = {'ddt0.15': dict(DDT=0.15, DDF=0.25), 'ddt0.3': dict(DDT=0.3, DDF=0.25)}  # added after the first seed-1 read: ddt0.2 was the only near-tie
ARMS.update(EXTRA)
SEEDS = (1, 2, 3)
UNIV = ('', '_xzec')


def jobs(root, arms=ARMS):
    for u in UNIV:
        for s in SEEDS:
            for n, a in arms.items():
                yield FX.format(u), f'{root}/{n}_b{s}{u}', {**BASE, 'BookSeed': s, **a}


if __name__ == '__main__':
    for fx, o, c in jobs(sys.argv[1], EXTRA if '--extra' in sys.argv else ARMS): print(f'{fx}|{o}|{json.dumps(c, separators=(",", ":"))}')
