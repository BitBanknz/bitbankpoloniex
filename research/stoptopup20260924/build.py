"""Qualify an entry guard after protective stops in isolated native source."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

REPO=Path('/vfast/data/code/bitbankpoloniex')
HERE=Path(__file__).resolve().parent
BASE=Path('/vfast/data/trading_research_20260924')
QUOTE=BASE/'poloniex_quote_aware_v1'
OLD=BASE/'poloniex_topup_deadband_v1'
OUT=BASE/'poloniex_stop_topup_guard_v1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def main():
    validation=read(QUOTE/'validation.json');assert validation['verified']
    assert all(sha(QUOTE/'source'/p)==h for p,h in validation['sources'].items())
    OUT.mkdir(exist_ok=False);source=OUT/'source'
    inputs=[Path(__file__),REPO/'docs/2026-09-24-stop-topup-guard-prereg.md',QUOTE/'validation.json',QUOTE/'stop_refill_probe_v2/verification.json',OLD/'replay/replay_test.go.txt',REPO/'research/quoteaware20260924/driver_test.go.txt']
    save(OUT/'registration.json',dict(at_ns=time.time_ns(),hashes={str(p):sha(p) for p in inputs}))
    shutil.copytree(QUOTE/'source',source)
    engine=source/'internal/bot/engine.go';old=engine.read_text()
    anchor='\tif ready {\n\t\tfor _, symbol := range ranked {'
    guard='''\tif ready {
        for _, symbol := range ranked {
            // A capped or blocked protective reduction must not be undone by
            // the entry/top-up pass while this holding is below its stop.
            if stops[symbol] { continue }'''
    engine.write_text(replace(old,anchor,guard));subprocess.run(['/usr/local/go/bin/gofmt','-w',str(engine)],check=True)
    (OUT/'research_guard.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),engine.read_text().splitlines(True),fromfile='a/internal/bot/engine.go',tofile='b/internal/bot/engine.go')))
    production=(REPO/'internal/bot/engine.go').read_text();patched=replace(production,anchor,guard)
    path=OUT/'production_engine.go.txt';path.write_text(patched);subprocess.run(['/usr/local/go/bin/gofmt','-w',str(path)],check=True)
    (OUT/'production_guard.patch').write_text(''.join(difflib.unified_diff(production.splitlines(True),path.read_text().splitlines(True),fromfile='a/internal/bot/engine.go',tofile='b/internal/bot/engine.go')))
    sources={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    commands=[]
    for label,args in [('suite',['test','./...','-count=1','-json']),('race',['test','-race','./...','-count=1','-json']),('vet',['vet','./...'])]:
        argv=['/usr/local/go/bin/go',*args]
        with (OUT/(label+'.log')).open('x') as log:r=subprocess.run(argv,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
        proof=dict(argv=argv,returncode=r.returncode,log_sha256=sha(OUT/(label+'.log')));save(OUT/(label+'.json'),proof);assert r.returncode==0,label
        commands.append(proof);print('STOP_GUARD',label,flush=True)
    save(OUT/'validation.json',dict(verified=True,at_ns=time.time_ns(),sources=sources,commands=commands,production_source_sha256=sha(REPO/'internal/bot/engine.go'),production_patch_sha256=sha(OUT/'production_guard.patch'),live_changed=False))
    for name,clock,template in [('observed','observedNow',REPO/'research/quoteaware20260924/driver_test.go.txt'),('historical','replayNow',OLD/'replay/replay_test.go.txt')]:
        folder=OUT/name;folder.mkdir();overlay={}
        for filename in ('engine.go','market.go','signals.go','client.go'):
            p=source/'internal/bot'/filename;text=p.read_text().replace('time.Now()',clock+'()')
            if filename=='client.go':
                text=replace(text,'c.mu.Lock()','if private || method != "GET" || !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research requires public loopback GET") }; c.mu.Lock()')
                text=replace(text,'delay := time.Until(c.next)','delay := time.Duration(0)')
            target=folder/(filename+'.txt');target.write_text(text);overlay[str(p)]=str(target)
        text=template.read_text()
        if name=='historical':
            text,n=re.subn(r'\n\s*if bonus == 2 \{\n\s*cfg\.SlotTopUpGapFraction = \.25\n\s*\}','',text);assert n==1
            text=replace(text,'selectedVariant < 0 || selectedVariant > 2','selectedVariant != 1')
        target=folder/'driver_test.go.txt';target.write_text(text);overlay[str(source/'internal/bot/stop_guard_research_test.go')]=str(target)
        save(folder/'overlay.json',dict(Replace=overlay));binary=folder/'engine.test'
        argv=['/usr/local/go/bin/go','test','-overlay',str(folder/'overlay.json'),'-c','-o',str(binary),'./internal/bot']
        with (folder/'build.log').open('x') as log:r=subprocess.run(argv,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
        assert r.returncode==0,folder
        save(folder/'verification.json',dict(verified=True,hashes={str(p):sha(p) for p in folder.iterdir() if p.is_file()},binary_sha256=sha(binary)))
    assert all(sha(source/p)==h for p,h in sources.items())
    print('STOP_GUARD_DRIVERS_BUILT',flush=True)

if __name__=='__main__':main()
