import json, time, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parents[2]/'data/ranker/prod_ohlcv.json'
PAIRS = ['BNB','ETC','ETH','PEPE','SUI','TRX','XRP','ZEC']
start_h = int(time.mktime((2026, 8, 20, 0, 0, 0, 0, 0, 0))) // 3600
end_h = int(time.time() // 3600) - 1
data = {}
for p in PAIRS:
    rows, h = {}, start_h
    while h <= end_h:
        e = min(h + 499, end_h)
        url = f'https://api.poloniex.com/markets/{p}_USDT/candles?interval=HOUR_1&startTime={h*3600000}&endTime={e*3600000+3599999}&limit=500'
        for r in json.load(urllib.request.urlopen(url, timeout=30)):
            rows[int(r[12]) // 3600000] = [float(r[2]), float(r[1]), float(r[0]), float(r[3]), float(r[4])]
        h = e + 1; time.sleep(0.15)
    data[p] = rows
    print(p, len(rows), min(rows), max(rows), flush=True)
json.dump(data, open(OUT, 'w'))
