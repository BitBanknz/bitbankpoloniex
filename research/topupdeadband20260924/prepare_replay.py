"""Bind an instrumented loopback-only replay and all fixed case definitions."""
import os
from pathlib import Path
import subprocess
from build import ROOT,HERE,OUT,read,save,sha,replace


def main():
    source=OUT/'source'
    validation=read(OUT/'validation.json');assert validation['verified']
    assert all(sha(source/p)==h for p,h in validation['sources'].items())
    replay=OUT/'replay';replay.mkdir(exist_ok=False)
    overlays={};inputs={str(OUT/'validation.json'):sha(OUT/'validation.json')}
    for name in ('engine.go','market.go','signals.go','client.go'):
        path=source/'internal/bot'/name
        text=path.read_text().replace('time.Now()','replayNow()')
        if name=='client.go':
            text=replace(text,'c.mu.Lock()','if !strings.HasPrefix(c.BaseURL, "http://127.0.0.1:") { return errors.New("research client requires loopback") }; c.mu.Lock()')
            text=replace(text,'delay := time.Until(c.next)','delay := time.Duration(0)')
        target=replay/(name+'.txt');target.write_text(text)
        overlays[str(path)]=str(target);inputs[str(path)]=sha(path)
    old=Path('/tmp/claude-1000/topup0924/replay_test.go.txt')
    text=old.read_text()
    text=replace(text,' "context"',' "context"\n "io"\n "log"')
    text=replace(text,'func TestFrozenLedgerReplay(t *testing.T) {','''func TestFrozenLedgerReplay(t *testing.T) {
 log.SetOutput(io.Discard)
 integer:=func(name string) int {v,e:=strconv.Atoi(os.Getenv(name));if e!=nil {t.Fatal(name,e)};return v}
 selectedDays,selectedVariant:=integer("RESEARCH_DAYS"),integer("RESEARCH_VARIANT")
 cooldown,windowCycles:=integer("RESEARCH_COOLDOWN"),integer("RESEARCH_CYCLES")
 selectedFee,feeErr:=strconv.ParseFloat(os.Getenv("RESEARCH_FEE"),64);if feeErr!=nil {t.Fatal(feeErr)}
 if (selectedDays!=0 && selectedDays!=28 && selectedDays!=56) || selectedVariant<0 || selectedVariant>2 || (cooldown!=72 && cooldown!=120) || (windowCycles!=12 && windowCycles!=60) || (selectedFee!=.003 && selectedFee!=.004 && selectedFee!=.006) {t.Fatal("unregistered replay setting")}
''')
    text=replace(text,'range []int{0,28,56}','range []int{selectedDays}')
    text=replace(text,'range []float64{.003,.004}','range []float64{selectedFee}')
    text=replace(text,'range []float64{0,1}','range []float64{float64(selectedVariant)}')
    text=replace(text,'cfg:=DefaultConfig();cfg.SlotTopUp=bonus>0;','cfg:=DefaultConfig();cfg.CooldownHours=cooldown;if bonus==2 {cfg.SlotTopUpGapFraction=.25};cfg.SlotTopUp=bonus>0;')
    text=replace(text,'cycles=12','cycles=windowCycles')
    text=replace(text,'os.O_CREATE|os.O_WRONLY|os.O_TRUNC','os.O_CREATE|os.O_WRONLY|os.O_EXCL')
    oldblock='''    row:=struct{Days int; Fee,SlotTopUp float64; Start,End int64; Report Report; Paused,HaltCycles int; Dust map[string]string}{days,fee,bonus,f.Hours[a].TS,f.Hours[b-1].TS,report,paused,halts,dust}'''
    newblock='''    ledgerName:=fmt.Sprintf("ledger_days%d_fee%g_bonus%g_start%d.json",days,fee,bonus,f.Hours[a].TS)
    raw,marshalErr:=json.MarshalIndent(s,"","  ");if marshalErr!=nil {t.Fatal(marshalErr)}
    if err:=os.WriteFile(filepath.Join(filepath.Dir(outPath),ledgerName),raw,0644);err!=nil {t.Fatal(err)}
    row:=struct{Days int; Fee,SlotTopUp float64; Start,End int64; Report Report; Paused,HaltCycles int; Dust map[string]string;Ledger string;Cooldown,WindowCycles int}{days,fee,bonus,f.Hours[a].TS,f.Hours[b-1].TS,report,paused,halts,dust,ledgerName,cooldown,windowCycles}'''
    text=replace(text,oldblock,newblock)
    oldline='''    if days==0 {raw,_:=json.MarshalIndent(s,"","  ");name:=fmt.Sprintf("ledger_fee%g_bonus%g.json",fee,bonus);if err:=os.WriteFile(filepath.Join(filepath.Dir(outPath),name),raw,0644);err!=nil {t.Fatal(err)}}'''
    text=replace(text,oldline,'')
    target=replay/'replay_test.go.txt';target.write_text(text)
    overlays[str(source/'internal/bot/frozen_ledger_research_test.go')]=str(target)
    save(replay/'overlay.json',dict(Replace=overlays))
    subprocess.run(['gofmt','-w',*overlays.values()],check=True)
    for p in (*map(Path,overlays.values()),old,Path(__file__),HERE/'build.py',replay/'overlay.json',ROOT/'data/frontier_20260912/ledger/fixture.json',ROOT/'data/frontier_20260912/ledger/markets.json'):
        inputs[str(p)]=sha(p)
    cases=[]
    for phase,cd,cycles in (('parity',72,12),('corrected',120,60)):
        for days in ((0,) if phase=='parity' else (0,28,56)):
            for fee in ((.003,.004) if phase=='parity' else (.003,.004,.006)):
                for variant in ((0,1) if phase=='parity' else (0,1,2)):
                    cases.append(dict(id=f'{phase}_days{days}_fee{fee}_arm{variant}',phase=phase,days=days,fee=fee,variant=variant,cooldown=cd,cycles=cycles))
    save(replay/'cases.json',cases);inputs[str(replay/'cases.json')]=sha(replay/'cases.json')
    save(replay/'inputs.json',inputs)
    argv=['go','test','-overlay',str(replay/'overlay.json'),'-c','-o',str(replay/'engine_replay.test'),'./internal/bot']
    with (replay/'build.log').open('x') as log:
        p=subprocess.run(argv,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly'},stdout=log,stderr=subprocess.STDOUT)
    save(replay/'build.json',dict(argv=argv,returncode=p.returncode,log_sha256=sha(replay/'build.log')));assert p.returncode==0
    assert all(sha(p)==h for p,h in inputs.items())
    save(replay/'verification.json',dict(verified=True,binary_sha256=sha(replay/'engine_replay.test'),inputs_sha256=sha(replay/'inputs.json'),cases=len(cases),live_changed=False))
    print('REPLAY_BUILT',len(cases),flush=True)


if __name__=='__main__':main()
