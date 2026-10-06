"""Hourly 8-pair panel 2023-06-01 -> latest completed hour from Poloniex public candles
(the production seed source; bit-identical to the production training seed
2025-10-01..2026-09-08). The local archive is only cross-checked (float-format
diffs ~1e-10). Gaps are counted and forward-filled (close carried,
zero volume) only where the venue returned no candle; production would refuse such
a window, so gap days are reported."""
import argparse, json, time, urllib.request
from pathlib import Path
import numpy as np, pandas as pd

PAIRS = ['BNB', 'ETC', 'ETH', 'PEPE', 'SUI', 'TRX', 'XRP', 'ZEC']
COLS = ['open', 'high', 'low', 'close', 'quote_volume']
ROOT = Path(__file__).resolve().parents[2]


def archive(p):
    df = pd.read_csv(ROOT/f'data/archive-hourly/{p}_USDT/candles.csv')
    df['h'] = pd.to_datetime(df.timestamp, utc=True).astype('int64') // 3600_000_000_000
    return df.drop_duplicates('h').set_index('h')[COLS].sort_index()


def fetch(p, h0, h1):
    rows, h = {}, h0
    while h < h1:
        e = min(h + 500, h1)
        url = f'https://api.poloniex.com/markets/{p}_USDT/candles?interval=HOUR_1&startTime={h*3600000}&endTime={e*3600000-1}&limit=500'
        for r in json.load(urllib.request.urlopen(url, timeout=30)):
            assert r[11] == 'HOUR_1' and int(r[13]) == int(r[12]) + 3599999
            rows[int(r[12]) // 3600000] = [float(r[i]) for i in (2, 1, 0, 3, 4)]
        h = e; time.sleep(.2)
    return pd.DataFrame.from_dict(rows, orient='index', columns=COLS).sort_index()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--out', type=Path, required=True); ap.add_argument('--seed', type=Path)
    ap.add_argument('--start', default='2023-06-01'); a = ap.parse_args()
    now = int(time.time() // 3600); h0 = int(pd.Timestamp(a.start, tz='UTC').value // 3600_000_000_000)
    fstart = h0 - 400
    grid = np.arange(h0, now)
    data = np.full((len(grid), len(PAIRS), 5), np.nan); gaps = {}; checks = {}; filled = np.zeros((len(grid), len(PAIRS)), bool)
    for j, p in enumerate(PAIRS):
        ar = archive(p); api = fetch(p, fstart, now)
        ov = ar.index.intersection(api.index)
        checks[p] = dict(api_overlap=len(ov), api_overlap_max_abs_diff=float(np.abs(ar.loc[ov].to_numpy() - api.loc[ov].to_numpy()).max()) if len(ov) else None)
        merged = pd.concat([ar[ar.index < fstart], api]).reindex(grid)
        if a.seed:
            sd = pd.read_csv(a.seed/f'{p}USDT.csv'); sd.index = pd.to_datetime(sd.timestamp, utc=True).astype('int64') // 3600_000_000_000
            checks[p].update(seed_rows=len(sd), seed_exact=bool((merged.loc[sd.index, COLS].to_numpy() == sd[COLS].to_numpy()).all()))
        miss = merged.close.isna().to_numpy()
        gaps[p] = int(miss.sum()); filled[:, j] = miss
        c = merged.close.ffill().to_numpy()
        for k in ('open', 'high', 'low', 'close'):
            merged.loc[miss, k] = c[miss]
        merged.loc[miss, 'quote_volume'] = 0.
        data[:, j] = merged[COLS].to_numpy(float)
    assert np.isfinite(data).all() and (data[:, :, :4] > 0).all()
    a.out.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(a.out, hours=grid, data=data, pairs=np.array(PAIRS), filled=filled)
    print(json.dumps(dict(first=str(pd.Timestamp(grid[0]*3600, unit='s')), last=str(pd.Timestamp(grid[-1]*3600, unit='s')), hours=len(grid), gaps=gaps, checks=checks), indent=1))


if __name__ == '__main__':
    main()
