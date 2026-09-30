"""Reproduce unrelated loopback probes and isolate future research transport."""
import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from capture import HERE,OUT as CAPTURE,sha,save
from audit import Bound,BINARIES
from native import Native

OUT=CAPTURE.parent/'poloniex_driver_trace_isolation_v1'
PARENT=CAPTURE.parent/'poloniex_quote_aware_v1'

def replace(s,a,b):
    assert s.count(a)==1,a
    return s.replace(a,b)

def main():
    OUT.mkdir(exist_ok=False)
    driver=HERE.parents[0]/'quoteaware20260924/driver_test.go.txt';source=PARENT/'source'
    proof=json.loads((PARENT/'validation.json').read_text());assert proof['verified']
    assert all(sha(source/name)==h for name,h in proof['sources'].items())
    original=driver.read_text();overlay=json.loads((PARENT/'driver/candidate/overlay.json').read_text())
    inputs=[Path(__file__),driver,PARENT/'validation.json',PARENT/'driver/verification.json',PARENT/'driver/candidate/overlay.json',CAPTURE/'trace_2062/results.json']
    hashes={str(p):sha(p) for p in inputs};save(OUT/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,live_changed=False))
    binaries={}
    for variant in ('probe_original','isolated'):
        folder=OUT/variant;folder.mkdir();text=original
        text=replace(text,'    ID string\n    NowNS int64','    ID string\n    ProbeRoot bool\n    ProbeKnown bool\n    NowNS int64')
        text=replace(text,'    Paths []string\n','    Paths []string\n    ProbeStatuses []int `json:",omitempty"`\n')
        anchor='    cfg:=DefaultConfig()'
        probes='''    // Synthetic external callers use no engine-specific loopback marker.
    if input.ProbeRoot || input.ProbeKnown {
        paths:=[]string{}
        if input.ProbeRoot { paths=append(paths,"/") }
        if input.ProbeKnown { paths=append(paths,"/markets") }
        for _, path:=range paths {
            probeClient:=&http.Client{Timeout:5*time.Second,CheckRedirect:func(*http.Request,[]*http.Request) error{return errors.New("probe redirect refused")}}
            response,err:=probeClient.Get(server.URL+path)
            if err!=nil { return output,err }
            output.ProbeStatuses=append(output.ProbeStatuses,response.StatusCode)
            io.Copy(io.Discard,response.Body);response.Body.Close()
        }
    }
    cfg:=DefaultConfig()'''
        text=replace(text,anchor,probes)
        if variant=='isolated':
            text=replace(text,'    "context"','    "context"\n    "crypto/rand"\n    "encoding/hex"\n    "strings"')
            text=replace(text,'var observedClock atomic.Int64','''type observedLocalTransport struct { base http.RoundTripper; host, token string }
func (t observedLocalTransport) RoundTrip(request *http.Request) (*http.Response,error) {
    if request.Method!="GET" || request.URL.Scheme!="http" || request.URL.Host!=t.host || request.URL.User!=nil || request.Header.Get("key")!="" || request.Header.Get("Authorization")!="" { return nil,errors.New("research transport requires public local GET") }
    copy:=request.Clone(request.Context());copy.Header=request.Header.Clone()
    copy.Header.Set("X-Paper-Driver-Cycle",t.token)
    return t.base.RoundTrip(copy)
}
var observedClock atomic.Int64''')
            text=replace(text,'    requests:=make(chan string,100)','''    nonce:=make([]byte,32)
    if _,err:=rand.Read(nonce);err!=nil{return output,err}
    token:=hex.EncodeToString(nonce)
    requests:=make(chan string,100)''')
            text=replace(text,'        requests<-r.URL.Path','        if r.Header.Get("X-Paper-Driver-Cycle")!=token { http.Error(w,"unrelated request",403);return }\n        requests<-r.URL.Path')
            text=replace(text,'    engine:=Engine{Config:cfg,Client:client}','''    transport:=observedLocalTransport{base:http.DefaultTransport,host:strings.TrimPrefix(server.URL,"http://"),token:token}
    client.HTTP.Transport=transport
    previousTransport:=predClient.Transport;predClient.Transport=transport
    defer func(){predClient.Transport=previousTransport}()
    engine:=Engine{Config:cfg,Client:client}''')
        file=folder/'driver_test.go.txt';file.write_text(text)
        subprocess.run(['/usr/local/go/bin/gofmt','-w',str(file)],check=True)
        copied={'Replace':dict(overlay['Replace'])};target=str(source/'internal/bot/observed_cycle_research_test.go');copied['Replace'][target]=str(file)
        save(folder/'overlay.json',copied);binary=folder/'engine.test'
        args=['/usr/local/go/bin/go','test','-overlay',str(folder/'overlay.json'),'-c','-o',str(binary),'./internal/bot']
        with (folder/'build.log').open('x') as log:r=subprocess.run(args,cwd=source,env={**os.environ,'GOMAXPROCS':'2','GOWORK':'off','GOFLAGS':'-mod=readonly','GOPROXY':'off','GOSUMDB':'off'},stdout=log,stderr=subprocess.STDOUT)
        save(folder/'build.json',dict(argv=args,returncode=r.returncode,binary_sha256=sha(binary) if binary.exists() else None));assert r.returncode==0,variant
        binaries[variant]=binary
    bound=Bound();packet=bound.gz('unguarded/batch_02062.input.json.gz')['packet'];expected=bound.gz('unguarded/batch_02062.output.json.gz')[1]
    request={**packet['Accounts'][1],'NowNS':packet['NowNS'],'Responses':packet['Responses']}
    cases=[json.loads(line) for line in gzip.decompress((PARENT/'paired_replay_v2/cycles.jsonl.gz').read_bytes()).splitlines()]
    temp=Path(tempfile.mkdtemp(prefix='polo-trace-check-',dir='/dev/shm'));prior_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    results=[]
    try:
        for variant,binary in binaries.items():
            native=Native(binary)
            try:
                for case in cases:
                    answer=native.apply(case['input']);wanted=case['output']
                    for k in ('ID','State','Report','Paused','CycleError'):assert answer[k]==wanted[k],(variant,case['input']['ID'],k)
                    assert sorted(answer['Paths'])==sorted(wanted['Paths'])
                for probe in ('none','root','known'):
                    answer=native.apply({**request,'ProbeRoot':probe=='root','ProbeKnown':probe=='known'})
                    for k in ('ID','State','Report','Paused','CycleError'):assert answer[k]==expected[k],(variant,probe,k)
                    actual=sorted(answer['Paths']);clean=sorted(p for p in expected['Paths'] if p!='/')
                    if variant=='probe_original':
                        wanted=sorted(clean+(['/'] if probe=='root' else ['/markets'] if probe=='known' else []))
                        assert actual==wanted and answer.get('ProbeStatuses',[])==([] if probe=='none' else [503] if probe=='root' else [200])
                        if probe=='root':assert actual==sorted(expected['Paths'])
                    else:
                        assert actual==clean and answer.get('ProbeStatuses',[])==([] if probe=='none' else [403])
                    name=f'{variant}_{probe}.json';save(OUT/name,answer)
                    results.append(dict(variant=variant,probe=probe,paths=answer['Paths'],probe_statuses=answer.get('ProbeStatuses',[]),financial_outputs_exact=True))
            finally:native.close()
    finally:
        if prior_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=prior_tmp
        shutil.rmtree(temp)
    assert all(sha(path)==h for path,h in hashes.items())
    assert all(sha(source/name)==h for name,h in proof['sources'].items())
    save(OUT/'verification.json',dict(verified=True,at_ns=time.time_ns(),source_engine_unchanged=True,historical_native_cases_per_variant=len(cases),
        controlled_probe_results=results,recorded_root_trace_reproduced=True,probe_origin_in_original_recording_unknown=True,
        isolated_driver_blocks_unrelated_requests=True,all_financial_fields_exact=True,live_changed=False,existing_studies_changed=False,
        input_hashes=hashes,artifact_hashes={str(p.relative_to(OUT)):sha(p) for p in OUT.rglob('*') if p.is_file()}))
    print(json.dumps(dict(verified=True,native_cases_per_variant=len(cases),recorded_root_trace_reproduced=True,isolated_probe_status=403,all_financial_fields_exact=True)),flush=True)

if __name__=='__main__':main()
