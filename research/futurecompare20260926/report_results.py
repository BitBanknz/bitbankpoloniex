"""Account attribution and plot from the fully verified fixed prefix only."""
from collections import defaultdict
from datetime import datetime,timezone
from decimal import Decimal as D
import gzip
import json
from pathlib import Path
import time
from capture import OUT,HERE,sha,save
from reference import mark

def main():
    root=OUT/'completed_v2/audit';proof=json.loads((root/'verification.json').read_text());assert proof['verified'] and proof['through_index']==3297
    for name,h in proof['output_hashes'].items():assert sha(root/name)==h
    for row in proof['trace_reconstructions']:assert sha(row['file'])==row['sha256']
    summary=json.loads((root/'summary.json').read_text());states=json.loads((root/'final_states.json').read_text())
    manifest=json.loads((OUT/'mirror/manifest.json').read_text());last_input=OUT/'mirror/unguarded/batch_03297.input.json.gz'
    assert sha(last_input)==manifest['unguarded/batch_03297.input.json.gz']['sha256']
    packet=json.loads(gzip.decompress(last_input.read_bytes()))['packet'];attribution=[]
    for fee in (30,40,60):
        name='control_fee'+str(fee);state=states['unguarded'][name];totals=defaultdict(lambda:dict(buys=D(0),sells=D(0),fees=D(0),fills=0))
        for fill in state['Fills'] or []:
            row=totals[fill['Order']['symbol']];row['buys' if fill['Order']['side']=='BUY' else 'sells']+=D(fill['Amount']);row['fees']+=D(fill['Fee']);row['fills']+=1
        equity,missing,bids=mark(state,packet['Responses'],packet['NowNS']);assert not missing
        net=D(0)
        for symbol,row in sorted(totals.items()):
            qty=D(state['Holdings'].get(symbol,{}).get('Quantity','0'));value=qty*D(bids[symbol]) if qty else D(0)
            pnl=value+row['sells']-row['buys']-row['fees'];net+=pnl
            attribution.append(dict(fee_bps=fee,symbol=symbol,quantity=str(qty),bid=bids.get(symbol),marked_value=str(value),
                purchases=str(row['buys']),sales=str(row['sells']),fees=str(row['fees']),net_contribution=str(pnl),fills=row['fills']))
        assert net==equity-495
    current={};dates=[];curves={fee:[] for fee in (30,40,60)};same_paths=0;first_ns=last_ns=None
    for line in (root/'paths.jsonl').open():
        row=json.loads(line)
        if row['index']<78:continue
        fee=int(row['account'].rsplit('fee',1)[1]);key=(row['index'],fee)
        values={k:row[k] for k in ('now_ns','cash','fees','turnover','dust','below_stop_buys','equity','unpriced','marks','new_fills')}
        if row['study']=='unguarded' and row['account'].startswith('control_'):
            current[key]=values
            if fee==30:
                dates.append(datetime.fromtimestamp(row['now_ns']/1e9,timezone.utc));first_ns=first_ns or row['now_ns'];last_ns=row['now_ns']
            curves[fee].append(float(row['equity']))
        else:assert current[key]==values,('strategy account paths differ',row['index'],row['study'],row['account']);same_paths+=1
        if row['study']=='guarded' and row['account'].startswith('quote_aware_'):del current[key]
    assert not current and same_paths==3220*9
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    fig,ax=plt.subplots(figsize=(10,4.6))
    for fee,color in [(30,'#1b4965'),(40,'#bd6c16'),(60,'#a33b3b')]:ax.plot(dates,curves[fee],color=color,linewidth=1.25,label=f'{fee} bps per side')
    ax.axhline(495,color='#606060',linestyle='--',linewidth=.8,label='Initial cash')
    ax.set_title('Poloniex paper equity: identical strategy paths at each fee level',loc='left',fontsize=12)
    ax.set_ylabel('USDT, holdings marked at captured bids');ax.set_xlabel('UTC — fixed common prefix, study still running')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %d %H:%M',tz=timezone.utc));ax.grid(alpha=.2);ax.legend(frameon=False,ncol=4,loc='lower left',fontsize=8)
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(root/'equity.png',dpi=170);fig.savefig(root/'equity.svg');plt.close(fig)
    result=dict(at_ns=time.time_ns(),verified=True,reporter_sha256=sha(Path(__file__)),verification_sha256=sha(root/'verification.json'),
        common_first_index=78,through_index=3297,common_minutes=3220,first_logical_ns=first_ns,last_logical_ns=last_ns,
        equal_paired_account_rows=same_paths,all_four_strategy_variants_have_identical_financial_paths_at_each_fee=True,
        fee_summary={str(fee):summary['unguarded']['control_fee'+str(fee)] for fee in (30,40,60)},
        asset_attribution=attribution,open_holdings_not_liquidated=True,profitability_established=False,deployment_qualified=False,
        plot_hashes={name:sha(root/name) for name in ('equity.png','equity.svg')})
    save(root/'report.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('asset_attribution','fee_summary','plot_hashes')}),flush=True)

if __name__=='__main__':main()
