"""Fast hourly screening simulator (selection only; decisions go to the Go fidelity harness). Long-only spot, equal slots,
1h delay (signal issued h-1 from bars < h-1, trade at open h), fee + per-pair half-spread per side, 10% trailing stop on hourly
opens, cooldown after any sale, cash reserve. Folds = production refit blocks (start V+1, 28 days)."""
import numpy as np

ANCHOR, PERIOD = 497256, 28*24


def folds(H, issued_blocks):
    H0 = int(H[0]); out = []
    for V in issued_blocks:
        a0, b0 = V+1-H0, min(V+PERIOD+1, int(H[-1])+1)-H0
        if b0-a0 >= 7*24: out.append((a0, b0, int(V)))
    return out


def run(op, sig, hs, fee, a0, b0, *, slots=3, th_in=0., th_out=None, min_hold=72, cool=120, reserve=.4, stop=.1, daily=False, topk_exit=False):
    """op (n,P) hourly opens; sig (n,P) signal usable at hour h (already delayed); hs (P,) half-spread. Returns equity path."""
    P = op.shape[1]; cash = 1.; qty = np.zeros(P); entered = np.full(P, -10**9); peak = np.zeros(P); cool_until = np.full(P, -10**9)
    eq = []; c_buy = 1+hs+fee; c_sell = (1-hs)*(1-fee)
    for h in range(a0, b0):
        px = op[h]; held = qty > 0
        peak = np.where(held, np.maximum(peak, px), 0.)
        equity = cash+(qty*px).sum()
        s = sig[h]; can = not daily or (h % 24 == 1)   # caller passes absolute hour parity via sig rows; see wrapper
        stopped = held & (px < (1-stop)*peak)
        for j in np.where(stopped)[0]:
            cash += qty[j]*px[j]*c_sell[j]; qty[j] = 0; cool_until[j] = h+cool
        if can and np.isfinite(s).all():
            held = qty > 0; order = np.argsort(-s)
            if topk_exit: keep = set(order[:slots].tolist())
            for j in np.where(held)[0]:
                if h-entered[j] < min_hold: continue
                out = (j not in keep) if topk_exit else (s[j] < th_out)
                if out: cash += qty[j]*px[j]*c_sell[j]; qty[j] = 0; cool_until[j] = h+cool
            equity = cash+(qty*px).sum(); target = equity*(1-reserve)/slots
            for j in order[:slots] if topk_exit else order:
                if (qty > 0).sum() >= slots: break
                if qty[j] > 0 or h < cool_until[j] or (not topk_exit and s[j] < th_in): continue
                spend = min(target, cash-equity*reserve)
                if spend <= target*.25: break
                qty[j] = spend/(px[j]*c_buy[j]); cash -= spend; entered[j] = h; peak[j] = px[j]
        eq.append(cash+(qty*px).sum())
    last = op[b0-1]; eq.append(cash+(qty*last*c_sell).sum())
    return np.array(eq)


def monthly_dd(eq):
    m = np.maximum.accumulate(eq); return float((1-eq/m).max())
