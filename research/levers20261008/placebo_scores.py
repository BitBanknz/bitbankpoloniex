"""Placebo score arm: same issue dates, refit blocks and pairs as a real arm, raw scores iid N(0,1) per day and pair.
make_fixture.py then applies the production EMA (0.35) exactly as for real scores, so placebo ranks have the
same smoothing/persistence mechanics but no information."""
import argparse
from pathlib import Path
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument('--like', type=Path, required=True); ap.add_argument('--seed', type=int, required=True); ap.add_argument('--out', type=Path, required=True)
a = ap.parse_args()
s = np.load(a.like)
rng = np.random.default_rng(a.seed)
raw = rng.standard_normal(s['raw'].shape)
np.savez(a.out, issued=s['issued'], raw=raw, model=s['model'], pairs=s['pairs'])
