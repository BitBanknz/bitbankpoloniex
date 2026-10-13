"""Paper-only signal sidecar for the hourly-EMA A/B (research arm d_hema). Read-only on bitbankgo's hourly state
(scripts/rotation_hourly_inference.py); writes nothing.
  /api/trading-bot/rotation-signals         daily schema for the unchanged daily consumer: proxies availability/shape
                                            of the real endpoint and replaces rank_scores with the hourly EMA's 00:00 snapshot
  /api/trading-bot/rotation-signals-hourly  current hourly ranks (cadence "hourly", issued every hour), 503 when stale"""
import argparse, json, time, urllib.request, urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


def load(path):
    with open(path) as f: return json.load(f)


def iso(hour): return datetime.fromtimestamp(hour*3600, timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def hour_of(text): return int(datetime.fromisoformat(text.replace('Z', '+00:00')).timestamp())//3600


def daily_body(upstream_json, state):
    data = json.loads(upstream_json)
    if data.get('available') is not True: return data
    issued = hour_of(data['issued_at']); snap = [d for d in state['daily'] if d['issued_hour'] == issued]
    if not snap: raise ValueError('no hourly-EMA snapshot for this daily issue')
    sm = dict(zip(state['pairs'], snap[0]['scores']))
    if set(sm) != set(data['rank_scores']): raise ValueError('pair mismatch')
    data['rank_scores'] = {k: float(sm[k]) for k in data['rank_scores']}
    data['signal_variant'] = 'hourly_ema_0.0178_daily_snapshot'
    return data


def hourly_body(state, now):
    hour = int(now//3600); h = state['issued_hour']
    if state.get('schema') != 'rotation-hourly-forecast-state-v1' or state.get('live_enabled') is not False or not hour-1 <= h <= hour:
        raise ValueError('stale hourly state')
    return dict(available=True, mode='research_rank_forecast', venue='POLONIEX', cadence='hourly', live_orders_enabled=False,
                issued_at=iso(h), execution_hour=iso(h), rank_scores={p: float(v) for p, v in zip(state['pairs'], state['smoothed_scores'])},
                raw_scores={p: float(v) for p, v in zip(state['pairs'], state['raw_scores'])}, observations=state['observations'],
                warning='Rank scores are not expected returns or buy/sell orders. Paper A/B research signal.')


def make_handler(a):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *x): pass

        def reply(self, code, obj):
            body = json.dumps(obj).encode(); self.send_response(code); self.send_header('Content-Type', 'application/json')
            self.send_header('Cache-Control', 'no-store'); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)

        def do_GET(self):
            path = self.path.split('?')[0]
            try:
                if path == '/api/trading-bot/rotation-signals-hourly':
                    return self.reply(200, hourly_body(load(a.state), time.time()))
                if path != '/api/trading-bot/rotation-signals': return self.send_error(404)
                try:
                    with urllib.request.urlopen(a.upstream, timeout=10) as r: code, raw = r.status, r.read()
                except urllib.error.HTTPError as e: code, raw = e.code, e.read()
                if code != 200: return self.reply(code, json.loads(raw))
                return self.reply(200, daily_body(raw, load(a.state)))
            except Exception as e:
                return self.reply(503, dict(available=False, mode='research_rank_forecast', reason=str(e)[:200], live_orders_enabled=False))
    return H


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--port', type=int, default=18748)
    p.add_argument('--upstream', default='http://127.0.0.1:8745/api/trading-bot/rotation-signals')
    p.add_argument('--state', default='/nvme0n1-disk/code/bitbankgo/data/rotation/hourly-state/forecast-hourly.json')
    a = p.parse_args(); ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(a)).serve_forever()
