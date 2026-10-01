import json, os, tempfile, threading, urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import ema_sidecar as S
d = tempfile.mkdtemp(); fc = os.path.join(d, 'forecast.json'); st = os.path.join(d, 'state.json')
pairs = ['BNBUSDT', 'ETHUSDT']
S.save(fc, dict(pairs=pairs, issued_hour=24, raw_scores=[1.0, -1.0], smoothed_scores=[0.5, -0.5]))
class Up(BaseHTTPRequestHandler):
    avail = True
    def log_message(self, *a): pass
    def do_GET(self):
        body = json.dumps(dict(available=Up.avail, venue='POLONIEX', mode='research_rank_forecast', issued_at='x', execution_hour='y', rank_scores={'BNBUSDT': 9, 'ETHUSDT': 9}) if Up.avail else dict(available=False)).encode()
        self.send_response(200 if Up.avail else 503); self.send_header('Content-Length', str(len(body))); self.end_headers(); self.wfile.write(body)
up = HTTPServer(('127.0.0.1', 0), Up); threading.Thread(target=up.serve_forever, daemon=True).start()
class A: pass
a = A(); a.upstream = f'http://127.0.0.1:{up.server_port}/x'; a.forecast = fc; a.state = st; a.alpha = 0.25
sv = ThreadingHTTPServer(('127.0.0.1', 0), S.make_handler(a)); threading.Thread(target=sv.serve_forever, daemon=True).start()
def get():
    try:
        with urllib.request.urlopen(f'http://127.0.0.1:{sv.server_port}/api/trading-bot/rotation-signals') as r: return r.status, json.load(r)
    except urllib.error.HTTPError as e: return e.code, None
c, j = get(); assert c == 200 and j['rank_scores'] == {'BNBUSDT': 0.5, 'ETHUSDT': -0.5}, (c, j)   # first day: production smoothed
c, j = get(); assert j['rank_scores'] == {'BNBUSDT': 0.5, 'ETHUSDT': -0.5}                        # idempotent within a day
S.save(fc, dict(pairs=pairs, issued_hour=48, raw_scores=[-1.0, 1.0], smoothed_scores=[0, 0]))
c, j = get(); assert abs(j['rank_scores']['BNBUSDT'] - (0.25 * -1.0 + 0.75 * 0.5)) < 1e-12 and abs(j['rank_scores']['ETHUSDT'] + (0.25 * -1.0 + 0.75 * 0.5)) < 1e-12, j
Up.avail = False
c, j = get(); assert c == 503                                                                      # availability is proxied
S.save(fc, dict(pairs=pairs, issued_hour=24, raw_scores=[0, 0], smoothed_scores=[0, 0])); Up.avail = True
c, j = get(); assert c == 503                                                                      # backwards forecast refused
print('ok')
