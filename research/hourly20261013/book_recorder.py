"""Public GET-only 5-level book recorder for universe extension (one snapshot per pair per minute). usage: book_recorder.py out.jsonl SYM..."""
import json, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor
out, syms = sys.argv[1], sys.argv[2:]
def get(s):
    try:
        with urllib.request.urlopen(f'https://api.poloniex.com/markets/{s}_USDT/orderBook?limit=5', timeout=10) as r: b = json.load(r)
        return dict(sym=s, ts=int(b['ts']), bids=b['bids'], asks=b['asks'])
    except Exception as e: return dict(sym=s, err=str(e)[:100], t=time.time())
while True:
    t0 = time.time()
    with ThreadPoolExecutor(4) as p: rows = list(p.map(get, syms))
    with open(out, 'a') as f:
        for r in rows: f.write(json.dumps(r, separators=(',', ':'))+'\n')
    time.sleep(max(1, 60-(time.time()-t0)))
