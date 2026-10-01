import re, sys, statistics as st
from pathlib import Path
pat = re.compile(r'days=(\d+) fee=(\S+) bonus=1 fold=(\d+) return=(\S+) dd=(\S+)')
def load(p):
    c = {}
    for m in pat.finditer(Path(p).read_text()):
        c.setdefault((int(m[1]), float(m[2])), {})[int(m[3])] = (float(m[4]), float(m[5]))
    return c
b, t = load(sys.argv[1]), load(sys.argv[2])
ok = True; wins = n = 0
for k in sorted(b):
    fb, ft = b[k], t[k]; mb = st.mean(v[0] for v in fb.values()); mt = st.mean(v[0] for v in ft.values())
    wb = min(v[0] for v in fb.values()); wt = min(v[0] for v in ft.values())
    db = max(v[1] for v in fb.values()); dt = max(v[1] for v in ft.values())
    w = sum(ft[i][0] > fb[i][0] for i in fb)
    if k[1] == 0.005: wins += w; n += len(fb)
    r1, r3, r4 = mt > mb, dt <= db, wt >= wb - 2
    ok &= r1 and r3 and r4
    print('days=%d fee=%g folds=%d mean %+.2f -> %+.2f  worst %+.1f -> %+.1f  dd %.1f -> %.1f  paired wins %d/%d  [mean %s dd %s worst %s]' % (k[0], k[1], len(fb), mb, mt, wb, wt, db, dt, w, len(fb), r1, r3, r4))
print('pooled paired wins at 50bps: %d/%d = %.0f%% (need >=60%%)' % (wins, n, 100 * wins / n))
print('CONFIRMED' if ok and wins / n >= .6 else 'NOT CONFIRMED')
