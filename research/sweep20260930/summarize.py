import re, sys, json, statistics as st
from pathlib import Path
root = Path(sys.argv[1]); base = sys.argv[2] if len(sys.argv) > 2 else 's3_c120_r0.4_h25_8'
pat = re.compile(r'days=(\d+) fee=(\S+) bonus=1 fold=(\d+) return=(\S+) dd=(\S+)')
def load(d):
    c = {}
    for m in pat.finditer((d/'run.log').read_text()):
        days, fee, fold, r, dd = int(m[1]), float(m[2]), int(m[3]), float(m[4]), float(m[5])
        c.setdefault((days, fee), {})[fold] = (r, dd)
    return c
runs = {d.name: load(d) for d in sorted(root.iterdir()) if (d/'run.log').exists() and '\nok' in '\n'+(d/'run.log').read_text()}
cells = [(d, f) for d in (0, 28, 56) for f in (.003, .004)]
def stat(c, k):
    v = c[k]; r = [x[0] for x in v.values()]
    return st.mean(r), min(r), sum(x > 0 for x in r), max(x[1] for x in v.values()), v
B = runs[base]
rows = []
for n, c in runs.items():
    s = {k: stat(c, k) for k in cells}; b = {k: stat(B, k) for k in cells}
    r1 = all(s[k][0] > b[k][0] for k in cells)
    r2 = all(s[k][1] >= b[k][1] - 2 for k in cells if k[0])
    r3 = all(s[k][2] >= b[k][2] for k in cells if k[0])
    r4 = all(s[k][3] <= 25 for k in cells)
    wins = sum(s[(28, .004)][4][i][0] > b[(28, .004)][4][i][0] for i in s[(28, .004)][4])
    r5 = wins >= 6
    score = (s[(28, .004)][0] + s[(56, .004)][0]) / 2
    rows.append((n, r1, r2, r3, r4, r5, wins, score, s))
rows.sort(key=lambda x: -x[7])
print('config | c30 m | c40 m | 28@30 mean/worst/pos/dd | 28@40 | 56@30 | 56@40 | rules1-5 wins40 score')
for n, r1, r2, r3, r4, r5, w, sc, s in rows:
    f = lambda k: '%+.2f/%.1f/%d/%.1f' % (s[k][0], s[k][1], s[k][2], s[k][3])
    print(n, '| %+.2f | %+.2f |' % (s[(0, .003)][0], s[(0, .004)][0]), f((28, .003)), '|', f((28, .004)), '|', f((56, .003)), '|', f((56, .004)), '|', ''.join('Y' if x else 'n' for x in (r1, r2, r3, r4, r5)), w, '%.2f' % sc)
print('PASS:', [r[0] for r in rows if all(r[1:6]) and r[0] != base])
