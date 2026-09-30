"""Own-state control/treatment replay of the fixed authenticated public prefix."""
from decimal import Decimal as D
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

from build import BASE, HERE, OUT, REPO, read, save, sha
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition


def main():
    source=BASE/'poloniex_future_prefix_3297_v1'
    folder=OUT/'observed_accounts';folder.mkdir(exist_ok=False)
    proof=read(source/'completed_v2/audit/verification.json')
    assert proof['verified'] and proof['through_index']==3297
    capture=read(source/'capture.verified.json')
    assert sha(source/'mirror/manifest.json')==capture['manifest_sha256']
    manifest=read(source/'mirror/manifest.json')
    inputs=[Path(__file__),OUT/'observed/engine.test',OUT/'observed/verification.json',
            OUT/'regressions/verification.json',source/'completed_v2/completion.json',
            source/'completed_v2/audit/verification.json',source/'mirror/manifest.json',
            REPO/'research/futurecompare20260926/reference.py']
    hashes={str(p):sha(p) for p in inputs}
    save(folder/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,first_index=78,through_index=3297,
                                       known_no_stop_prefix=True,reused_diagnostic_data=True))
    states={arm:{} for arm in ('control','clock')};stats={arm:{} for arm in states}
    def load(index,suffix):
        name=f'guarded/batch_{index:05d}.{suffix}.json.gz';path=source/'mirror'/name
        assert sha(path)==manifest[name]['sha256'],name
        return json.loads(gzip.decompress(path.read_bytes()))
    temp=Path(tempfile.mkdtemp(prefix='protective-observed-',dir='/dev/shm'))
    previous_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    native=Native(OUT/'observed/engine.test');count=0;paired=0
    try:
        with (folder/'paths.jsonl').open('x') as out:
            for index in range(78,3298):
                packet=load(index,'input')['packet']
                originals={a['ID']:a for a in load(index,'output') if a['ID'].startswith('control_')}
                accounts=[a for a in packet['Accounts'] if a['ID'].startswith('control_')]
                assert len(accounts)==3
                for account in accounts:
                    aid=account['ID'];expected=originals[aid];answers={}
                    assert states['control'].get(aid)==account['Before']
                    for arm in ('control','clock'):
                        before=states[arm].get(aid)
                        request=dict(ID=aid,NowNS=packet['NowNS'],Responses=packet['Responses'],Before=before,
                                     Config={**account['Config'],'ProtectiveActualHour':arm=='clock'})
                        answer=native.apply(request);count+=1
                        money=transition(before,answer['State'],account['Config']['FeeRate'],packet['Responses'],packet['NowNS'],True)
                        for key in ('ID','State','Report','Paused','CycleError'):
                            assert answer[key]==expected[key],(index,arm,aid,key)
                        assert sorted(answer['Paths'])==sorted(expected['Paths']),(index,arm,aid,'Paths')
                        states[arm][aid]=answer['State'];answers[arm]=answer
                        s=stats[arm].setdefault(aid,dict(cycles=0,peak=D(495),dd=D(0),fees=D(0),turnover=D(0),fills=0,unmarked=0))
                        s['cycles']+=1;s['fees']+=D(money['fees']);s['turnover']+=D(money['turnover']);s['fills']+=len(money['new_fills'])
                        if money['equity'] is None:s['unmarked']+=1
                        else:
                            equity=D(money['equity']);s['peak']=max(s['peak'],equity);s['dd']=max(s['dd'],(s['peak']-equity)/s['peak']*100);s['last_equity']=equity
                        out.write(json.dumps(dict(index=index,arm=arm,account=aid,now_ns=packet['NowNS'],**money),sort_keys=True)+'\n')
                    for key in ('ID','State','Report','Paused','CycleError'):assert answers['clock'][key]==answers['control'][key]
                    paired+=1
                if index%200==0:
                    print(json.dumps(dict(index=index,native_cycles=count,paired_cycles=paired)),flush=True)
    finally:
        native.close()
        if previous_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=previous_tmp
        shutil.rmtree(temp)
    assert count==19320 and paired==9660
    summary={}
    for arm,accounts in stats.items():
        summary[arm]={}
        for aid,s in accounts.items():
            s['return_pct']=(s['last_equity']-495)/495*100
            summary[arm][aid]={key:str(value) if isinstance(value,D) else value for key,value in s.items()}
    save(folder/'summary.json',summary);save(folder/'final_states.json',states)
    assert all(sha(path)==h for path,h in hashes.items())
    save(folder/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_cycles=count,paired_cycles=paired,
        first_index=78,through_index=3297,default_off_full_output_parity=True,all_treatment_states_and_financial_outputs_identical=True,
        reused_no_stop_prefix=True,live_changed=False,deployment_qualified=False,
        registration_sha256=sha(folder/'registration.json'),
        output_hashes={name:sha(folder/name) for name in ('paths.jsonl','summary.json','final_states.json')}))
    print(json.dumps(dict(verified=True,native_cycles=count,paired_cycles=paired,all_financial_paths_identical=True)),flush=True)

if __name__=='__main__':main()
