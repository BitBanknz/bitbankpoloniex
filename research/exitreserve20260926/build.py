"""Private exit-reserve treatment built from the exact guarded release."""
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = Path('/vfast/data/trading_research_20260924')
PARENT = BASE / 'poloniex_stop_topup_guard_v1/release_candidate'
OUT = BASE / 'poloniex_exit_reserve_v1'
GO_ROOT = Path('/home/lee/go/pkg/mod/golang.org/toolchain@v0.0.1-go1.25.0.linux-amd64')
ENV = {**os.environ, 'GOROOT':str(GO_ROOT), 'GOTOOLCHAIN':'local', 'GOMAXPROCS':'2',
       'GOWORK':'off', 'GOFLAGS':'-mod=readonly', 'GOPROXY':'off', 'GOSUMDB':'off'}
ARMS = {'baseline':(12,0), 'cap9':(9,0), 'reserve3':(12,3)}


def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda:f.read(1<<20),b''):h.update(data)
    return h.hexdigest()


def read(path):return json.loads(Path(path).read_text())


def save(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2,sort_keys=True,allow_nan=False);f.write('\n')


def replace(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)


def command(label,args,cwd):
    path=OUT/(label+'.log');argv=[str(GO_ROOT/'bin/go'),*args]
    with path.open('x') as log:
        result=subprocess.run(argv,cwd=cwd,env=ENV,stdout=log,stderr=subprocess.STDOUT)
    save(OUT/(label+'.json'),dict(argv=argv,returncode=result.returncode,log_sha256=sha(path)))
    assert result.returncode==0,label
    print('EXIT_RESERVE',label,flush=True)


def main():
    proof=read(PARENT/'validation.json');assert proof['verified']
    assert all(sha(PARENT/'source'/name)==digest for name,digest in proof['sources'].items())
    OUT.mkdir(exist_ok=False)
    isolated=BASE/'poloniex_driver_trace_isolation_v3'
    assert read(isolated/'verification.json')['verified'] and read(isolated/'race/verification.json')['verified']
    inputs=[Path(__file__),HERE/'config_test.go.txt',REPO/'docs/2026-09-26-exit-order-reserve-prereg.md',
            PARENT/'validation.json',PARENT/'parity/verification.json',PARENT/'historical/driver_test.go.txt',
            isolated/'verification.json',isolated/'race/verification.json',isolated/'isolated/driver_test.go.txt']
    save(OUT/'registration.json',dict(at_ns=time.time_ns(),hashes={str(p):sha(p) for p in inputs},arms=ARMS,live_changed=False))
    source=OUT/'source';source.mkdir()
    for name in proof['sources']:
        target=source/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(PARENT/'source'/name,target)
    engine=source/'internal/bot/engine.go';original=engine.read_text()
    text=replace(original,'type Config struct {','type Config struct {\n\tExitOrderReserve int // private paper research; defaults off')
    text=replace(text,'func (c Config) Validate() error {','''func (c Config) Validate() error {
    if c.ExitOrderReserve < 0 || c.ExitOrderReserve > c.MaxOrdersDay {
        return errors.New("exit order reserve must be within the daily allowance")
    }
    if c.ExitOrderReserve > 0 && (c.Mode != "paper" || c.ExperimentalFallback) {
        return errors.New("exit order reservation requires paper rotation")
    }''')
    text=replace(text,'\tif s.Processed[key] || s.OrdersToday >= e.Config.MaxOrdersDay {\n\t\treturn nil\n\t}',
        '''    if s.Processed[key] || s.OrdersToday >= e.Config.MaxOrdersDay {
        return nil
    }
    if side == "BUY" && e.Config.ExitOrderReserve > 0 && s.OrdersToday >= e.Config.MaxOrdersDay-e.Config.ExitOrderReserve {
        return nil
    }''')
    engine.write_text(text)
    test=source/'internal/bot/exit_reserve_test.go';shutil.copyfile(HERE/'config_test.go.txt',test)
    subprocess.run([str(GO_ROOT/'bin/gofmt'),'-w',str(engine),str(test)],check=True)
    (OUT/'treatment.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),engine.read_text().splitlines(True),fromfile='a/internal/bot/engine.go',tofile='b/internal/bot/engine.go')))
    sources={str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()}
    for label,args in [('suite',['test','./...','-count=1','-json']),('race',['test','-race','./...','-count=1','-json']),('vet',['vet','./...'])]:
        command(label,args,source)
    save(OUT/'validation.json',dict(verified=True,at_ns=time.time_ns(),sources=sources,parent_sha256=sha(PARENT/'validation.json')))
    for name,clock in [('observed','observedNow'),('historical','replayNow')]:
        folder=OUT/name;folder.mkdir();overlay={}
        for filename in ('engine.go','market.go','signals.go','client.go'):
            p=source/'internal/bot'/filename;text=p.read_text().replace('time.Now()',clock+'()')
            if filename=='client.go':
                text=replace(text,'c.mu.Lock()','if private || method != "GET" || !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research requires public loopback GET") }; c.mu.Lock()')
                text=replace(text,'delay := time.Until(c.next)','delay := time.Duration(0)')
            target=folder/(filename+'.txt');target.write_text(text);overlay[str(p)]=str(target)
        if name=='observed':
            text=replace((isolated/'isolated/driver_test.go.txt').read_text(),' || cfg.MirrorState != ""','')
        else:
            text=(PARENT/'historical/driver_test.go.txt').read_text()
            text=replace(text,'\tlog.SetOutput(io.Discard)','''    log.SetOutput(io.Discard)
    arm := os.Getenv("RESEARCH_ARM")
    if arm != "baseline" && arm != "cap9" && arm != "reserve3" { t.Fatal("explicit research arm required") }''')
            text=replace(text,'cfg := DefaultConfig()','''cfg := DefaultConfig()
                    if arm == "cap9" { cfg.MaxOrdersDay = 9 }
                    if arm == "reserve3" { cfg.ExitOrderReserve = 3 }''')
        driver=folder/'driver_test.go.txt';driver.write_text(text)
        overlay[str(source/'internal/bot/exit_reserve_driver_test.go')]=str(driver)
        save(folder/'overlay.json',dict(Replace=overlay))
        command(name+'_build',['test','-overlay',str(folder/'overlay.json'),'-c','-o',str(folder/'engine.test'),'./internal/bot'],source)
        if name=='observed':command(name+'_race_build',['test','-race','-overlay',str(folder/'overlay.json'),'-c','-o',str(folder/'engine_race.test'),'./internal/bot'],source)
        save(folder/'verification.json',dict(verified=True,hashes={str(p):sha(p) for p in folder.iterdir() if p.is_file()}))
    assert all(sha(source/name)==digest for name,digest in sources.items())
    print('EXIT_RESERVE_BUILT',flush=True)


if __name__=='__main__':main()
