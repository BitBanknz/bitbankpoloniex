import json, sys, time, urllib.request
from pathlib import Path
OUT = Path(__file__).resolve().parents[2]/'data/ranker'
SYMS = {'BNB': 'BNBUSDT', 'ETC': 'ETCUSDT', 'ETH': 'ETHUSDT', 'PEPE': '1000PEPEUSDT', 'SUI': 'SUIUSDT', 'TRX': 'TRXUSDT', 'XRP': 'XRPUSDT', 'ZEC': 'ZECUSDT'}
START = int(time.mktime((2022, 6, 1, 0, 0, 0, 0, 0, 0))) * 1000
for k, sym in SYMS.items():
    rows, t = [], START
    while True:
        url = f'https://fapi.binance.com/fapi/v1/fundingRate?symbol={sym}&startTime={t}&limit=1000'
        with urllib.request.urlopen(url, timeout=30) as r: data = json.load(r)
        if not data: break
        rows += [(d['fundingTime'], float(d['fundingRate'])) for d in data]
        if len(data) < 1000: break
        t = data[-1]['fundingTime'] + 1; time.sleep(0.2)
    (OUT/f'funding_{k}.json').write_text(json.dumps(rows))
    print(k, sym, len(rows), time.strftime('%Y-%m-%d', time.gmtime(rows[0][0]/1000)) if rows else None, flush=True)
