"""Archived Poloniex 5-level books -> per-symbol snapshot shapes for the replay book model.\nusage: python3 -I book_snapshots.py <out-dir> <panel.npz>  (derived from the 2026-10-09 books_build.py extractor)"""
import base64, gzip, io, json, os, re, subprocess, sys, tarfile, glob, collections
OUT = sys.argv[1]
PANEL = sys.argv[2]
R = '/vfast/data/trading_research_20260924/'
SYMS = ['BNB', 'ETC', 'ETH', 'PEPE', 'SUI', 'TRX', 'XRP', 'ZEC']
DIRS = sorted(set(os.path.dirname(p) for p in glob.glob(R + 'poloniex_*/**/minute_*.jsonl.gz', recursive=True)))
TARS = [R + 'poloniex_future_prefix_3297_v1/capture_v3.tar.zst', R + 'poloniex_future_prefix_3297_v1/capture_v2.tar.zst', R + 'poloniex_future_prefix_3297_v1/capture.tar'] + sorted(glob.glob(R + 'poloniex_*/**/snapshot.tar.gz', recursive=True))
MRE = re.compile(r'minute_(\d+)\.jsonl\.gz$')
rows = {}
src = collections.OrderedDict()
stat = collections.Counter()
start_by = {}

def recorder_of(protocol_bytes):
    return int(json.loads(protocol_bytes)['start_ns'])

def feed(data, tag, start_ns, minute):
    s = src.setdefault(tag, dict(minutes=set(), book_rows=0, new_rows=0, non200=0, start_ns=start_ns))
    s['minutes'].add(minute)
    data = gzip.decompress(data) if data[:2] == b'\x1f\x8b' else data
    for line in data.splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        n = r.get('name', '')
        if not n.startswith('book_'):
            continue
        sym = n[5:].split('_')[0]
        if sym not in SYMS:
            continue
        if r.get('status') != 200 or not r.get('body_b64'):
            s['non200'] += 1; stat['non200_' + str(r.get('status'))] += 1
            continue
        b = json.loads(base64.b64decode(r['body_b64']))
        bids, asks = b.get('bids') or [], b.get('asks') or []
        bl = [(float(bids[i]), float(bids[i + 1])) for i in range(0, len(bids) - 1, 2)]
        al = [(float(asks[i]), float(asks[i + 1])) for i in range(0, len(asks) - 1, 2)]
        if not bl or not al:
            stat['empty_side'] += 1
            continue
        s['book_rows'] += 1
        ts = int(b['ts'])
        key = (sym, ts)
        if key in rows:
            stat['dup'] += 1
            continue
        b1, a1 = bl[0][0], al[0][0]
        bw = [(p, q) for p, q in bl if p >= b1 * 0.999]
        aw = [(p, q) for p, q in al if p <= a1 * 1.001]
        rows[key] = (ts, sym, bl, al)
        s['new_rows'] += 1
        continue
        rows[key] = (ts, sym, b1, a1,
                     sum(q for _, q in bw), sum(p * q for p, q in bw), sum(p * q for p, q in bl), len(bl),
                     sum(q for _, q in aw), sum(p * q for p, q in aw), sum(p * q for p, q in al), len(al),
                     start_ns, minute, int(r['response_received_ns']) // 1_000_000)
        s['new_rows'] += 1

for d in DIRS:
    pp = os.path.join(d, 'protocol.json')
    st = recorder_of(open(pp, 'rb').read()) if os.path.exists(pp) else None
    if st is None and os.path.exists(os.path.join(os.path.dirname(d), 'source', 'protocol.json')):
        st = recorder_of(open(os.path.join(os.path.dirname(d), 'source', 'protocol.json'), 'rb').read())
    for f in sorted(glob.glob(d + '/minute_*.jsonl.gz')):
        feed(open(f, 'rb').read(), d, st, int(MRE.search(f).group(1)))

for t in TARS:
    try:
        if t.endswith('.zst'):
            p = subprocess.Popen(['zstd', '-dc', t], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            tf = tarfile.open(fileobj=p.stdout, mode='r|')
        elif t.endswith('.gz'):
            tf = tarfile.open(t, mode='r|gz')
        else:
            tf = tarfile.open(t, mode='r|')
        st = None
        pending = []
        for m in tf:
            if not m.isfile():
                continue
            if m.name.endswith('source/protocol.json'):
                st = recorder_of(tf.extractfile(m).read())
                continue
            mm = MRE.search(m.name)
            if mm and '/source/' in '/' + m.name:
                data = tf.extractfile(m).read()
                if st is None:
                    pending.append((data, int(mm.group(1))))
                else:
                    feed(data, t, st, int(mm.group(1)))
        for data, mi in pending:
            feed(data, t, st, mi)
    except Exception as e:
        stat['tar_error'] += 1
        src.setdefault(t, dict(minutes=set(), book_rows=0, new_rows=0, non200=0, start_ns=None))['error'] = repr(e)[:200]
        for data, mi in locals().get('pending', []):
            feed(data, t, st, mi)


import numpy as np
z = np.load(PANEL); H = z['hours'].astype(int); vol = z['data'][:, :, 4]; pairs = list(z['pairs']); idx = {h: i for i, h in enumerate(H)}
snaps = {s: [] for s in SYMS}; skipped = collections.Counter()
for (sym, ts), (_, _, bl, al) in sorted(rows.items(), key=lambda kv: (kv[0][1], kv[0][0])):
    h = ts // 3600000; i = idx.get(h)
    if i is None or i < 1: skipped['no_panel_hour'] += 1; continue
    turn = float(vol[i - 24:i, pairs.index(sym)].mean())
    if not turn > 0: skipped['zero_turnover'] += 1; continue
    mid = (bl[0][0] + al[0][0]) / 2
    snaps[sym].append(dict(ts=ts, B=[[p / mid - 1, p * q / turn] for p, q in bl], A=[[p / mid - 1, p * q / turn] for p, q in al]))
json.dump(dict(source='archived Poloniex 5-level public books (recorder 2026-09-24..27), levels as [price/mid-1, level USDT / mean hourly quote turnover of the prior 24h]', counts={s: len(v) for s, v in snaps.items()}, skipped=dict(skipped), Snapshots=snaps), gzip.open(os.path.join(OUT, 'book_snapshots.json.gz'), 'wt'), separators=(',', ':'))
print({s: len(v) for s, v in snaps.items()}, dict(skipped), dict(stat))
