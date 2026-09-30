"""Own-state three-arm replay of the fixed authenticated public-book prefix."""
from decimal import Decimal as D
import gzip
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
from build import BASE,HERE,OUT,REPO,ARMS,read,save,sha
from checks_v2 import causal,daily_budget
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition


def main():
    source=BASE/'poloniex_future_prefix_3297_v1'
    folder=OUT/'observed_accounts';folder.mkdir(exist_ok=False)
    proof=read(source/'completed_v2/audit/verification.json')
    assert proof['verified'] and proof['through_index']==3297
    assert read(OUT/'regressions_v3/verification.json')['verified']
    capture=read(source/'capture.verified.json')
    assert sha(source/'mirror/manifest.json')==capture['manifest_sha256']
    manifest=read(source/'mirror/manifest.json')
    inputs=[Path(__file__),HERE/'checks_v2.py',OUT/'observed/engine.test',OUT/'observed/verification.json',
            OUT/'regressions_v3/verification.json',source/'completed_v2/completion.json',
            source/'completed_v2/audit/verification.json',source/'mirror/manifest.json',
            REPO/'research/futurecompare20260926/reference.py']
    hashes={str(p):sha(p) for p in inputs}
    save(folder/'registration.json',dict(at_ns=time.time_ns(),hashes=hashes,first_index=78,through_index=3297,
                                       arms=ARMS,known_no_stop_prefix=True,reused_diagnostic_data=True))
    states={arm:{} for arm in ARMS};stats={arm:{} for arm in ARMS}

    def load(index,suffix):
        name=f'guarded/batch_{index:05d}.{suffix}.json.gz';path=source/'mirror'/name
        assert sha(path)==manifest[name]['sha256'],name
        return json.loads(gzip.decompress(path.read_bytes()))

    temp=Path(tempfile.mkdtemp(prefix='exit-reserve-observed-',dir='/dev/shm'))
    old_tmp=os.environ.get('TMPDIR');os.environ['TMPDIR']=str(temp)
    native=Native(OUT/'observed/engine.test');count=0;paired=0
    try:
        with (folder/'paths.jsonl').open('x') as out:
            for index in range(78,3298):
                packet=load(index,'input')['packet']
                originals={a['ID']:a for a in load(index,'output') if a['ID'].startswith('control_')}
                accounts=[a for a in packet['Accounts'] if a['ID'].startswith('control_')]
                assert len(accounts)==3
                for account in accounts:
                    aid=account['ID'];answers={}
                    assert states['baseline'].get(aid)==account['Before']
                    for arm,(maximum,reserve) in ARMS.items():
                        before=states[arm].get(aid)
                        config={**account['Config'],'MaxOrdersDay':maximum,'ExitOrderReserve':reserve}
                        request=dict(ID=aid,NowNS=packet['NowNS'],Responses=packet['Responses'],Before=before,Config=config)
                        causal(before,packet['NowNS'])
                        answer=native.apply(request);count+=1;causal(answer['State'],packet['NowNS'])
                        money=transition(before,answer['State'],config['FeeRate'],packet['Responses'],packet['NowNS'],True)
                        budget=daily_budget(before,answer['State'],config,packet['NowNS'])
                        if arm=='baseline':
                            expected=originals[aid]
                            for key in ('ID','State','Report','Paused','CycleError'):assert answer[key]==expected[key],(index,aid,key)
                            assert sorted(answer['Paths'])==sorted(expected['Paths']),(index,aid,'Paths')
                        states[arm][aid]=answer['State'];answers[arm]=answer
                        stat=stats[arm].setdefault(aid,dict(cycles=0,peak=D(495),dd=D(0),fees=D(0),turnover=D(0),
                                                         buys=0,sells=0,unmarked=0))
                        stat['cycles']+=1;stat['fees']+=D(money['fees']);stat['turnover']+=D(money['turnover'])
                        stat['buys']+=sum(f['Order']['side']=='BUY' for f in money['new_fills'])
                        stat['sells']+=sum(f['Order']['side']=='SELL' for f in money['new_fills'])
                        if money['equity'] is None:stat['unmarked']+=1
                        else:
                            equity=D(money['equity']);stat['peak']=max(stat['peak'],equity)
                            stat['dd']=max(stat['dd'],(stat['peak']-equity)/stat['peak']*100);stat['last_equity']=equity
                        out.write(json.dumps(dict(index=index,arm=arm,account=aid,now_ns=packet['NowNS'],
                                                 budget=budget,**money),sort_keys=True)+'\n')
                    # This previously observed prefix has no stops. Check the
                    # hypothesis that only the buying restriction is exercised.
                    for key in ('ID','State','Report','Paused','CycleError'):
                        assert answers['reserve3'][key]==answers['cap9'][key],(index,aid,key)
                    paired+=1
                if index%300==0:
                    print('EXIT_RESERVE_OBSERVED',index,count,flush=True)
    finally:
        native.close()
        if old_tmp is None:os.environ.pop('TMPDIR',None)
        else:os.environ['TMPDIR']=old_tmp
        shutil.rmtree(temp)
    assert count==28980 and paired==9660
    summary={}
    for arm,accounts in stats.items():
        summary[arm]={}
        for aid,stat in accounts.items():
            stat['return_pct']=(stat['last_equity']-495)/495*100
            summary[arm][aid]={k:str(v) if isinstance(v,D) else v for k,v in stat.items()}
    save(folder/'summary.json',summary);save(folder/'final_states.json',states)
    assert all(sha(p)==digest for p,digest in hashes.items())
    save(folder/'verification.json',dict(verified=True,at_ns=time.time_ns(),native_cycles=count,
        matched_control_comparisons=paired,first_index=78,through_index=3297,
        baseline_full_output_parity=True,candidate_and_nine_order_control_financial_paths_identical=True,
        exact_clock_causality=True,daily_buy_and_total_budgets_checked=True,reused_no_stop_prefix=True,
        live_changed=False,deployment_qualified=False,registration_sha256=sha(folder/'registration.json'),
        output_hashes={name:sha(folder/name) for name in ('paths.jsonl','summary.json','final_states.json')}))
    print('EXIT_RESERVE_OBSERVED_VERIFIED',count,flush=True)


if __name__=='__main__':main()
