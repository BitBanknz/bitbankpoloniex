"""All paired results and dependence on repeated synthetic hourly liquidity."""
from collections import defaultdict
from decimal import Decimal as D
import hashlib
import json
from pathlib import Path
import time

from build import OUT, REPO, read, save, sha
from account_reference import stamp


def economic_fills(state):
    return [{**fill, 'Order':{key:value for key,value in fill['Order'].items() if key!='clientOrderId'}}
            for fill in state['Fills'] or []]


def main():
    root=OUT/'historical_accounts';proof=read(root/'verification.json')
    assert proof['verified']
    assert sha(root/'accounts.json')==proof['accounts_sha256']
    registration=read(root/'registration.json')
    assert all(sha(path)==h for path,h in registration['hashes'].items())
    fixture=read(REPO/'data/frontier_20260912/ledger/fixture.json')
    hours={hour['TS']:hour for hour in fixture['Hours']}
    symbol_index={symbol.removesuffix('USDT')+'_USDT':i for i,symbol in enumerate(fixture['Pairs'])}
    pairs=read(root/'accounts.json');rows=[];all_repeated=[]
    for pair in pairs:
        states={}
        for arm,binding in pair['bindings'].items():
            assert sha(binding['path'])==binding['sha256']
            states[arm]=read(binding['path'])
        candidate=states['repeat']
        protective_ids={
            'bbp-'+hashlib.sha256(('paper|'+key).encode()).hexdigest()[:40]
            for key in candidate['Processed'] if '|protective-minute-' in key
        }
        groups=defaultdict(list)
        for fill in candidate['Fills'] or []:
            if fill['Order']['clientOrderId'] in protective_ids:
                assert fill['Order']['side']=='SELL'
                groups[(stamp(fill['At'])//3600*3600,fill['Order']['symbol'])].append(fill)
        repeated=[]
        for (hour,symbol),fills in sorted(groups.items()):
            if len(fills)<2:continue
            ticks=[stamp(fill['At'])//60 for fill in fills]
            assert len(ticks)==len(set(ticks))
            source=hours[hour];i=symbol_index[symbol]
            # Match the retained historical driver, not an observed order book.
            modeled_book_depth=D(format(source['PriorTurnover'][i]/source['Open'][i]*.1,'.14f'))
            quantity=sum(D(fill['Quantity']) for fill in fills)
            row=dict(case=pair['case'],start=pair['start'],hour=hour,symbol=symbol,fills=len(fills),
                     quantities=str(quantity),modeled_one_quote_book_depth=str(modeled_book_depth),
                     total_over_one_quote_10pct_allowance=str(quantity/(modeled_book_depth*D('.1'))),
                     actual_minute_replenishment_observed=False)
            repeated.append(row);all_repeated.append(row)
        rows.append(dict(case=pair['case'],start=pair['start'],end=pair['end'],difference=pair['difference'],
                         same_economic_fills=economic_fills(states['control'])==economic_fills(states['repeat']),
                         control_fills=len(states['control']['Fills'] or []),repeat_fills=len(candidate['Fills'] or []),
                         protective_fills=sum(len(f) for f in groups.values()),
                         repeated_protective_hours=repeated))

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,ax=plt.subplots(figsize=(8.5,5))
    colors={'0.003':'#1b4965','0.004':'#bd6c16','0.006':'#a33b3b'}
    for fee,color in colors.items():
        values=[p for p in pairs if '_fee'+fee+'_' in p['case']]
        ax.scatter([float(p['difference']['return_pct']) for p in values],
                   [float(p['difference']['max_drawdown_pct']) for p in values],
                   s=44,alpha=.65,color=color,label=f'{round(float(fee)*10000)} bps per side')
    ax.axhline(0,color='#666666',linewidth=.8);ax.axvline(0,color='#666666',linewidth=.8)
    ax.set_xlabel('Return change vs guarded control (percentage points)')
    ax.set_ylabel('Drawdown change (percentage points; lower is better)')
    ax.set_title('Repeated protective sells: all 45 reused historical account pairs',loc='left')
    ax.text(.02,.98,'Hourly prices and synthetic books; overlapping accounts and fee arms',transform=ax.transAxes,va='top',fontsize=8)
    ax.grid(alpha=.2);ax.legend(frameon=False,fontsize=9);fig.tight_layout()
    fig.savefig(root/'paired_changes.png',dpi=160);fig.savefig(root/'paired_changes.svg');plt.close(fig)
    result=dict(verified=True,at_ns=time.time_ns(),history_verification_sha256=sha(root/'verification.json'),
                analyzer_sha256=sha(Path(__file__)),rows=rows,accounts=45,
                accounts_with_same_economic_fills=sum(row['same_economic_fills'] for row in rows),
                repeated_protective_hour_groups=len(all_repeated),
                repeated_groups_above_one_quote_10pct_allowance=sum(D(row['total_over_one_quote_10pct_allowance'])>1 for row in all_repeated),
                better_return_and_no_worse_drawdown=sum(D(p['difference']['return_pct'])>0 and D(p['difference']['max_drawdown_pct'])<=0 for p in pairs),
                higher_return_and_higher_drawdown=sum(D(p['difference']['return_pct'])>0 and D(p['difference']['max_drawdown_pct'])>0 for p in pairs),
                independent_observations_claimed=False,deployment_qualified=False,
                plot_hashes={name:sha(root/name) for name in ('paired_changes.png','paired_changes.svg')})
    save(root/'attribution.json',result)
    print(json.dumps({key:value for key,value in result.items() if key not in ('rows','plot_hashes')}),flush=True)


if __name__=='__main__':main()
