"""Job lines fixture|out|config for one stage. usage: python3 -I jobs.py <root> <stage> [--xzec]"""
import json, sys
root, stage = sys.argv[1], sys.argv[2]; xz = '_xzec' if '--xzec' in sys.argv else ''
BASE = dict(Slots=3, Cooldown=120, WindowCycles=60, Reserve=0.4, HaltPeak=0.25, HaltDaily=0.08, TopUp=True, Budget='495', MaxOrder='49',
            Fees=[0.0014, 0.004], MinHoldH=72, Book='archive', FollowCycles=59, MinExit='24.5', ExitRamp=20)
GATE = f'{root}/in/gate_btc720.json'
ARMS = dict(incumbent=('incumbent', {}), xr_feat=('xr_feat', {}), btc720_entry=('incumbent', dict(Gate=GATE, GateMode='entry')),
            btc720_flat=('incumbent', dict(Gate=GATE, GateMode='flat')), xr_feat_btc720=('xr_feat', dict(Gate=GATE, GateMode='entry')),
            exec_buy=('incumbent', dict(BuyBand=0.003, BuyPart=0.25)))
only = [a for a in sys.argv[3:] if not a.startswith('--')] or list(ARMS)
for arm in only:
    fx, extra = ARMS[arm]
    for seed in (1, 2, 3):
        print(f'{root}/fx/{fx}{xz}_{stage}.json|{root}/rp/{stage}/{arm}_b{seed}{xz}|{json.dumps(dict(BASE, BookSeed=seed, **extra), separators=(",", ":"))}')
