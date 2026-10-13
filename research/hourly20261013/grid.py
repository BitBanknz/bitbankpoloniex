"""Job lines for the hourly-cadence k-fold. usage: grid.py <stage> <rp-root> <fx-root>  (fixture|outdir|config)"""
import json, sys
INC_FX = '/vfast/data/code/bitbankpoloniex/data/longkfold20261007/fx/e2306{}.json'
BASE = dict(Slots=3, Cooldown=120, WindowCycles=60, Reserve=0.4, HaltPeak=0.25, HaltDaily=0.08, TopUp=True, Budget='495', MaxOrder='49',
            MinHoldH=72, Book='archive', FollowCycles=59, MinExit='24.5', ExitRamp=20)
HOURLY = dict(Cadence='hourly', HourCycles=12, Delay=1)
FEES = [0.0014, 0.0033]
SEEDS = (1, 2, 3)
STAGES = {
    # name: (fixture stem or None for daily incumbent, config overrides)
    's1': {'inc': (None, {}), 'h_ema': ('m0_ema00178', HOURLY), 'h_anch': ('m0_anchored', HOURLY), 'h_ema05': ('m0_ema005', HOURLY), 'h_raw': ('m0_raw', HOURLY)},
    's2': {'d_hema': ('d_hema', {}), 'h_ema_d0': ('m0_ema00178', {**HOURLY, 'Delay': 0}), 'h_anch_d0': ('m0_anchored', {**HOURLY, 'Delay': 0}),
           'd_chr': ('d_m0c', {}), 'h_chr': ('m0c_ema00178', HOURLY),
           'h_ema_cf24': ('m0_ema00178', {**HOURLY, 'ExitConfirmH': 24}), 'h_anch_cf24': ('m0_anchored', {**HOURLY, 'ExitConfirmH': 24})},
    's3': {'h_stale': ('h_stale', HOURLY)},
}


def main():
    stage, rp, fx = sys.argv[1:4]
    for u in ('', '_xzec'):
        for seed in SEEDS:
            for arm, (stem, over) in STAGES[stage].items():
                f = INC_FX.format(u) if stem is None else f'{fx}/{stem}{u}.json'
                c = {**BASE, **over, 'BookSeed': seed, 'Fees': FEES}
                print(f'{f}|{rp}/{arm}_b{seed}{u}|{json.dumps(c, separators=(",", ":"))}')


if __name__ == '__main__':
    main()
