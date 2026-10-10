"""Stage fixtures with only the folds a stage may see: dev = folds 0-29, conf = 30-41, w84 = 14 merged 3-fold windows.
usage: python3 -I split_fixture.py fixture.json out_prefix"""
import hashlib, json, sys

src, prefix = sys.argv[1], sys.argv[2]
f = json.load(open(src)); folds = f['Folds']; assert len(folds) == 42
assert all(folds[i][1] == folds[i+1][0] for i in range(41))
stages = dict(dev=folds[:30], conf=folds[30:], w84=[[folds[3*k][0], folds[3*k+2][1]] for k in range(14)])
for name, fs in stages.items():
    g = dict(f, Folds=fs); path = f'{prefix}_{name}.json'
    open(path, 'w').write(json.dumps(g, separators=(',', ':')))
    print(name, len(fs), hashlib.sha256(open(path, 'rb').read()).hexdigest())
