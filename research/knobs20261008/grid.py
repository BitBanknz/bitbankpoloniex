"""Pre-registered knob grid (docs/2026-10-08-knob-grid-measured-cost-prereg.md). Prints queue.sh job lines."""
import json, sys
D = dict(slots=3, hold=72, cool=120, res=0.4, topup=True)
AXES = dict(slots=[1, 2, 3, 4, 5], hold=[24, 48, 72, 96, 120], cool=[24, 72, 120, 168, 240], res=[0.2, 0.3, 0.4, 0.5], topup=[True, False])
CUBE = [dict(slots=s, hold=h, cool=c) for s in (3, 4) for h in (48, 72) for c in (72, 120)]
FEES = [0.0014, 0.0033]


def name(c):
    return 's%d_h%d_c%d_r%g%s' % (c['slots'], c['hold'], c['cool'], c['res'], '' if c['topup'] else '_notop')


def configs():
    out = {name(D): dict(D)}
    for ax, vals in AXES.items():
        for v in vals: c = dict(D); c[ax] = v; out[name(c)] = c
    for x in CUBE: c = dict(D); c.update(x); out[name(c)] = c
    return out


def engine_cfg(c):
    return json.dumps(dict(Slots=c['slots'], Cooldown=c['cool'], WindowCycles=12, Reserve=c['res'], HaltPeak=0.25, HaltDaily=0.08,
                           TopUp=c['topup'], Budget='495', MaxOrder='49', Fees=FEES, MinHoldH=c['hold']), separators=(',', ':'))


if __name__ == '__main__':
    fx, rp = sys.argv[1], sys.argv[2]
    for n, c in configs().items():
        for suf in ('', '_xzec'):
            print(f'{fx}/e2306{suf}.json|{rp}/{n}{suf}|{engine_cfg(c)}')
