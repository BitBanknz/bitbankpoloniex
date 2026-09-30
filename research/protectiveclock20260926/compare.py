"""Three-way paired attribution; all accounts and economic differences retained."""
from collections import Counter
from decimal import Decimal as D
import hashlib
from pathlib import Path
import time

from build import BASE, HERE, OUT, read, save, sha
from account_reference import stamp

def economic_fills(state):
    return [{**fill,'Order':{key:value for key,value in fill['Order'].items() if key!='clientOrderId'}} for fill in state['Fills'] or []]

def difference(a,b):
    return {key:str(D(a[key])-D(b[key])) for key in ('return_pct','max_drawdown_pct','initial_budget_drawdown_pct','final_equity','fees')}

def counts(rows,key):
    return dict(higher_return=sum(D(row[key]['return_pct'])>0 for row in rows),
                lower_return=sum(D(row[key]['return_pct'])<0 for row in rows),
                equal_return=sum(D(row[key]['return_pct'])==0 for row in rows),
                lower_drawdown=sum(D(row[key]['max_drawdown_pct'])<0 for row in rows),
                higher_drawdown=sum(D(row[key]['max_drawdown_pct'])>0 for row in rows),
                equal_drawdown=sum(D(row[key]['max_drawdown_pct'])==0 for row in rows),
                largest_drawdown_increase_pp=str(max(D(row[key]['max_drawdown_pct']) for row in rows)),
                largest_return_increase_pp=str(max(D(row[key]['return_pct']) for row in rows)),
                largest_return_decrease_pp=str(min(D(row[key]['return_pct']) for row in rows)))

def main():
    root=OUT/'historical_accounts';older=BASE/'poloniex_protective_minute_v1/historical_accounts'
    current=read(root/'verification.json');oldproof=read(older/'verification.json')
    assert current['verified'] and oldproof['verified']
    assert sha(root/'accounts.json')==current['accounts_sha256']
    assert sha(older/'accounts.json')==oldproof['accounts_sha256']
    oldpairs={(p['case'],p['start'],p['end']):p for p in read(older/'accounts.json')}
    rows=[];events=Counter();minute_events=Counter();clock_sell_hours=0
    for pair in read(root/'accounts.json'):
        old=oldpairs.pop((pair['case'],pair['start'],pair['end']))
        states={};bindings={**pair['bindings'],'minute':old['bindings']['repeat']}
        assert sha(old['bindings']['control']['path'])==sha(pair['bindings']['control']['path'])
        for arm,binding in bindings.items():
            assert sha(binding['path'])==binding['sha256'];states[arm]=read(binding['path'])
        metrics=dict(control=pair['control'],clock=pair['clock'],minute=old['repeat'])
        fill_views={arm:economic_fills(state) for arm,state in states.items()}
        sells=Counter((stamp(fill['At'])//3600,fill['Order']['symbol']) for fill in states['clock']['Fills'] or [] if fill['Order']['side']=='SELL')
        assert all(number==1 for number in sells.values()),('extra actual-hour sale',pair['case'],pair['start'])
        clock_sell_hours+=len(sells)
        divergences={}
        for baseline in ('control','minute'):
            left,right=fill_views[baseline],fill_views['clock']
            if left==right:continue
            index=next((i for i,(a,b) in enumerate(zip(left,right)) if a!=b),min(len(left),len(right)))
            target=right[index] if index<len(right) else None
            other=left[index] if index<len(left) else None
            keys={arm:{'bbp-'+hashlib.sha256(('paper|'+key).encode()).hexdigest()[:40]:key for key in states[arm]['Processed']} for arm in (baseline,'clock')}
            native_clock=states['clock']['Fills'][index] if target is not None else None
            native_other=states[baseline]['Fills'][index] if other is not None else None
            divergences[baseline]=dict(fill_index=index,clock=target,baseline=other,
                clock_key=keys['clock'][native_clock['Order']['clientOrderId']] if native_clock else None,
                baseline_key=keys[baseline][native_other['Order']['clientOrderId']] if native_other else None)
            if target is not None:
                (events if baseline=='control' else minute_events)[(target['At'],target['Order']['symbol'],target['Order']['side'])]+=1
        rows.append(dict(case=pair['case'],start=pair['start'],end=pair['end'],metrics=metrics,bindings=bindings,
                         clock_minus_control=difference(metrics['clock'],metrics['control']),
                         clock_minus_minute=difference(metrics['clock'],metrics['minute']),
                         same_economic_fills_vs_control=fill_views['clock']==fill_views['control'],
                         same_economic_fills_vs_minute=fill_views['clock']==fill_views['minute'],
                         first_economic_differences=divergences))
    assert len(rows)==45 and not oldpairs
    groups=[]
    for case in [group['case'] for group in current['groups']]:
        selected=[row for row in rows if row['case']==case['id']]
        def stats(arm):
            values=[row['metrics'][arm] for row in selected]
            return dict(mean_return_pct=str(sum(D(value['return_pct']) for value in values)/len(values)),
                        maximum_drawdown_pct=str(max(D(value['max_drawdown_pct']) for value in values)),
                        fees=str(sum(D(value['fees']) for value in values)),fills=sum(value['fills'] for value in values))
        groups.append(dict(case=case,accounts=len(selected),control=stats('control'),clock=stats('clock'),minute=stats('minute')))

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(1,2,figsize=(12,4.8))
    colors={'0.003':'#1b4965','0.004':'#bd6c16','0.006':'#a33b3b'}
    for ax,key,title in zip(axes,('clock_minus_control','clock_minus_minute'),('Clock correction vs guarded control','Clock correction vs minute selling')):
        for fee,color in colors.items():
            selected=[row for row in rows if '_fee'+fee+'_' in row['case']]
            ax.scatter([float(row[key]['return_pct']) for row in selected],[float(row[key]['max_drawdown_pct']) for row in selected],s=35,alpha=.65,color=color,label=f'{round(float(fee)*10000)} bps/side')
        ax.axhline(0,color='#666666',linewidth=.8);ax.axvline(0,color='#666666',linewidth=.8)
        ax.set_title(title,loc='left',fontsize=11);ax.set_xlabel('Return difference (percentage points)')
        ax.set_ylabel('Drawdown difference (pp; lower is better)');ax.grid(alpha=.2)
    axes[1].legend(frameon=False,fontsize=8)
    fig.suptitle('45 reused historical pairs — hourly prices and synthetic books; overlapping account windows',fontsize=10)
    fig.tight_layout();fig.savefig(root/'clock_ablation.png',dpi=160);fig.savefig(root/'clock_ablation.svg');plt.close(fig)
    save(root/'three_way_accounts.json',rows)
    result=dict(verified=True,at_ns=time.time_ns(),accounts=45,control_ledgers_identical_across_experiments=True,
                clock_minus_control=counts(rows,'clock_minus_control'),clock_minus_minute=counts(rows,'clock_minus_minute'),
                same_economic_fills_vs_control=sum(row['same_economic_fills_vs_control'] for row in rows),
                same_economic_fills_vs_minute=sum(row['same_economic_fills_vs_minute'] for row in rows),
                all_clock_sells_at_most_once_per_symbol_per_actual_hour=True,clock_sell_hours=clock_sell_hours,
                first_clock_vs_control_events=[dict(at=key[0],symbol=key[1],side=key[2],comparisons=value) for key,value in sorted(events.items())],
                first_clock_vs_minute_events=[dict(at=key[0],symbol=key[1],side=key[2],comparisons=value) for key,value in sorted(minute_events.items())],
                groups=groups,historical_reuse=True,independent_holdout=False,deployment_qualified=False,
                hashes={str(p):sha(p) for p in [Path(__file__),root/'verification.json',root/'accounts.json',older/'verification.json',older/'accounts.json']},
                output_hashes={name:sha(root/name) for name in ('three_way_accounts.json','clock_ablation.png','clock_ablation.svg')})
    save(root/'three_way_verification.json',result)
    print({key:value for key,value in result.items() if key not in ('groups','hashes','output_hashes')},flush=True)

if __name__=='__main__':main()
