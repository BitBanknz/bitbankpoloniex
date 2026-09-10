"""Hourly execution stress for the already selected daily candidate; no promotion."""
import argparse,json
from pathlib import Path
import numpy as np
import pandas as pd
from evaluate import load_archive,weights,metrics
p=argparse.ArgumentParser();p.add_argument('--daily',type=Path,required=True);p.add_argument('--hourly',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
grid,symbols,data,x,features,y,valid,eligible,sources=load_archive(a.daily);eth=symbols.index('ETH_USDT');end=len(grid)-2;h=end-365;bounds=np.linspace(max(730,h-5*365),h,6,dtype=int);c=dict(name='trend20-top3-btc',kind='trend',lookback=20,slots=3,regime='btc');scores=x['r20'].values
frames={s:pd.read_csv(a.hourly/s/'candles.csv',index_col='timestamp',parse_dates=True) for s in symbols};records=[];all_daily=[]
for lo,hi in zip(bounds[:-1],bounds[1:]):
 w=weights(c,scores,x,eligible,lo,hi,eth);clock=pd.date_range(grid[lo+1]-pd.Timedelta(hours=1),grid[hi],freq='h');arrays={k:np.column_stack([frames[s][k].reindex(clock).values for s in symbols]) for k in ['open','high','low','close','quote_volume']}
 q=np.zeros(len(symbols));peaks=np.zeros(len(symbols));cash=10000.;curve=[];stops=0;clipped=0;fees=0.;failure=None
 for t in range(1,len(clock)):
  price=arrays['open'][t];held=q>1e-12
  if ((~np.isfinite(price))&held).any():failure='missing held hourly price at '+str(clock[t]);break
  equity=cash+np.where(held,q*price,0).sum()
  i=lo+(t-1)//24
  if (t-1)%24==0 and (i-lo)%7==0 and i<hi-1:
   target=w[i]*equity;desired=np.divide(target,price,out=np.zeros_like(q),where=target>0);delta=desired-q
   active=np.abs(delta)>1e-12
   if ((~np.isfinite(price)|~np.isfinite(arrays['quote_volume'][t-1]))&active).any():failure='missing entry price/preceding volume';break
   cap=np.nan_to_num(arrays['quote_volume'][t-1])*.001
   notionals=delta*np.nan_to_num(price);bounded=np.sign(notionals)*np.minimum(np.abs(notionals),cap);clipped+=int((np.abs(notionals)>cap).sum());delta=np.divide(bounded,price,out=np.zeros_like(q),where=active)
   # Sell before buying; 30bps fee + 10bps adverse execution per side.
   cost=np.abs(bounded).sum()*.004;cash-=bounded.sum()+cost;fees+=cost;q+=delta
   new=(q>1e-12)&~held;peaks[new]=price[new];peaks[q<=1e-12]=0
  if t==len(clock)-1:curve.append(cash+np.where(q>1e-12,q*price,0).sum());break
  held=q>1e-12;low=arrays['low'][t];high=arrays['high'][t];close=arrays['close'][t]
  if ((~np.isfinite(low)|~np.isfinite(high)|~np.isfinite(close))&held).any():failure='missing intraday held bar';break
  # Only prior observed highs determine this hour's stop threshold.
  trigger=held&(low<=peaks*.9);fill=np.minimum(price,peaks*.9);sell=np.where(trigger,q,0);volumeCap=np.nan_to_num(arrays['quote_volume'][t-1])*.001
  sell=np.minimum(sell,np.divide(volumeCap,fill,out=np.zeros_like(q),where=fill>0));proceeds=sell*np.nan_to_num(fill);cost=proceeds.sum()*.004;cash+=proceeds.sum()-cost;fees+=cost;q-=sell;stops+=int((sell>0).sum());peaks=np.where(q>1e-12,np.maximum(peaks,np.nan_to_num(high)),0)
  curve.append(cash+np.where(q>1e-12,q*close,0).sum())
 if failure:records.append({'start':str(grid[lo]),'error':failure});continue
 terminal=np.sum(np.where(q>1e-12,q*arrays['open'][-1],0))*.004;curve[-1]-=terminal;fees+=terminal;daily=np.array([10000.]+[curve[j] for j in range(23,len(curve)-1,24)]+[curve[-1]])
 r=daily[1:]/daily[:-1]-1;m=metrics(r);m.update(stops=stops,clipped_order_changes=clipped,execution_costs_initial_equity=fees/10000);records.append({'start':str(grid[lo]),'end':str(grid[hi]),'metrics':m});all_daily.extend(r);print(records[-1],flush=True)
result={'candidate':c,'folds':records,'aggregate':metrics(all_daily),'all_folds_completed':all('metrics'in r for r in records),'positive_folds':sum(r.get('metrics',{}).get('return',-1)>0 for r in records),'assumptions':'$10k initial per fold; weekly weights; hourly 10% trailing high stop; min(open,stop) gap fill; 40bps per side; 0.1% prior-hour volume cap; original model selected after comparison; not live validated'}
a.out.write_text(json.dumps(result,indent=2));print(result['aggregate'],result['positive_folds'],flush=True)
