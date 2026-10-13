"""Selection-bias check: apply the pre-registered finalist rule using only folds before 2024-01 (6 folds), then score the
selected configs once on 2024-01+ (36 folds). usage: hn_timesplit.py baseline_split.txt split/*.txt"""
import re, sys, collections
base = {}
for l in open(sys.argv[1]):
    m = re.match(r'(\S+) (\S+) .* pre (\S+) (\S+) post (\S+) (\S+)', l)
    f, u = float(m.group(1)), 'ZEC' if m.group(2) == 'xZEC' else '8p'; base[(f, u)] = tuple(map(float, m.groups()[2:]))
rows = collections.defaultdict(dict)
for fn in sys.argv[2:]:
    for l in open(fn):
        m = re.match(r'(\S+) (\S+) (.*?) \| 14: (\S+) \| 33: (\S+)', l.strip())
        if m: rows[(m.group(1), m.group(3))][m.group(2)] = {.0014: tuple(map(float, m.group(4).split('/'))), .0033: tuple(map(float, m.group(5).split('/')))}
sel = []
for k, d in rows.items():
    if set(d) != {'8p', 'ZEC'}: continue
    ok = all(d[u][f][0] > base[(f, u)][0] and d[u][f][1] > base[(f, u)][1] for u in d for f in (.0014, .0033)) and all(d[u][.0033][0] > 0 for u in d)
    if ok: sel.append((d['ZEC'][.0014][0], k, d))
sel.sort(reverse=True)
print(f'{len(sel)} of {len(rows)} configs pass the rule on pre-2024 folds only')
print('baseline 2024+ (mean/worst):', {f'{u}@{f*1e4:.0f}': (v[2], v[3]) for (f, u), v in base.items()})
for rank, (x, k, d) in enumerate(sel[:5], 1):
    print(rank, k, 'pre', {f'{u}@{f*1e4:.0f}': d[u][f][:2] for u in d for f in d[u]}, '2024+', {f'{u}@{f*1e4:.0f}': d[u][f][2:] for u in d for f in d[u]})
rk = sorted(rows, key=lambda k: -rows[k].get('ZEC', {}).get(.0014, (-9,))[0] if set(rows[k]) == {'8p', 'ZEC'} else 9)
print('rank of hn_xs_m24 (u8_xs24_ridge in50 out-50 mh24 k3) by pre-2024 xZEC@14 mean:', rk.index(('u8_xs24_ridge', 'in50 out-50 mh24 k3'))+1, 'of', len(rk))
