"""Synthetic regression discovery: a capped stop on a topped-up holding."""
from copy import deepcopy
import time
from replay_v2 import Native,synthetic,config,money
from build import OUT,save,sha

def main():
    output=OUT/'stop_refill_probe_v2';output.mkdir(exist_ok=False)
    worker=Native(OUT/'driver/candidate/observed_cycle.test');rows=[]
    try:
        for aware in (False,True):
            now,responses=synthetic()
            before=worker.apply(dict(ID='initialize',NowNS=now,Config=config(aware,'.003'),Before=None,Responses={**responses,'/prediction':dict(Status=503,Body={})}))['State']
            before['Cash']='395';before['Holdings']['AAA_USDT']=dict(Imported=False,Quantity='10',Peak='12',Entered='2026-09-20T00:00:00Z')
            for index in range(2):
                request=dict(ID=f'stop_refill_{int(aware)}_{index}',NowNS=now,Config=config(aware,'.003'),Before=before,Responses=responses)
                answer=worker.apply(request);money(before,answer['State'],'.003')
                fills=(answer['State']['Fills'] or [])[len(before['Fills'] or []):]
                row=deepcopy(dict(input=request,output=answer,new_fills=fills))
                save(output/(request['ID']+'.json'),row);rows.append(row)
                before=deepcopy(answer['State']);now+=60_000_000_000
                for path,r in responses.items():
                    if path.endswith('/orderBook'):r['Body']['ts']=now//1_000_000
                    if path=='/markets/ticker24h':
                        for ticker in r['Body']:ticker['ts']=now//1_000_000
    finally:worker.close()
    for index,row in enumerate(rows):
        sides=[f['Order']['side'] for f in row['new_fills'] if f['Order']['symbol']=='AAA_USDT']
        assert sides==(['SELL','BUY'] if index%2==0 else []),sides
    save(output/'verification.json',dict(verified=True,at_ns=time.time_ns(),synthetic=True,observed_live_occurrence=False,cycles=4,
        same_cycle_stop_then_rebuy_both_arms=True,next_minute_same_stop_id_blocks_additional_sell=True,
        retained_quantity_after_first_cycle=rows[0]['output']['State']['Holdings']['AAA_USDT']['Quantity'],
        hashes={str(p):sha(p) for p in [*output.glob('*.json'),__file__,OUT/'driver/candidate/observed_cycle.test']},live_changed=False))
    print('CAPPED_STOP_REBUY_REPRODUCED',rows[0]['output']['State']['Holdings']['AAA_USDT']['Quantity'],flush=True)

if __name__=='__main__':main()
