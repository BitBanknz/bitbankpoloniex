"""Build private treatment and original-control receipt replay executables."""
import os
from pathlib import Path
import subprocess
from build import HERE,OUT,REPO,replace,save,sha
import json

def main():
    validation=json.loads((OUT/'validation.json').read_text());assert validation['verified']
    registration=json.loads((OUT/'registration.json').read_text())['hashes']
    assert all(sha(p)==h for p,h in registration.items())
    assert all(sha(OUT/'source'/p)==h for p,h in validation['sources'].items())
    out=OUT/'driver';out.mkdir(exist_ok=False)
    inputs={str(OUT/'validation.json'):sha(OUT/'validation.json'),str(HERE/'driver_test.go.txt'):sha(HERE/'driver_test.go.txt'),str(Path(__file__)):sha(__file__)}
    binaries={}
    for name,source in [('candidate',OUT/'source'),('original',REPO)]:
        folder=out/name;folder.mkdir();overlay={}
        for filename in ('engine.go','market.go','signals.go','client.go'):
            original=source/'internal/bot'/filename;text=original.read_text();inputs[str(original)]=sha(original)
            text=text.replace('time.Now()','observedNow()')
            if filename=='client.go':
                text=replace(text,'c.mu.Lock()','if private || method != "GET" || !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research driver requires public loopback GET") }; c.mu.Lock()')
                text=replace(text,'delay := time.Until(c.next)','delay := time.Duration(0)')
            target=folder/(filename+'.txt');target.write_text(text);overlay[str(original)]=str(target)
        overlay[str(source/'internal/bot/observed_cycle_research_test.go')]=str(HERE/'driver_test.go.txt')
        save(folder/'overlay.json',dict(Replace=overlay))
        binary=folder/'observed_cycle.test'
        argv=['/usr/local/go/bin/go','test','-overlay',str(folder/'overlay.json'),'-c','-o',str(binary),'./internal/bot']
        with (folder/'build.log').open('x') as log:p=subprocess.run(argv,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
        save(folder/'build.json',dict(argv=argv,returncode=p.returncode));assert p.returncode==0,folder
        for p in folder.iterdir():
            if p.is_file():inputs[str(p)]=sha(p)
        binaries[name]=str(binary)
    assert all(sha(p)==h for p,h in inputs.items())
    assert all(sha(p)==h for p,h in registration.items())
    save(out/'verification.json',dict(verified=True,binaries=binaries,hashes=inputs,public_loopback_only=True,live_changed=False))
    print('DRIVERS_BUILT',flush=True)

if __name__=='__main__':main()
