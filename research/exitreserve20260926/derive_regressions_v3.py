"""Preserve a synthetic timestamp-format failure, then use Go-canonical UTC text."""
from copy import deepcopy
import gzip
import json
import sys
from build import HERE,OUT,REPO,read,save,sha
from regressions_v2 import initial,stop
from checks import fresh,iso,ns,MINUTE,DAY,HOUR
sys.path.insert(0,str(REPO/'research/quoteaware20260924'))
from native import Native
sys.path.insert(0,str(REPO/'research/futurecompare20260926'))
from reference import transition


def main():
    rows=[json.loads(line) for line in gzip.open(OUT/'regressions_v2/cycles.jsonl.gz','rt')]
    row=next(r for r in rows if r['input']['ID']=='buys_.003_baseline_4')
    request=initial('.003','baseline');start=request['NowNS'];request['Before']=deepcopy(row['output']['State'])
    fresh(request,start+5*MINUTE,True);request['ID']='ordinary_.003_baseline'
    request['Responses']['/prediction']['Body']['rank_scores']['AAAUSDT']=-1
    for p in request['Before']['Holdings'].values():p['Entered']=iso(start-4*DAY)
    native=Native(OUT/'observed/engine.test')
    try:answer=native.apply(request)
    finally:native.close()
    save(OUT/'regressions_v2/failing_ordinary_cycle.json',dict(input=request,output=answer))
    try:transition(request['Before'],answer['State'],request['Config']['FeeRate'],request['Responses'],request['NowNS'],True)
    except AssertionError:pass
    else:raise AssertionError('expected textual clock mismatch not reproduced')
    corrected=deepcopy(request['Before'])
    for symbol,position in corrected['Holdings'].items():
        actual=answer['State']['Holdings'][symbol]
        assert ns(position['Entered'])==ns(actual['Entered'])
        position['Entered']=actual['Entered']
    transition(corrected,answer['State'],request['Config']['FeeRate'],request['Responses'],request['NowNS'],True)
    source=HERE/'checks.py';target=HERE/'checks_v2.py'
    old="    return datetime.fromtimestamp(seconds,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{fraction:09d}Z'"
    new="    suffix=('.'+f'{fraction:09d}'.rstrip('0')) if fraction else ''\n    return datetime.fromtimestamp(seconds,timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+suffix+'Z'"
    text=source.read_text();assert text.count(old)==1
    with target.open('x') as f:f.write(text.replace(old,new))
    previous=HERE/'regressions_v2.py';current=HERE/'regressions_v3.py'
    text=previous.read_text()
    replacements=[('from checks import','from checks_v2 import'),("root=OUT/'regressions_v2'","root=OUT/'regressions_v3'"),("HERE/'checks.py'","HERE/'checks_v2.py'")]
    for a,b in replacements:
        assert text.count(a)==1
        text=text.replace(a,b)
    with current.open('x') as f:f.write(text)
    save(HERE/'regression_correction_v3.json',dict(
        hashes={str(p):sha(p) for p in (source,target,previous,current,OUT/'regressions_v2/failing_ordinary_cycle.json')},
        clock_replacements=[(old,new)],runner_replacements=replacements,
        reason='Synthetic ordinary-exit age used .000000000Z; Go canonically emits whole-second Z. Exact instants agree, and the unchanged money oracle passes with canonical input text.',
        native_code_changed=False,financial_oracle_changed=False,clock_instants_changed=False,historical_outcomes_inspected=False))


if __name__=='__main__':main()
