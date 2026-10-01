"""Paper-only signal sidecar: serves the production rank endpoint with a different EMA weight on the raw daily scores.
Read-only on the forecast state; proxies availability and shape from the real endpoint; writes only its own state file."""
import argparse, json, os, tempfile, urllib.request, urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

def load(path):
    try:
        with open(path) as f: return json.load(f)
    except FileNotFoundError: return None

def save(path, obj):
    d = os.path.dirname(path) or '.'
    fd, tmp = tempfile.mkstemp(dir=d); os.close(fd)
    with open(tmp, 'w') as f: json.dump(obj, f)
    os.replace(tmp, path)

def smoothed(forecast, state_path, alpha):
    """EMA state advances once per issued day; first use starts from the production smoothed scores of that day."""
    pairs, h = forecast['pairs'], forecast['issued_hour']
    st = load(state_path)
    if st is None or st['pairs'] != pairs:
        st = dict(pairs=pairs, issued_hour=h, scores=list(map(float, forecast['smoothed_scores'])), alpha=alpha)
        save(state_path, st)
    elif st['issued_hour'] < h:
        if (h - st['issued_hour']) % 24: raise ValueError('forecast progression is not whole days')
        prev = st['scores']
        st = dict(pairs=pairs, issued_hour=h, alpha=alpha,
                  scores=[alpha * r + (1 - alpha) * p for r, p in zip(map(float, forecast['raw_scores']), prev)])
        save(state_path, st)
    elif st['issued_hour'] > h: raise ValueError('forecast moved backwards')
    return dict(zip(pairs, st['scores']))

def make_handler(args):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_GET(self):
            if self.path.split('?')[0] != '/api/trading-bot/rotation-signals':
                self.send_error(404); return
            try:
                with urllib.request.urlopen(args.upstream, timeout=10) as r: code, body = r.status, r.read()
            except urllib.error.HTTPError as e: code, body = e.code, e.read()
            except Exception: self.send_error(502); return
            try:
                data = json.loads(body)
                if code == 200 and data.get('available') is True:
                    fc = load(args.forecast)
                    sm = smoothed(fc, args.state, args.alpha)
                    keys = set(data['rank_scores'])
                    if keys != set(sm): raise ValueError('pair mismatch')
                    data['rank_scores'] = {k: sm[k] for k in data['rank_scores']}
                    body = json.dumps(data).encode()
            except Exception:
                self.send_error(503); return
            self.send_response(code); self.send_header('Content-Type', 'application/json'); self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
    return H

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--port', type=int, default=18746); p.add_argument('--alpha', type=float, default=0.25)
    p.add_argument('--upstream', default='http://127.0.0.1:8745/api/trading-bot/rotation-signals')
    p.add_argument('--forecast', default='/nvme0n1-disk/code/bitbankgo/data/rotation/state/forecast.json')
    p.add_argument('--state', required=True)
    a = p.parse_args()
    ThreadingHTTPServer(('127.0.0.1', a.port), make_handler(a)).serve_forever()
