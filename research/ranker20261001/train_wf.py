import sys, time
import numpy as np, pandas as pd
from feats import *
import lightgbm as lgb
import torch
from sklearn.linear_model import Ridge

m = load(); days, f, y, liq = daily_panel(m)
names, arr, yv, ok = long_form(days, f, y, liq)
yok = ok & np.isfinite(yv)
X = np.stack([xs_rank(arr[..., k], ok) for k in range(arr.shape[-1])], axis=-1)
Y = xs_rank(np.nan_to_num(yv), yok)
T, N, F = X.shape
dates = days
start = np.searchsorted(dates, pd.Timestamp('2023-01-01', tz='UTC'))
end = np.searchsorted(dates, pd.Timestamp('2026-09-07', tz='UTC'))
first = np.searchsorted(dates, pd.Timestamp('2020-01-01', tz='UTC'))
dev = 'cuda'

def rows(a, b):
    sl = slice(a, b); msk = yok[sl]
    return X[sl][msk], Y[sl][msk]

def fit_predict(kind, cfg, Xtr, Ytr, Xte):
    if kind == 'ridge':
        return Ridge(alpha=cfg).fit(Xtr, Ytr).predict(Xte)
    if kind == 'lgb':
        mdl = lgb.LGBMRegressor(n_estimators=200, learning_rate=0.03, num_leaves=cfg, min_child_samples=200,
                                subsample=0.8, subsample_freq=1, colsample_bytree=0.8, verbose=-1, n_jobs=8)
        return mdl.fit(Xtr, Ytr).predict(Xte)
    if kind == 'mlp':
        h = cfg
        xt = torch.tensor(Xtr, dtype=torch.float32, device=dev); yt = torch.tensor(Ytr, dtype=torch.float32, device=dev)
        xe = torch.tensor(Xte, dtype=torch.float32, device=dev)
        preds = []
        for seed in range(8):
            torch.manual_seed(seed)
            net = torch.nn.Sequential(torch.nn.Linear(F, h), torch.nn.ReLU(), torch.nn.Dropout(0.2),
                                      torch.nn.Linear(h, h), torch.nn.ReLU(), torch.nn.Dropout(0.2), torch.nn.Linear(h, 1)).to(dev)
            opt = torch.optim.AdamW(net.parameters(), lr=2e-3, weight_decay=1e-3)
            n = len(xt)
            for ep in range(12):
                perm = torch.randperm(n, device=dev)
                for i in range(0, n, 1024):
                    b = perm[i:i+1024]
                    loss = torch.nn.functional.mse_loss(net(xt[b]).squeeze(-1), yt[b])
                    opt.zero_grad(); loss.backward(); opt.step()
            net.eval()
            with torch.no_grad(): preds.append(net(xe).squeeze(-1).cpu().numpy())
        return np.mean(preds, 0)

models = [('ridge', 1), ('ridge', 10), ('ridge', 100), ('lgb', 7), ('lgb', 15), ('lgb', 31), ('mlp', 64), ('mlp', 128)]
out = {f'{k}_{c}': np.full((T, N), np.nan) for k, c in models}
t0 = time.time()
r = start
while r < end:
    r2 = min(r + 30, end)
    Xtr, Ytr = rows(first, r - 2)
    te = ok[r:r2]
    Xte = X[r:r2][te]
    for k, c in models:
        p = fit_predict(k, c, Xtr, Ytr, Xte)
        blk = out[f'{k}_{c}'][r:r2]; blk[te] = p
    print('refit', dates[r].date(), len(Xtr), '%.0fs' % (time.time() - t0), flush=True)
    r = r2
np.savez_compressed(D/'wf_scores.npz', dates=np.array([d.value for d in dates]), cols=np.array(list(m['close'].columns)), **out)
print('done')
