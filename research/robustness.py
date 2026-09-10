"""Post-selection diagnostics. All results retained; no promotion."""
import argparse,json
from pathlib import Path
import numpy as np
from evaluate import load_archive,weights,simulate,metrics
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
grid,symbols,data,x,feature,y,valid,eligible,sources=load_archive(a.archive);eth=symbols.index('ETH_USDT');end=len(grid)-2;h=end-365;bounds=np.linspace(max(730,h-5*365),h,6,dtype=int)
c={'name':'trend20-top3-btc','kind':'trend','lookback':20,'slots':3,'regime':'btc'};scores=x['r20'].values

def assess(mask,cost=.003,delay=False,cap=1.):
 rs=[];folds=[];used=set();dd=data
 if delay:dd={k:v.shift(-1) for k,v in data.items()}
 for lo,hi in zip(bounds[:-1],bounds[1:]):
  w=weights(c,scores,x,mask,lo,hi,eth)*cap;used.update(np.flatnonzero((np.abs(w)>0).any(axis=0)))
  r,m=simulate(w,dd,lo,hi,fee=cost);rs.extend(r);folds.append(m)
 return dict(aggregate=metrics(rs),folds=folds,positive_folds=sum(f['return']>0 for f in folds)),used
base,used=assess(eligible);stress,_=assess(eligible,.006);delay,_=assess(eligible,delay=True);half,_=assess(eligible,cap=.5);removed={}
for j in sorted(used):
 mask=eligible.copy();mask[:,j]=False;removed[symbols[j]]=assess(mask)[0]
 print('leave-out',symbols[j],removed[symbols[j]]['aggregate']['return'],flush=True)
r=np.concatenate([np.zeros(0)])
# Paired time-block bootstrap of the already selected strategy's daily returns.
returns=[]
for lo,hi in zip(bounds[:-1],bounds[1:]):
 w=weights(c,scores,x,eligible,lo,hi,eth);r,_=simulate(w,data,lo,hi);returns.extend(r)
r=np.asarray(returns);rng=np.random.default_rng(20260910);means=[]
for _ in range(2000):
 starts=rng.integers(0,len(r)-30+1,size=int(np.ceil(len(r)/30)));sample=np.concatenate([r[i:i+30] for i in starts])[:len(r)];means.append(sample.mean()*365)
result={'candidate':c,'selection_warning':'Selected after comparing 18 strategies on these folds; these diagnostics do not remove selection bias','base':base,'double_cost':stress,'one_day_execution_delay':delay,'half_risk':half,'leave_one_market_out':removed,'block_bootstrap_annual_mean_95pct':np.quantile(means,[.025,.975]).tolist(),'runtime_promoted':False}
a.out.write_text(json.dumps(result,indent=2))
print('base',base['aggregate'],'worst_leaveout',min(v['aggregate']['return'] for v in removed.values()),'delay',delay['aggregate'],flush=True)
