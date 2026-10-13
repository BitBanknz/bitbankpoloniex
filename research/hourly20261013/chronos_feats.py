"""Chronos-2 zero-shot close forecasts at every hour from the 512 completed hourly closes before it (bars < h).
Saves q[h, pair, k] for k = (q10,q50,q90) at steps 24 and 72 as returns vs the last close. usage: chronos_feats.py panel.npz out.npz [--stride 1] [--limit N]"""
import argparse, time
import numpy as np, torch
from chronos import Chronos2Pipeline

ap = argparse.ArgumentParser(); ap.add_argument('panel'); ap.add_argument('out'); ap.add_argument('--ctx', type=int, default=512)
ap.add_argument('--stride', type=int, default=1); ap.add_argument('--limit', type=int, default=0); ap.add_argument('--batch', type=int, default=1024)
a = ap.parse_args()
z = np.load(a.panel); D = z['data']; close = D[:, :, 3]; n, P = close.shape
pipe = Chronos2Pipeline.from_pretrained('amazon/chronos-2', device_map='cuda', torch_dtype=torch.bfloat16)
origins = np.arange(a.ctx, n+1, a.stride)
if a.limit: origins = origins[:a.limit]
out = np.full((n+1, P, 2, 3), np.nan, dtype=np.float32); t0 = time.time()
jobs = [(i, j) for i in origins for j in range(P)]
for k in range(0, len(jobs), a.batch):
    b = jobs[k:k+a.batch]
    ctx = np.stack([np.log(close[i-a.ctx:i, j]) for i, j in b]); last = ctx[:, -1:]
    q, _ = pipe.predict_quantiles(torch.tensor(ctx-last, dtype=torch.float32)[:, None, :], prediction_length=72, quantile_levels=[.1, .5, .9], batch_size=a.batch)
    q = torch.stack(q).float().cpu().numpy()[:, 0]  # (B, 72, 3) log-return paths
    for (i, j), v in zip(b, q): out[i, j] = np.expm1(v[[23, 71]])
    if k//a.batch % 20 == 0: print(f'{k+len(b)}/{len(jobs)} {time.time()-t0:.0f}s', flush=True)
np.savez_compressed(a.out, q=out, origins=origins, ctx=a.ctx)
print('done', time.time()-t0)
