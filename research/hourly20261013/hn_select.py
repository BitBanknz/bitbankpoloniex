"""Apply the pre-registered finalist rule to screen outputs. usage: hn_select.py baseline.txt screen_*.txt"""
import re, sys, collections
base = {}
for l in open(sys.argv[1]):
    f, u, m, w = re.match(r'(\S+) (\S+) mean (\S+) worst (\S+)', l).groups(); base[(float(f), 'ZEC' if u == 'xZEC' else '8p')] = (float(m), float(w))
rows = collections.defaultdict(dict)
for fn in sys.argv[2:]:
    for l in open(fn):
        m = re.match(r'(\S+) (\S+) (.*?) \| 14: (\S+) \| 33: (\S+)', l.strip())
        if not m: continue
        v = [tuple(map(float, x.split('/'))) for x in m.groups()[3:]]
        rows[(m.group(1), m.group(3))][m.group(2)] = {.0014: v[0], .0033: v[1]}
ok = []
for k, d in rows.items():
    if set(d) != {'8p', 'ZEC'}: continue
    good = all(d[u][f][0] > base[(f, u)][0] and d[u][f][1] > base[(f, u)][1] for u in d for f in (.0014, .0033)) and all(d[u][.0033][0] > 0 for u in d)
    if good: ok.append((d['ZEC'][.0014][0], k, d))
ok.sort(reverse=True)
print(f'{len(ok)} of {len(rows)} configs pass the screen rule')
for x, k, d in ok[:10]: print(k, {u: {f: d[u][f] for f in d[u]} for u in d})
