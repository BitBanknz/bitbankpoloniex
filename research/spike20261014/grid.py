"""Round-4 jobs: resting spike sells, depth haircuts, liquidity floor; incumbent and paper arms. usage: grid.py <rp> <fx>"""
import json, sys
rp, fx = sys.argv[1:3]
BASE = dict(Slots=3, Cooldown=120, WindowCycles=60, Reserve=0.4, HaltPeak=0.25, HaltDaily=0.08, TopUp=True, Budget='495', MaxOrder='49',
            MinHoldH=72, Book='archive', FollowCycles=59, MinExit='24.5', ExitRamp=20, Fees=[0.0014, 0.0033])
RIDGE = dict(Cadence='hourly', HourCycles=12, Delay=1, Thresh=True, EntryMin=.005, ExitBelow=-.005, MinHoldH=24)
H = {'d25': dict(DepthMult=.25), 'd10': dict(DepthMult=.1), 'z02': dict(DepthSym={'ZEC_USDT': .02})}
arms = {}
for k in (2, 3, 4, 6):
    for w in (24, 168):
        arms[f'sp_k{k}_w{w}'] = ('inc', dict(SpikeK=k, SpikeWin=w, SpikeTT=.001))
for n, o in H.items():
    arms[f'inc_{n}'] = ('inc', o)
arms['liq_mv3m'] = ('inc', dict(MinVolume=3e6)); arms['liq_mv8m'] = ('inc', dict(MinVolume=8e6)); arms['liq_drop2'] = ('inc_drop2', {})
for n, o in H.items():
    arms[f'hema_{n}'] = ('d_hema', o); arms[f'ridge_{n}'] = ('ridge', {**RIDGE, **o})
for u in ('', '_xzec'):
    for s in (1, 2, 3):
        for a, (stem, o) in arms.items():
            print(f'{fx}/{stem}{u}.json|{rp}/{a}_b{s}{u}|{json.dumps({**BASE, **o, "BookSeed": s}, separators=(",", ":"))}')
