"""Extract verbatim public orderBook?limit=5 and ticker24h responses per minute, and the served rotation-signals rank
scores, from a public_retention recorder archive.
usage: python3 -I extract_recorded_books.py <recorder-dir> <out.json.gz> [<ranks-out.json>]"""
import base64, glob, gzip, json, sys
from pathlib import Path


def main():
    root, out = sys.argv[1], sys.argv[2]
    books, tick, ranks = {}, {}, {}
    for path in sorted(glob.glob(f'{root}/minute_*.jsonl.gz')):
        for line in gzip.open(path, 'rt'):
            r = json.loads(line)
            if r['status'] != 200 or r['error'] or r['body_truncated']:
                continue
            minute = r['request_started_ns'] // 60_000_000_000 * 60
            if r['name'].startswith('book_'):
                b = json.loads(base64.b64decode(r['body_b64']))
                books.setdefault(r['name'][5:], {})[str(minute)] = [b['bids'], b['asks'], b['ts']]
            elif r['name'] == 'ranks':
                b = json.loads(base64.b64decode(r['body_b64']))
                ranks.setdefault(b['issued_at'], set()).add(json.dumps(b['rank_scores'], sort_keys=True))
            elif r['name'] == 'ticker24h':
                rows = json.loads(base64.b64decode(r['body_b64']))
                tick[str(minute)] = {x['symbol']: x['amount'] for x in rows if x['symbol'].endswith('_USDT')}
    with gzip.open(out, 'wt') as f:
        json.dump(dict(books=books, ticker24h_amount=tick), f, separators=(',', ':'))
    if len(sys.argv) > 3:
        Path(sys.argv[3]).write_text(json.dumps({k: [json.loads(x) for x in v] for k, v in ranks.items()}))
    print({k: len(v) for k, v in books.items()}, len(tick), len(ranks))


if __name__ == '__main__':
    main()
