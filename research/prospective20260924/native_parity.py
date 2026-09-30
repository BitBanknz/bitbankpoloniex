"""Replay recorded public books through unmodified native order sizing (clock overlay)."""
import base64
import gzip
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
BASE=Path('/vfast/data/trading_research_20260924')
MIRROR=BASE/'poloniex_public_retention_first_prefix_v1/mirror'
AUDIT=BASE/'poloniex_public_retention_first_audit_v1'
OUT=BASE/'poloniex_public_quote_native_parity_v1'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    OUT.mkdir(exist_ok=False)
    independent=json.loads((AUDIT/'verification.json').read_text());assert independent['verified']
    cases=[]
    for row in independent['summaries']:
        records=[json.loads(line) for line in gzip.decompress((MIRROR/f"minute_{row['index']:05d}.jsonl.gz").read_bytes()).splitlines()]
        values={r['name']:json.loads(base64.b64decode(r['body_b64'])) for r in records}
        markets={m['symbol']:m for m in values['markets']}
        for expected in row['books']:
            cases.append(dict(Index=row['index'],Now=row['complete_after_ns'],Market=markets[expected['symbol']],Book=values['book_'+expected['symbol']],Expected=expected))
    (OUT/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    source=REPO/'internal/bot/market.go'
    text=source.read_text();assert text.count('time.Now()')==4,text.count('time.Now()')
    (OUT/'market.go.txt').write_text(text.replace('time.Now()','retainedNow()'))
    replacements={str(source):str(OUT/'market.go.txt'),str(REPO/'internal/bot/prospective_quote_test.go'):str(HERE/'quote_parity_test.go.txt')}
    (OUT/'overlay.json').write_text(json.dumps({'Replace':replacements},indent=2)+'\n')
    paths=[*sorted((REPO/'internal/bot').glob('*.go')),REPO/'go.mod',REPO/'go.sum',HERE/'quote_parity_test.go.txt',Path(__file__),AUDIT/'verification.json',AUDIT/'verifier_tests.log',HERE/'test_verify.py']
    bound={str(p):sha(p) for p in paths}
    (OUT/'inputs.json').write_text(json.dumps(dict(at_ns=time.time_ns(),hashes=bound),indent=2)+'\n')
    env={**os.environ,'GOMAXPROCS':'2','RETAINED_QUOTE_CASES':str(OUT/'cases.json')}
    command=['/usr/local/go/bin/go','test','-overlay',str(OUT/'overlay.json'),'./internal/bot','-run','^TestRetainedQuoteFeasibility$','-count=1','-v']
    with (OUT/'native.log').open('xb') as log:result=subprocess.run(command,cwd=REPO,env=env,stdout=log,stderr=subprocess.STDOUT)
    assert result.returncode==0
    for p,h in bound.items():assert sha(Path(p))==h
    log=(OUT/'native.log').read_text();assert log.count('--- PASS: TestRetainedQuoteFeasibility/')==40 and '--- FAIL:' not in log
    report=dict(verified=True,at_ns=time.time_ns(),cases=40,accepted=sum(c['Expected']['quote_feasible'] for c in cases),rejected=sum(not c['Expected']['quote_feasible'] for c in cases),
        native_order_acceptance_price_quantity_amount_equal=True,clock_overlay_only=True,network_used=False,external_orders=False,
        hashes={**bound,**{str(p):sha(p) for p in OUT.iterdir() if p.is_file()}})
    (OUT/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='hashes'}))


if __name__=='__main__':main()
