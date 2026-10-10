"""Read-only shadow comparison of live Poloniex decisions against the Go engine behind loopback mock HTTP.
Each window starts from the real live ledger snapshot and uses the live unit argv of that period.
usage: python3 -I shadow.py fixtures | run <window> <arm> [--engine new|old] | compare"""
import argparse, gzip, json, os, shlex, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

W = Path(os.environ.get('SHADOW_WORK', '/vfast/data/trading_research_20261011/shadow'))
IN = W/'inputs'
REPO = Path('/vfast/data/code/bitbankpoloniex')
PAIRS = ['BNB', 'ETC', 'ETH', 'PEPE', 'SUI', 'TRX', 'XRP', 'ZEC']
BOOKS = Path('/vfast/data/trading_research_20261009/fidelity/book_snapshots.json.gz')
WINDOWS = {
    'w0': dict(start='states/cooldown-release-20260914/live-verified-state.json', end='states/release-topup-20260924/state.before.json',
               check='states/topup_20260918/state.before.json', unit='states/cooldown-release-20260914/bitbankpoloniex-live.service',
               binaries='c5d03648 (09-14 10:21), 2c2c81c4 (09-15 03:16, 698c9b5), eb9a2d10 (09-18)', engine_default_fee=.003),
    'w2': dict(start='states/release-topup-20260924/state.before.json', end='states/release-fidelity-20261009/live.before/state.json',
               check=None, unit='states/release-fidelity-20261009/unit.before',
               binaries='eb9a2d10 (to 09-30 10:13), 4cc91224 release-stop-guard-20260930_v3 (09-30 10:13)', engine_default_fee=.003),
    'w1': dict(start='states/release-fidelity-20261009/live.before/state.json', end='live-state-20261010T1156.json',
               check=None, unit='live-unit-current.txt', binaries='6b10fdb6 = f3aa665 (10-08 14:50)', engine_default_fee=.0014),
}
ARMS = {
    'hourly_proxy': dict(Clock='hourly', Book='proxy', seeds=[0]),
    'hourly_archive': dict(Clock='hourly', Book='archive', seeds=[1, 2, 3]),
    'minute_archive': dict(Clock='minute', Book='archive', seeds=[1, 2, 3]),
    'minute_recorded': dict(Clock='minute', Book='archive', seeds=[1, 2, 3], recorded=True),
}
LIVE_ONLY = {'--command': 'run', '--mode': 'live'}
IGNORED = {'--state', '--predictions', '--env'}


def iso(t): return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%MZ')


def parse_ts(s):
    s = s.replace('Z', '')
    if '.' in s:
        a, b = s.split('.'); s = a + '.' + b[:6]
    return datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp()


def argv_config(text, default_fee):
    line = [l for l in text.splitlines() if l.startswith('ExecStart=')]
    toks = shlex.split(line[0].split('=', 1)[1]) if line else shlex.split(text.strip().splitlines()[-1])
    assert toks[0].endswith('/bitbankpoloniex'), toks[0]
    c = dict(Slots=3, Cooldown=0, MinHoldH=0, ExitRamp=0, MaxOrdersDay=12, Reserve=.4, HaltPeak=0, HaltDaily=0, TopUp=False, Budget='1000', MaxOrder='25', MinExit='0', fee=default_fee)
    num = {'--budget': ('Budget', str), '--max-order': ('MaxOrder', str), '--slots': ('Slots', int), '--cooldown-hours': ('Cooldown', int), '--min-hold-hours': ('MinHoldH', int),
           '--cash-reserve': ('Reserve', float), '--halt-peak-dd': ('HaltPeak', float), '--halt-daily-loss': ('HaltDaily', float), '--fee-rate': ('fee', float),
           '--min-exit-usdt': ('MinExit', str), '--exit-ramp-minutes': ('ExitRamp', int), '--max-orders-day': ('MaxOrdersDay', int)}
    seen, i, live = [], 1, False
    while i < len(toks):
        k = toks[i]; seen.append(k)
        if k in ('--slot-top-up', '--enable-live-orders'):
            c['TopUp'] |= k == '--slot-top-up'; live |= k == '--enable-live-orders'; i += 1; continue
        v = toks[i+1]; i += 2
        if k in LIVE_ONLY:
            assert v == LIVE_ONLY[k], (k, v)
        elif k in IGNORED:
            pass
        elif k == '--interval':
            assert v in ('1m', '1m0s', '60s'), v
        elif k in num:
            c[num[k][0]] = num[k][1](v)
        else:
            raise SystemExit(f'unsupported live flag {k}: refusing to simulate an unknown configuration')
    assert live and len(seen) == len(set(seen))
    return c, toks


def candles():
    out = {}
    for name in ('candles_1h.json.gz', 'candles_1m.json.gz'):
        c = json.load(gzip.open(IN/'candles'/name, 'rt'))
        out[name] = {p: {int(r[0]): r[1:] for r in c['pairs'][p]} for p in PAIRS}
    return out['candles_1h.json.gz'], out['candles_1m.json.gz']


def served_scores():
    s = np.load(REPO/'data/longkfold20261007/scores/s2510.npz'); iss, raw = s['issued'].astype(int), s['raw']
    assert [str(x) for x in s['pairs']] in (PAIRS, [p+'USDT' for p in PAIRS])
    ema = raw.copy()
    for i in range(1, len(ema)): ema[i] = .35*raw[i]+.65*ema[i-1]
    rec = {int(h): (ema[k].tolist(), 'reconstructed_s2510_ema') for k, h in enumerate(iss)}
    collected = [json.loads(x) for x in (REPO/'data/forward/scores.jsonl').read_text().splitlines() if x.strip()]
    for d in sorted((IN/'snapshots').glob('snapshot_*')):
        collected.append(json.loads((d/'forecast.json').read_text()))
    for k, vs in json.loads((IN/'recorded_served_ranks.json').read_text()).items():
        assert len(vs) == 1
        collected.append(dict(pairs=[p+'USDT' for p in PAIRS], issued_hour=int(parse_ts(k))//3600, smoothed_scores=[vs[0][p+'USDT'] for p in PAIRS]))
    err = {}
    for r in collected:
        assert r['pairs'] == [p+'USDT' for p in PAIRS]
        h = int(r['issued_hour'])
        if h in rec and rec[h][1].startswith('reconstructed'):
            err[iso(h*3600)] = float(np.abs(np.array(r['smoothed_scores'])-np.array(rec[h][0])).max())
        if h in rec and rec[h][1] == 'served':
            assert np.allclose(rec[h][0], r['smoothed_scores'], atol=0), h
        rec[h] = (list(r['smoothed_scores']), 'served')
    return rec, err


def build_fixture(name):
    w = WINDOWS[name]
    start, end = json.loads((IN/w['start']).read_text()), json.loads((IN/w['end']).read_text())
    h0 = int(parse_ts(start['LastCycle'])//3600)+1
    h1 = int(parse_ts(end['LastCycle'])//3600)-1
    c1h, c1m = candles()
    hours = []
    for h in range(h0, h1+1):
        ts = h*3600
        o = [c1h[p][ts][0] for p in PAIRS]
        prior = [c1h[p][ts-3600][4] for p in PAIRS]
        v24 = [sum(c1h[p][ts-3600*j][4] for j in range(1, 25)) for p in PAIRS]
        minute = [[c1m[p].get(ts+60*m, [0])[0] for m in range(60)] for p in PAIRS]
        hours.append(dict(TS=ts, Open=o, PriorTurnover=prior, Volume24=v24, Minute=minute))
    rec, err = served_scores()
    ranks = {str(h*3600): v for h, (v, _) in rec.items() if h0-48 <= h <= h1}
    src = {iso(h*3600): s for h, (_, s) in rec.items() if h0-24 <= h <= h1}
    fx = W/'fixtures'/f'{name}.json'; fx.parent.mkdir(parents=True, exist_ok=True)
    fx.write_text(json.dumps(dict(Pairs=[p+'USDT' for p in PAIRS], Hours=hours, Ranks=ranks), separators=(',', ':')))
    cfg, toks = argv_config((IN/w['unit']).read_text(), w['engine_default_fee'])
    meta = dict(window=name, start=iso(h0*3600), end=iso((h1+1)*3600), start_state=w['start'], end_state=w['end'], argv=toks, config=cfg,
                live_binaries=w['binaries'], score_source=src, reconstructed_vs_served_max_abs_err=err,
                missing_minutes={p: sum(1 for h in hours for x in h['Minute'][j] if x == 0) for j, p in enumerate(PAIRS)})
    (W/'fixtures'/f'{name}.meta.json').write_text(json.dumps(meta, indent=1))
    print(name, meta['start'], meta['end'], len(hours), 'hours', cfg)


def run_one(fx, state, out, cfg, arm, seed, engine, fees):
    a = ARMS[arm]; binp = W/f'build-{engine}'/'replay.test'
    c = {k: v for k, v in cfg.items() if k != 'fee'}
    c.update(WindowCycles=60, FollowCycles=59, Clock=a['Clock'], Book=a['Book'], BookSeed=seed, Fees=fees)
    env = {**os.environ, 'SH_FIXTURE': str(fx), 'SH_MARKETS': str(IN/'candles/markets.json'), 'SH_BOOKS': str(BOOKS),
           'SH_CONFIG': json.dumps(c), 'SH_STATE': str(state), 'SH_OUT': str(out), 'GOMAXPROCS': '2', 'GOGC': '400', 'TMPDIR': '/dev/shm'}
    if a.get('recorded'):
        env['SH_RECORDED'] = str(IN/'recorded_books.json.gz')
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([str(binp), '-test.run', 'TestShadowReplay', '-test.count=1', '-test.timeout', '4h', '-test.v'], env=env, capture_output=True, text=True)
    (out/'run.log').write_text(r.stdout[-20000:] + r.stderr[-20000:])
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    (out/'config.json').write_text(json.dumps(dict(config=c, engine=engine, inputs=json.loads((W/f'build-{engine}'/'inputs.json').read_text())), indent=1))
    return [l for l in r.stdout.splitlines() if l.startswith(('fee=', 'recorded'))]


def run(name, arm, engine, fees=None):
    meta = json.loads((W/'fixtures'/f'{name}.meta.json').read_text()); cfg = meta['config']
    fees = fees or sorted({cfg['fee'], .0014})
    for seed in ARMS[arm]['seeds']:
        print(name, arm, engine, seed, run_one(W/'fixtures'/f'{name}.json', IN/meta['start_state'], W/'runs'/name/f'{arm}_{engine}_s{seed}', cfg, arm, seed, engine, fees))


def fills(state, t0, t1, live):
    rows = []
    for f in state.get('Fills') or []:
        t = parse_ts(f['At'])
        if not t0 <= t < t1:
            continue
        o = f['Order']; q, amt = float(f['Quantity']), float(f['Amount'])
        fee_q = sum(float(x['feeAmount']) for x in f.get('ExchangeTrades') or []) if live else float(f['Fee'])
        rows.append(dict(t=t, sym=o['symbol'].split('_')[0], side=o['side'], oq=float(o['quantity']), q=q, amt=amt, px=amt/q,
                         lim=float(o['price']), fee=fee_q, fee_cur=sorted({x['feeCurrency'] for x in f.get('ExchangeTrades') or []}) if live else ['USDT'], src=f['Source']))
    return rows


def keys(state, start_keys, t0, t1):
    out = set()
    for k in state.get('Processed') or {}:
        if k in start_keys:
            continue
        h = parse_ts(k.split('|')[0])
        if t0 - 3600 <= h < t1:
            out.add(k)
    return out


def group(rows):
    g = defaultdict(lambda: dict(q=0., amt=0., n=0, t=[], partial=0))
    for r in rows:
        k = (iso(r['t'])[:10], r['sym'], r['side']); x = g[k]
        x['q'] += r['q']; x['amt'] += r['amt']; x['n'] += 1; x['t'].append(iso(r['t'])[11:16]); x['partial'] += r['q'] < r['oq'] - 1e-12
    return g


def ledger_curve(start, rows, hours, opens, live):
    cash = float(start['Cash']); q = defaultdict(float)
    for s, p in start['Holdings'].items(): q[s.split('_')[0]] += float(p['Quantity'])
    ev = sorted(rows, key=lambda r: r['t']); k = 0; out = []
    for h in hours:
        while k < len(ev) and ev[k]['t'] < h*3600:
            r = ev[k]; k += 1; sg = 1 if r['side'] == 'BUY' else -1
            cash -= sg*r['amt']; q[r['sym']] += sg*r['q']
            if live:
                for cur in r['fee_cur']:
                    if cur == 'USDT': cash -= r['fee']
                    elif cur == 'TRX': q['TRX'] -= r['fee'] if q['TRX'] > 0 else 0; cash -= 0 if q['TRX'] > 0 else r['fee']*opens['TRX'](h)
                    else: q[cur] -= r['fee']
            else:
                cash -= r['fee']
        out.append(cash + sum(v*opens[s](h)*.9995 for s, v in q.items() if v > 1e-12))
    return np.array(out)


def compare():
    c1h, _ = candles(); report = {}
    opens = {p: (lambda p: (lambda h: c1h[p][h*3600][0]))(p) for p in PAIRS}
    for name in WINDOWS:
        mp = W/'fixtures'/f'{name}.meta.json'
        if not mp.exists():
            continue
        meta = json.loads(mp.read_text()); w = WINDOWS[name]
        start, end = json.loads((IN/w['start']).read_text()), json.loads((IN/w['end']).read_text())
        t0, t1 = parse_ts(meta['start']), parse_ts(meta['end'])
        hours = list(range(int(t0//3600), int(t1//3600)+1))
        sk = set(start.get('Processed') or {})
        lrows = fills(end, parse_ts(start['LastCycle']), t1, True); lkeys = keys(end, sk, t0, t1); lg = group(lrows)
        E_live = ledger_curve(start, lrows, hours, opens, True); E0 = E_live[0]
        res = dict(window=meta['start']+'..'+meta['end'], live_binaries=meta['live_binaries'], argv_config=meta['config'],
                   live=dict(fills=len(lrows), decision_keys=len(lkeys), groups=len(lg), ret_pct=(E_live[-1]/E0-1)*100,
                             groups_detail={'|'.join(k): dict(amt=round(v['amt'], 2), n=v['n'], t=v['t'], partial=v['partial']) for k, v in sorted(lg.items())}), arms={})
        for rd in sorted((W/'runs'/name).glob('*')):
            for sf in sorted(rd.glob('state_fee*.json')):
                fee = sf.stem.split('fee')[1]; sim = json.loads(sf.read_text())
                srows = fills(sim, t0-3600, t1, False); skeys = keys(sim, sk, t0, t1); sg = group(srows)
                ks = sorted(set(lg) | set(sg)); agree = lo = so = size = timing = 0; mism = []
                for k in ks:
                    L, S = lg.get(k), sg.get(k)
                    if L and S:
                        if abs(L['amt']/S['amt']-1) > .10:
                            size += 1; mism.append(('size', k, round(L['amt'], 2), round(S['amt'], 2), L['t'][:3], S['t'][:3]))
                        else:
                            agree += 1
                            if L['t'][0][:2] != S['t'][0][:2]:
                                timing += 1
                    elif L:
                        lo += 1; mism.append(('live_only', k, round(L['amt'], 2), None, L['t'][:3], None))
                    else:
                        so += 1; mism.append(('sim_only', k, None, round(S['amt'], 2), None, S['t'][:3]))
                E_sim = ledger_curve(start, srows, hours, opens, False)
                skips = json.loads((rd/f'skips_fee{fee}.json').read_text()) or []
                skip_kinds = defaultdict(int)
                for s in skips: skip_kinds[s['Err'].split(':')[0][:60]] += 1
                gap = (E_sim[-1]-E_live[-1])/E0*100; days = (t1-t0)/86400
                res['arms'][f'{rd.name}_fee{fee}'] = dict(
                    fills=len(srows), groups=len(sg), group_agreement_pct=100*agree/len(ks) if ks else 100., agree=agree, live_only=lo, sim_only=so, size=size,
                    hour_timing_diff_in_agreed=timing, exact_key_agreement_pct=100*len(lkeys & skeys)/len(lkeys | skeys) if lkeys | skeys else 100.,
                    sim_ret_pct=(E_sim[-1]/E0-1)*100, gap_pct=gap, gap_bps_month=gap*100*30.4375/days, max_abs_div_pct=float(np.abs(E_sim-E_live).max()/E0*100),
                    median_clip=float(np.median([r['amt'] for r in srows])) if srows else None, skips=dict(skip_kinds), mismatches=mism)
        report[name] = res
    (W/'report.json').write_text(json.dumps(report, indent=1, default=str))
    for name, r in report.items():
        print(f"== {name} {r['window']} live fills={r['live']['fills']} groups={r['live']['groups']} ret={r['live']['ret_pct']:+.2f}%")
        for arm, x in r['arms'].items():
            print(f"  {arm:34s} agree={x['group_agreement_pct']:5.1f}% ({x['agree']}/{x['agree']+x['live_only']+x['sim_only']+x['size']}) lo={x['live_only']} so={x['sim_only']} size={x['size']} key={x['exact_key_agreement_pct']:5.1f}% sim={x['sim_ret_pct']:+.2f}% gap={x['gap_pct']:+.2f}% ({x['gap_bps_month']:+.0f}bps/mo) clip={x['median_clip']}")


def ts_iso(t): return datetime.fromtimestamp(t, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


_BM = []


def bid_model():
    if not _BM:
        rec = json.load(gzip.open(IN/'recorded_books.json.gz', 'rt'))['books']
        rb = {sym: {m: v[0][0] for m, v in d.items() if v[0]} for sym, d in rec.items()}
        bs = json.load(gzip.open(BOOKS, 'rt'))['Snapshots']
        off = {p: float(np.median([x['B'][0][0] for x in bs[p]])) for p in PAIRS}
        _BM.extend([rb, off])
    return _BM[0], _BM[1]


def reconstruct(start, end, t, cooldown_h, c1m):
    from decimal import Decimal as D
    mk = {m['symbol']: max(D(1), D(m['symbolTradeLimit']['minAmount'])) for m in json.loads((IN/'candles/markets.json').read_text())}
    cash = D(start['Cash']); hold = {k: dict(v) for k, v in start['Holdings'].items()}; cd = dict(start.get('Cooldown') or {})
    t_s = parse_ts(start['LastCycle'])
    marks = {k: parse_ts(v['Entered']) for k, v in hold.items()}
    rb, off = bid_model()
    def peak_upto(sym, a, b, peak):
        p = sym.split('_')[0]; m = int(a)//60*60+60
        while m < b:
            x = rb.get(sym, {}).get(str(m))
            if x: peak = max(peak, D(x))
            else:
                o = c1m[p].get(m)
                if o: peak = max(peak, D(repr(o[0]*(1+off[p]))))
            m += 60
        return peak
    last = t_s
    for f in sorted(end.get('Fills') or [], key=lambda f: parse_ts(f['At'])):
        ft = parse_ts(f['At'])
        if not t_s < ft < t:
            continue
        for k, v in hold.items(): v['Peak'] = str(peak_upto(k, last, ft, D(v['Peak'])))
        last = ft
        o = f['Order']; sym = o['symbol']; q, amt, fee = D(f['Quantity']), D(f['Amount']), D(f['Fee'])
        if o['side'] == 'BUY':
            cash -= amt + fee
            if sym not in hold:
                hold[sym] = dict(Imported=False, Quantity='0', Peak=o['price'], Entered=f['At'])
            hold[sym]['Quantity'] = str(D(hold[sym]['Quantity']) + q)
        else:
            cash += amt - fee
            hold[sym]['Quantity'] = str(D(hold[sym]['Quantity']) - q)
        for x in f.get('ExchangeTrades') or []:
            cur = x['feeCurrency']
            if cur not in ('USDT', sym.split('_')[0]) and D(x['feeAmount']) > 0:
                hold[cur+'_USDT']['Quantity'] = str(D(hold[cur+'_USDT']['Quantity']) - D(x['feeAmount']))
        if D(hold[sym]['Quantity']) <= 0:
            del hold[sym]; cd[sym] = ts_iso(ft + 3600*(cooldown_h or 72))
        elif D(hold[sym]['Quantity'])*D(o['price']) < mk[sym]:
            del hold[sym]
    for k, v in hold.items(): v['Peak'] = str(peak_upto(k, last, t, D(v['Peak'])))
    proc = {k: True for k in (end.get('Processed') or {}) if parse_ts(k.split('|')[0]) < t}
    proc.update({k: True for k in (start.get('Processed') or {})})
    hw = max([D(start['HighWater'])] + [D(e['Value']) for e in end.get('Equity') or [] if parse_ts(e['At']) < t])
    st = {k: start[k] for k in start}
    st.update(Cash=str(cash), Holdings=hold, Cooldown=cd, Processed=proc, HighWater=str(hw), Day=datetime.fromtimestamp(t-86400, timezone.utc).strftime('%Y-%m-%d'),
              OrdersToday=0, LastCycle=ts_iso(t-60), Fills=None, Equity=None, Pending=None, Halted='')
    return st


def daily(name, arms, engine='new', jobs=8):
    from concurrent.futures import ThreadPoolExecutor
    meta = json.loads((W/'fixtures'/f'{name}.meta.json').read_text()); w = WINDOWS[name]; cfg = meta['config']
    start, end = json.loads((IN/w['start']).read_text()), json.loads((IN/w['end']).read_text())
    fx = json.loads((W/'fixtures'/f'{name}.json').read_text()); _, c1m = candles()
    t0, t1 = parse_ts(meta['start']), parse_ts(meta['end'])
    days = [d for d in range(int(t0//86400)*86400, int(t1), 86400)]
    tasks = []
    for d in days:
        a, b = max(d, t0), min(d+86400, t1)
        dd = W/'daily'/name/datetime.fromtimestamp(d, timezone.utc).strftime('%m%d'); dd.mkdir(parents=True, exist_ok=True)
        st = reconstruct(start, end, a, cfg['Cooldown'], c1m); (dd/'state.json').write_text(json.dumps(st, indent=1))
        hrs = [h for h in fx['Hours'] if a <= h['TS'] < b]
        (dd/'fixture.json').write_text(json.dumps(dict(Pairs=fx['Pairs'], Hours=hrs, Ranks=fx['Ranks']), separators=(',', ':')))
        for arm in arms:
            for seed in ARMS[arm]['seeds']:
                tasks.append((dd/'fixture.json', dd/'state.json', dd/f'{arm}_{engine}_s{seed}', cfg, arm, seed, engine, [.0014]))
    final = reconstruct(start, end, t1+3600*24, cfg['Cooldown'], c1m)
    chk = dict(cash_recon=final['Cash'], cash_live=end['Cash'], qty={k: (v['Quantity'], end['Holdings'].get(k, {}).get('Quantity')) for k, v in final['Holdings'].items()},
               peak={k: (v['Peak'], end['Holdings'].get(k, {}).get('Peak')) for k, v in final['Holdings'].items()}, live_holdings=sorted(end['Holdings']))
    (W/'daily'/name/'reconstruction_check.json').write_text(json.dumps(chk, indent=1))
    print(name, 'reconstruction check', chk)
    with ThreadPoolExecutor(jobs) as ex:
        for r in ex.map(lambda x: run_one(*x), tasks): pass
    print(name, 'daily runs', len(tasks))


def daily_compare():
    rep = {}; c1h, _ = candles()
    opens = {p: (lambda p: (lambda h: c1h[p][h*3600][0]))(p) for p in PAIRS}
    for name in WINDOWS:
        base = W/'daily'/name
        if not base.exists(): continue
        w = WINDOWS[name]; end = json.loads((IN/w['end']).read_text())
        arms = defaultdict(lambda: dict(agree=0, lo=0, so=0, size=0, rows=[]))
        ndays = 0
        live_groups = 0
        for dd in sorted(p for p in base.iterdir() if p.is_dir()):
            hrs = json.loads((dd/'fixture.json').read_text())['Hours']
            if not hrs: continue
            ndays += (hrs[-1]['TS']+3600-hrs[0]['TS'])/86400
            a, b = hrs[0]['TS'], hrs[-1]['TS']+3600
            st = json.loads((dd/'state.json').read_text()); lrows = fills(end, a, b, True)
            lg = group(lrows); live_groups += len(lg)
            le = ledger_curve(st, lrows, [a//3600, b//3600], opens, True)
            for rd in sorted(p for p in dd.iterdir() if p.is_dir()):
                arm = rd.name.rsplit('_s', 1)[0]
                sim = json.loads((rd/'state_fee0.0014.json').read_text()); sg = group(fills(sim, a, b, False))
                skips = json.loads((rd/'skips_fee0.0014.json').read_text()) or []
                x = arms[arm]
                se = ledger_curve(st, fills(sim, a, b, False), [a//3600, b//3600], opens, False)
                x.setdefault('gap', defaultdict(float))[rd.name.rsplit('_s', 1)[1]] += (se[1]-le[1])/le[0]*100
                for k in sorted(set(lg) | set(sg)):
                    L, S = lg.get(k), sg.get(k)
                    if L and S and abs(L['amt']/S['amt']-1) <= .10: x['agree'] += 1; kind = 'agree'
                    elif L and S: x['size'] += 1; kind = 'size'
                    elif L: x['lo'] += 1; kind = 'live_only'
                    else: x['so'] += 1; kind = 'sim_only'
                    sk = sorted({s['Err'][:40] for s in skips if k[1]+'_USDT' in s['Key'] and k[2] in s['Key']})
                    x['rows'].append(dict(seed=rd.name.rsplit('_s', 1)[1], key='|'.join(k), kind=kind, live=None if not L else dict(amt=round(L['amt'], 2), n=L['n'], t=L['t']),
                                          sim=None if not S else dict(amt=round(S['amt'], 2), n=S['n'], t=S['t']), sim_skips=sk))
        out = {}
        for arm, x in arms.items():
            n = x['agree']+x['lo']+x['so']+x['size']
            g = list(x['gap'].values())
            out[arm] = dict(agreement_pct=100*x['agree']/n if n else None, agree=x['agree'], live_only=x['lo'], sim_only=x['so'], size=x['size'], groups=n,
                            sum_daily_gap_pct=float(np.mean(g)), sum_daily_gap_range=[min(g), max(g)], gap_bps_month=float(np.mean(g))*100*30.4375/ndays, days=ndays, rows=x['rows'])
        rep[name] = dict(live_groups=live_groups, arms=out)
        print(f'== {name} daily-reseeded, live groups={live_groups}')
        for arm, o in sorted(out.items()):
            print(f"  {arm:24s} agree={o['agreement_pct']:5.1f}% ({o['agree']}/{o['groups']}) lo={o['live_only']} so={o['sim_only']} size={o['size']} sum-daily-gap={o['sum_daily_gap_pct']:+.2f}% [{o['sum_daily_gap_range'][0]:+.2f},{o['sum_daily_gap_range'][1]:+.2f}] ({o['gap_bps_month']:+.0f}bps/mo)")
    (W/'daily_report.json').write_text(json.dumps(rep, indent=1))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('cmd'); ap.add_argument('window', nargs='?'); ap.add_argument('arm', nargs='?')
    ap.add_argument('--engine', default='new'); a = ap.parse_args()
    if a.cmd == 'fixtures':
        for n in WINDOWS: build_fixture(n)
    elif a.cmd == 'run':
        run(a.window, a.arm, a.engine)
    elif a.cmd == 'compare':
        compare()
    elif a.cmd == 'daily':
        daily(a.window, a.arm.split(','), a.engine)
    elif a.cmd == 'daily-compare':
        daily_compare()


if __name__ == '__main__':
    main()
