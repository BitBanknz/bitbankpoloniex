"""Python walk-forward harness (rotation_policy.simulate_rotation, as poloniex_deployed_walkforward --slots 3)
on the same EMA ranks and fold blocks as the Go replay, to quantify the harness gap.
Python fee = Go FeeRate + 5 bps proxy half-spread."""
import argparse, json, os, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, os.environ.get('BITBANKGO_SCRIPTS', '/vfast/data/code/bitbankgo/scripts'))
from poloniex_execution_study import execution_inputs  # noqa: E402
from rotation_policy import simulate_rotation  # noqa: E402


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--panel', type=Path, required=True); ap.add_argument('--scores', type=Path, required=True)
    ap.add_argument('--go', type=Path, required=True, help='Go replay dir (results.jsonl)'); a = ap.parse_args()
    z = np.load(a.panel); H, D = z['hours'], z['data']; H0 = int(H[0])
    s = np.load(a.scores); issued, raw, model = s['issued'], s['raw'], s['model']
    ema = raw.copy()
    for i in range(1, len(ema)): ema[i] = .35*raw[i]+.65*ema[i-1]
    go = [json.loads(l) for l in open(a.go/'results.jsonl')]
    rows = []
    for v in sorted(set(model.tolist())):
        k = np.where(model == v)[0]; k = k[issued[k]+24 <= H[-1]]
        if len(k) < 7: continue
        inputs = execution_inputs(D, issued[k]-H0, 1, 'volatility')
        for fee in (.003, .004):
            m, curve, _ = simulate_rotation(ema[k], fee_bps=fee*1e4+5, slots=3, margin=.4, min_days=3, cash_reserve=.4, trailing_stop=.1, **inputs)
            g = [r for r in go if r['Fee'] == fee and r['Start'] == (int(v)+1)*3600]
            rows.append(dict(start=str(pd.Timestamp(v*3600, unit='s').date()), fee=fee, py=m['return_pct'], py_dd=m['max_drawdown_pct'],
                             go=g[0]['LiqReturnPct'] if g else np.nan, go_dd=g[0]['Report']['MaxDrawdownPct'] if g else np.nan))
    df = pd.DataFrame(rows).dropna()
    for fee, g in df.groupby('fee'):
        print(f'fee={fee} folds={len(g)} py mean {g.py.mean():+.2f} go mean {g.go.mean():+.2f} gap {(g.py-g.go).mean():+.2f}pp '
              f'mean|gap| {(g.py-g.go).abs().mean():.2f}pp corr {np.corrcoef(g.py, g.go)[0, 1]:.2f} py maxdd {g.py_dd.max():.1f} go maxdd {g.go_dd.max():.1f}')
    df.to_csv(a.go/'harness_gap.csv', index=False)


if __name__ == '__main__':
    main()
