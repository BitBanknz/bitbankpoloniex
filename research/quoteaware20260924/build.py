"""Build/test an isolated quote-aware native engine without changing production."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

REPO=Path('/vfast/data/code/bitbankpoloniex')
HERE=Path(__file__).resolve().parent
OUT=Path('/vfast/data/trading_research_20260924/poloniex_quote_aware_v1')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,sort_keys=True);f.write('\n')
def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def main():
    OUT.mkdir(exist_ok=False);source=OUT/'source';source.mkdir()
    inputs=[*sorted((REPO/'internal').rglob('*.go')),*sorted((REPO/'cmd').rglob('*.go')),REPO/'go.mod',REPO/'go.sum',Path(__file__),HERE/'selection.go.txt',HERE/'selection_test.go.txt',REPO/'docs/2026-09-24-quote-aware-entry-prereg.md']
    bound={str(p):sha(p) for p in inputs};save(OUT/'registration.json',dict(at_ns=time.time_ns(),hashes=bound))
    for p in inputs:
        if p.suffix=='.go' or p.name in ('go.mod','go.sum'):
            q=source/p.relative_to(REPO);q.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,q)
    p=source/'internal/bot/engine.go';text=p.read_text()
    text=replace(text,'ExperimentalFallback bool','QuoteAwareEntry bool // research-only unheld-target quote eligibility\n\tExperimentalFallback bool')
    text=replace(text,'func (c Config) Validate() error {','func (c Config) Validate() error {\n\tif c.QuoteAwareEntry && (c.Mode != "paper" || c.mirror()) { return errors.New("quote-aware entry experiment requires paper rotation") }')
    text=replace(text,'ranked := Targets(scores, markets, e.Config.Slots)','ranked := Targets(scores, markets, e.Config.Slots)\n\tif e.Config.QuoteAwareEntry && ready { ranked = e.quoteAwareTargets(ctx, scores, markets, s) }')
    p.write_text(text)
    for name in ('selection','selection_test'):shutil.copyfile(HERE/(name+'.go.txt'),source/'internal/bot'/(name+'.go'))
    subprocess.run(['/usr/local/go/bin/gofmt','-w',str(p),str(source/'internal/bot/selection.go'),str(source/'internal/bot/selection_test.go')],check=True)
    changes=[p,source/'internal/bot/selection.go',source/'internal/bot/selection_test.go']
    patch=''.join(''.join(difflib.unified_diff((REPO/p.relative_to(source)).read_text().splitlines(True) if (REPO/p.relative_to(source)).exists() else [],p.read_text().splitlines(True),fromfile='a/'+str(p.relative_to(source)),tofile='b/'+str(p.relative_to(source)))) for p in changes)
    (OUT/'native.patch').write_text(patch)
    sources={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    commands=[]
    for label,args in [('suite',['test','./...','-count=1','-json']),('race',['test','-race','./...','-count=1','-json']),('vet',['vet','./...'])]:
        argv=['/usr/local/go/bin/go',*args]
        with (OUT/(label+'.log')).open('x') as log:r=subprocess.run(argv,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
        receipt=dict(argv=argv,returncode=r.returncode,log_sha256=sha(OUT/(label+'.log')));save(OUT/(label+'.json'),receipt);assert r.returncode==0,(label,OUT/(label+'.log'))
        commands.append(receipt);print('QUOTE_AWARE',label,flush=True)
    assert all(sha(p)==h for p,h in bound.items());assert all(sha(source/p)==h for p,h in sources.items())
    save(OUT/'validation.json',dict(verified=True,at_ns=time.time_ns(),sources=sources,commands=commands,registration_sha256=sha(OUT/'registration.json'),patch_sha256=sha(OUT/'native.patch'),live_changed=False))

if __name__=='__main__':main()
