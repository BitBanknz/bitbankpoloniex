"""Build the minimal correction from the byte-reproduced deployed release."""
import difflib
import os
from pathlib import Path
import subprocess
import time
from build import REPO,HERE,OUT,QUOTE,read,save,sha,replace

def main():
    baseline=OUT/'release_source_rebuild';assert read(baseline/'verification.json')['byte_identical_to_live']
    out=OUT/'release_candidate';out.mkdir(exist_ok=False);source=out/'source'
    revision=read(baseline/'inputs.json')['revision']
    with (out/'clone.log').open('x') as log:
        subprocess.run(['git','clone','--no-checkout','--local',str(REPO),str(source)],check=True,stdout=log,stderr=subprocess.STDOUT)
        subprocess.run(['git','-C',str(source),'checkout','--detach',revision],check=True,stdout=log,stderr=subprocess.STDOUT)
    original=(source/'internal/bot/engine.go').read_text()
    anchor='\tif ready {\n\t\tfor _, symbol := range ranked {'
    change='''\tif ready {
        for _, symbol := range ranked {
            // Do not undo a capped or blocked protective reduction by buying
            // this holding while its observed price is below the stop.
            if stops[symbol] { continue }'''
    engine=source/'internal/bot/engine.go';engine.write_text(replace(original,anchor,change));subprocess.run(['/usr/local/go/bin/gofmt','-w',str(engine)],check=True)
    (out/'guard.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),engine.read_text().splitlines(True),fromfile='a/internal/bot/engine.go',tofile='b/internal/bot/engine.go')))
    old=read(baseline/'inputs.json')['hashes'];current={name:sha(source/name) for name in old}
    assert [name for name in old if old[name]!=current[name]]==['internal/bot/engine.go']
    save(out/'registration.json',dict(at_ns=time.time_ns(),revision=revision,sources=current,baseline_verification_sha256=sha(baseline/'verification.json'),changed_files=['internal/bot/engine.go'],patch_sha256=sha(out/'guard.patch'),builder_sha256=sha(__file__)))
    env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'};commands=[]
    for label,args in [('suite',['test','./...','-count=1','-json']),('race',['test','-race','./...','-count=1','-json']),('vet',['vet','./...'])]:
        argv=['/usr/local/go/bin/go',*args]
        with (out/(label+'.log')).open('x') as log:p=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
        result=dict(argv=argv,returncode=p.returncode,log_sha256=sha(out/(label+'.log')));save(out/(label+'.json'),result);assert p.returncode==0,label
        commands.append(result);print('RELEASE_GUARD',label,flush=True)
    binary=out/'bitbankpoloniex';argv=['/usr/local/go/bin/go','build','-buildvcs=true','-trimpath','-o',str(binary),'./cmd/bitbankpoloniex']
    with (out/'build.log').open('x') as log:p=subprocess.run(argv,cwd=source,env={**env,'CGO_ENABLED':'0','GOAMD64':'v1'},stdout=log,stderr=subprocess.STDOUT)
    assert p.returncode==0
    save(out/'validation.json',dict(verified=True,at_ns=time.time_ns(),binary_sha256=sha(binary),sources=current,commands=commands,registration_sha256=sha(out/'registration.json'),build_argv=argv,baseline_binary_sha256=sha(baseline/'bitbankpoloniex'),live_changed=False))
    for name,clock in [('observed','observedNow'),('historical','replayNow')]:
        folder=out/name;folder.mkdir();overlay={}
        for filename in ('engine.go','market.go','signals.go','client.go'):
            p=source/'internal/bot'/filename;text=p.read_text().replace('time.Now()',clock+'()')
            if filename=='client.go':
                text=replace(text,'c.mu.Lock()','if private || method != "GET" || !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("release test requires public loopback GET") }; c.mu.Lock()')
                text=replace(text,'delay := time.Until(c.next)','delay := time.Duration(0)')
            target=folder/(filename+'.txt');target.write_text(text);overlay[str(p)]=str(target)
        text=(OUT/name/'driver_test.go.txt').read_text()
        if name=='observed':text=replace(text,' || cfg.MirrorState!=""','')
        target=folder/'driver_test.go.txt';target.write_text(text);overlay[str(source/'internal/bot/release_guard_research_test.go')]=str(target)
        save(folder/'overlay.json',dict(Replace=overlay))
        argv=['/usr/local/go/bin/go','test','-overlay',str(folder/'overlay.json'),'-c','-o',str(folder/'engine.test'),'./internal/bot']
        with (folder/'build.log').open('x') as log:p=subprocess.run(argv,cwd=source,env=env,stdout=log,stderr=subprocess.STDOUT)
        assert p.returncode==0,name
        save(folder/'verification.json',dict(verified=True,hashes={str(p):sha(p) for p in folder.iterdir() if p.is_file()}))
    assert all(sha(source/p)==h for p,h in current.items())
    print('RELEASE_GUARD_BUILT',sha(binary),flush=True)

if __name__=='__main__':main()
