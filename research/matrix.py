"""All-candidate diagnostics on already consumed folds. No fresh holdout claim."""
import argparse,json
from pathlib import Path
import numpy as np
from evaluate import load_archive,weights,simulate,metrics
p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
grid,symbols,data,x,features,y,valid,eligible,sources=load_archive(a.archive);eth=symbols.index('ETH_USDT');end=len(grid)-2;h=end-365;bounds=np.linspace(max(730,h-5*365),h,6,dtype=int);rows=[]
for lookback in [20,60,120]:
 for slots in [1,3]:
  for regime in ['none','btc','breadth']:
   c=dict(name=f'trend{lookback}-top{slots}-{regime}',kind='trend',lookback=lookback,slots=slots,regime=regime);scores=x[f'r{lookback}'].values
   folds=[];returns=[]
   for lo,hi in zip(bounds[:-1],bounds[1:]):
    w=weights(c,scores,x,eligible,lo,hi,eth);r,m=simulate(w,data,lo,hi);_,stress=simulate(w,data,lo,hi,fee=.006);returns.extend(r);folds.append({'normal':m,'stress':stress})
   # A fixed 50% sleeve is a declared risk scaling scenario, not a new model.
   w=weights(c,scores,x,eligible,h,end,eth);_,hold=simulate(w,data,h,end,conversion=True)
   reduced=[]
   for lo,hi in zip(bounds[:-1],bounds[1:]):
    w=weights(c,scores,x,eligible,lo,hi,eth)*.5;r,_=simulate(w,data,lo,hi);reduced.extend(r)
   row={'candidate':c,'folds':folds,'cv':metrics(returns),'half_risk_cv':metrics(reduced),'positive_folds':sum(f['normal']['return']>0 for f in folds),'stress_positive_folds':sum(f['stress']['return']>0 for f in folds),'reused_final_year':hold}
   rows.append(row)
rows.sort(key=lambda r:(-r['positive_folds'],-r['cv']['return']))
a.out.write_text(json.dumps({'warning':'exploratory comparison after viewing all folds; selection-biased; not eligible for automatic promotion','candidates':rows},indent=2))
for r in rows:print(r['candidate']['name'],r['positive_folds'],r['stress_positive_folds'],r['cv']['return'],r['cv']['max_drawdown'],r['half_risk_cv']['return'],r['half_risk_cv']['max_drawdown'],flush=True)
