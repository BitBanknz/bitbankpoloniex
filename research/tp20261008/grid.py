"""Pre-registered take-profit / armed-trail grid (docs/2026-10-08-take-profit-prereg.md). Prints queue.sh job lines."""
import json, sys
D = dict(tp=0.0, arm=0.0, stop=0.0)
TP = [0.10, 0.15, 0.20, 0.30, 0.35, 0.40, 0.50]
ARM = [0.10, 0.20, 0.30]; ARM_STOP = 0.05
FEES = [0.0014, 0.0033]


def name(c):
    if c['tp']: return 'tp%04d' % round(c['tp']*1e4)
    if c['arm']: return 'arm%04d_s%03d' % (round(c['arm']*1e4), round(c['stop']*1e4))
    return 'D'


def configs():
    out = {'D': dict(D)}
    for v in TP: c = dict(D, tp=v); out[name(c)] = c
    for v in ARM: c = dict(D, arm=v, stop=ARM_STOP); out[name(c)] = c
    return out


def neighbours(n):
    """one-step neighbours along the arm's own ladder (D excluded)."""
    c = configs()[n]
    lad, k = (TP, 'tp') if c['tp'] else (ARM, 'arm')
    i = lad.index(c[k]); return [name(dict(c, **{k: lad[j]})) for j in (i-1, i+1) if 0 <= j < len(lad)]


def engine_cfg(c):
    return json.dumps(dict(Slots=3, Cooldown=120, WindowCycles=12, Reserve=0.4, HaltPeak=0.25, HaltDaily=0.08, TopUp=True, Budget='495', MaxOrder='49',
                           Fees=FEES, MinHoldH=72, TakeProfit=c['tp'], TrailArm=c['arm'], TrailArmStop=c['stop']), separators=(',', ':'))


if __name__ == '__main__':
    fx, rp = sys.argv[1], sys.argv[2]
    for n, c in configs().items():
        for suf in ('', '_xzec'):
            print(f'{fx}/e2306{suf}.json|{rp}/{n}{suf}|{engine_cfg(c)}')
