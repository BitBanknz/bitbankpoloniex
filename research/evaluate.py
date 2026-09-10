#!/usr/bin/env python3
"""Fixed, predeclared strategy families; nested expanding CV + sealed final year.
Research only. No keys, account APIs, order submission, or runtime model promotion.
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb

FEATURES=['r5','r20','r60','r120','vol20','range20','volume20','rank20','rank60']

def load_archive(root):
    manifest=json.loads((root/'manifest.json').read_text()); frames={}; sources={}
    for symbol,status in sorted(manifest.items()):
        path=root/symbol/'candles.csv'
        if status.get('Error') or not status.get('Complete') or not path.exists():continue
        raw=path.read_bytes()
        if hashlib.sha256(raw).hexdigest()!=status['CSVHash']:raise ValueError('archive checksum '+symbol)
        f=pd.read_csv(path,index_col='timestamp',parse_dates=True)
        if len(f)<400:continue
        if f.index.has_duplicates or not f.index.is_monotonic_increasing:raise ValueError('bad calendar')
        frames[symbol]=f;sources[symbol]={'sha256':status['CSVHash'],'rows':len(f),'gaps':status['Gaps']}
    if 'ETH_USDT' not in frames:raise ValueError('ETH archive required for actual collateral benchmark')
    grid=pd.date_range(min(f.index[0] for f in frames.values()),max(f.index[-1] for f in frames.values()),freq='D')
    symbols=sorted(frames)
    data={field:pd.DataFrame({s:f[field].reindex(grid) for s,f in frames.items()})[symbols] for field in ['open','high','low','close','quote_volume']}
    close=data['close']; returns=close.pct_change(fill_method=None)
    x={f'r{n}':close/close.shift(n)-1 for n in [5,20,60,120]}
    x['vol20']=returns.rolling(20,min_periods=20).std()*np.sqrt(365)
    x['range20']=((data['high']-data['low'])/close).rolling(20,min_periods=20).mean()
    x['volume20']=np.log1p(data['quote_volume'].rolling(20,min_periods=20).median())
    x['btc_regime']=((close['BTC_USDT']>close['BTC_USDT'].rolling(200).mean())&(close['BTC_USDT']>close['BTC_USDT'].rolling(50).mean())).values
    x['breadth_regime']=((x['r120']>0).sum(axis=1)/x['r120'].notna().sum(axis=1).clip(lower=1)>.5).values
    x['rank20']=x['r20'].rank(axis=1,pct=True);x['rank60']=x['r60'].rank(axis=1,pct=True)
    feature=np.stack([x[k].values for k in FEATURES],axis=-1)
    # Daily close features -> following open entry; no same-close fills.
    target=data['open'].shift(-15)/data['open'].shift(-1)-1
    valid=np.isfinite(feature).all(axis=2)&np.isfinite(target.values)
    eligible=np.isfinite(feature).all(axis=2)&(data['quote_volume'].rolling(20,min_periods=20).median().values>=100000)
    return grid,symbols,data,x,feature,target.values,valid,eligible,sources

def metrics(r):
    r=np.asarray(r,dtype=float);curve=np.cumprod(1+r);peak=np.maximum.accumulate(np.r_[1,curve])[1:]
    return {'return':float(curve[-1]-1) if len(curve) else 0.,'max_drawdown':float(np.max(1-curve/peak)) if len(curve) else 0.,'sharpe':float(np.mean(r)/max(np.std(r),1e-12)*np.sqrt(365)), 'days':len(r)}

def family():
    # Never change this grid in response to the final holdout.
    out=[]
    for lookback in [20,60,120]:
        for regime in ['none','btc','breadth']:
            out.append(dict(name=f'trend{lookback}-top3-{regime}',kind='trend',lookback=lookback,slots=3,regime=regime))
    for leaves in [7,15]:
        for regime in ['none','btc']:
            out.append(dict(name=f'lightgbm{leaves}-{regime}',kind='lgb',leaves=leaves,slots=3,regime=regime))
    return out

def forecast(candidate,train_end,test_end,feature,y,valid,x):
    if candidate['kind']=='trend':return x[f'r{candidate["lookback"]}'].values.copy()
    # The last training label completes before any validation/test observation.
    cutoff=train_end-16
    mask=valid[:cutoff];xx=feature[:cutoff][mask];yy=y[:cutoff][mask]
    if len(yy)<1000:raise ValueError('insufficient training observations')
    model=lgb.LGBMRegressor(n_estimators=100,num_leaves=candidate['leaves'],max_depth=4,learning_rate=.03,min_child_samples=200,reg_lambda=20,feature_fraction=1.,n_jobs=4,verbosity=-1,random_state=20260910)
    model.fit(xx,np.clip(yy,-.5,1.))
    out=np.full(y.shape,np.nan);test=feature[train_end:test_end];good=np.isfinite(test).all(axis=2);part=np.full(test.shape[:2],np.nan);part[good]=model.predict(test[good]);out[train_end:test_end]=part;return out

def weights(candidate,score,x,eligible,start,end,eth,collateral=False,margin=False):
    result=np.zeros_like(score);previous=np.zeros(score.shape[1])
    for i in range(start,end):
        if (i-start)%7==0:
            valid=eligible[i]&np.isfinite(score[i])
            # Positive absolute momentum is independent of model ranking.
            valid&=(x['r120'].values[i]>0)&(score[i]>0)
            regime=candidate.get('regime','none')
            if regime!='none' and not x[regime+'_regime'][i]:valid[:]=False
            choices=np.flatnonzero(valid)
            choices=sorted(choices,key=lambda j:(-score[i,j],j))[:candidate['slots']]
            previous=np.zeros(score.shape[1])
            for j in choices:
                previous[j]=min(.25, .20/max(x['vol20'].values[i,j],.20)/max(candidate['slots'],1))
        result[i]=previous
        if collateral:
            # Keep existing ETH as collateral; overlay is borrowed USDT. Cap gross to 1.25.
            result[i]*=.25/max(result[i].sum(),.25)
            result[i,eth]+=1.
        elif margin:
            result[i]*=1.25/max(result[i].sum(),1.)
    return result

def simulate(weights,data,start,end,fee=.003,borrow=.0003,eth=None,initial_eth=False,conversion=False):
    """Close-i decision -> open i+1; weights drift between weekly rebalances.
    Missing held prices fail the run. Liquidation uses adverse daily OHLC jointly,
    a deliberately conservative bound without pretending to know the intraday path.
    """
    op=data['open'].values;lo=data['low'].values;hi=data['high'].values
    n=op.shape[1];positions=np.zeros(n);cash=1.-(fee if conversion else 0.);equity=1.;rets=[];turnover=0.;liquidations=0;borrow_paid=0.;trades=0
    if initial_eth:
        if eth is None or not np.isfinite(op[start+1,eth]):raise ValueError("initial ETH price absent")
        positions[eth]=1./op[start+1,eth];cash=0.
    for i in range(start,end-1):
        price=op[i+1];next_price=op[i+2]
        held=np.abs(positions)>1e-12
        if ((~np.isfinite(price)|~np.isfinite(next_price))&held).any():raise ValueError('held market has a historical price gap')
        marked=np.where(held,positions*price,0.);before=cash+marked.sum()
        # Rebalance only on the declared weekly clock, or on final flatten.
        if (i-start)%7==0:
            target=weights[i]*before;active=np.abs(target)>1e-12
            if ((~np.isfinite(price))&active).any():raise ValueError('unavailable entry open')
            if (target>=0).all() and target.sum()<=before+1e-12:
                for _ in range(4):
                    estimate=np.abs(target-marked).sum()*fee
                    if target.sum()+estimate<=before:break
                    target*=max(0.,before-estimate)/max(target.sum(),1e-12)
            change=target-marked;traded=np.abs(change).sum();cost=traded*fee;cash-=change.sum()+cost
            positions=np.divide(target,price,out=np.zeros(n),where=active);turnover+=traded/max(before,1e-12);trades+=int((np.abs(change)>1e-10).sum())
        debt=max(0.,-cash);short_value=np.sum(np.maximum(-positions*np.nan_to_num(price),0.));interest=(debt+short_value)*borrow;cash-=interest;borrow_paid+=interest
        held=np.abs(positions)>1e-12
        adverse=np.where(positions>=0,lo[i+1],hi[i+1])
        if ((~np.isfinite(adverse))&held).any():raise ValueError('missing intraday risk price')
        adverse_values=np.where(held,positions*adverse,0.);worst=cash+adverse_values.sum();gross=np.abs(adverse_values).sum()
        if debt+short_value>0 and worst<=.15*gross:
            cash=max(0.,worst-.005*gross);positions[:]=0;liquidations+=1
            # A liquidation is terminal, never followed by a synthetic restart.
            after=cash;rets.append(after/equity-1);rets.extend([0.]*(end-2-i));break
        after=cash+np.where(held,positions*next_price,0.).sum()
        if i==end-2:after-=np.abs(np.where(held,positions*next_price,0.)).sum()*fee
        if not np.isfinite(after) or after<=0:raise ValueError('insolvent or invalid simulation')
        rets.append(after/equity-1);equity=after
    m=metrics(rets);m.update(turnover=float(turnover),order_changes=trades,borrow_cost_initial_equity=float(borrow_paid),liquidations=liquidations);return np.asarray(rets),m

def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    grid,symbols,data,x,feature,y,valid,eligible,sources=load_archive(a.archive);eth=symbols.index('ETH_USDT')
    # Freeze dates, grid and candidates before evaluating any test performance.
    final=len(grid)-2;holdout_start=final-365;first=max(730,holdout_start-5*365)
    if holdout_start-first<5*120:raise ValueError('not enough independent history')
    boundaries=np.linspace(first,holdout_start,6,dtype=int);candidates=family()
    declaration={'schema':'nested-daily-v2','candidates':candidates,'outer_boundaries':[str(grid[i]) for i in boundaries],'final_holdout':[str(grid[holdout_start]),str(grid[final])],'sources':sources,'cost_per_side':.003,'borrow_daily_scenario':.0003,'warning':'current-listed universe has survivorship bias; historical collateral/borrow availability unknown; margin results are scenarios only'}
    (a.out/'declaration.json').write_text(json.dumps(declaration,indent=2));all_outer=[];selected=[];cv_rows=[]
    for fold,(start,end) in enumerate(zip(boundaries[:-1],boundaries[1:])):
        inner_start=max(365,start-365);scores=[]
        for candidate in candidates:
            pred=forecast(candidate,inner_start,start,feature,y,valid,x)
            w=weights(candidate,pred,x,eligible,inner_start,start,eth)
            try:_,m=simulate(w,data,inner_start,start)
            except ValueError as e:m={'return':-1.,'max_drawdown':1.,'sharpe':-100.,'error':str(e)}
            # Select on three chronological inner blocks, penalizing the weakest block.
            inner=[]
            for aa,bb in zip(np.linspace(inner_start,start,4,dtype=int)[:-1],np.linspace(inner_start,start,4,dtype=int)[1:]):
                try:_,mm=simulate(w,data,aa,bb);inner.append(mm['return']-mm['max_drawdown'])
                except ValueError:inner.append(-1.)
            objective=float(np.mean(inner)+min(inner));m['inner_block_objectives']=inner;scores.append((objective,candidate,m))
        scores.sort(key=lambda z:(-z[0],z[1]['name']));chosen=scores[0][1];selected.append(chosen)
        pred=forecast(chosen,start,end,feature,y,valid,x);w=weights(chosen,pred,x,eligible,start,end,eth)
        r,m=simulate(w,data,start,end);stress_r,stress=simulate(w,data,start,end,fee=.006,borrow=.001)
        all_outer.extend(r.tolist());record={'fold':fold,'start':str(grid[start]),'end':str(grid[end]),'selected':chosen,'inner_candidates':[{'candidate':c,'metrics':mm,'objective':o} for o,c,mm in scores],'outer':m,'outer_doubled_costs':stress}
        cv_rows.append(record);print('fold',fold,chosen['name'],m,flush=True)
    # Select final model strictly on the final inner window BEFORE the sealed year.
    inner_start=holdout_start-365;rank=[]
    for c in candidates:
        pred=forecast(c,inner_start,holdout_start,feature,y,valid,x);w=weights(c,pred,x,eligible,inner_start,holdout_start,eth)
        try:
            inner=[]
            for aa,bb in zip(np.linspace(inner_start,holdout_start,4,dtype=int)[:-1],np.linspace(inner_start,holdout_start,4,dtype=int)[1:]):
                _,mm=simulate(w,data,aa,bb);inner.append(mm['return']-mm['max_drawdown'])
            objective=float(np.mean(inner)+min(inner))
        except ValueError:objective=-1e6
        rank.append((objective,c))
    rank.sort(key=lambda z:(-z[0],z[1]['name']));chosen=rank[0][1];(a.out/'final-selection.json').write_text(json.dumps(chosen,indent=2))
    pred=forecast(chosen,holdout_start,final,feature,y,valid,x);scenarios={};curves={}
    for name,collateral,margin in [('cash',False,False),('existing_eth_collateral',True,False)]:
        w=weights(chosen,pred,x,eligible,holdout_start,final,eth,collateral,margin)
        r,m=simulate(w,data,holdout_start,final,eth=eth,initial_eth=collateral,conversion=not collateral);_,stress=simulate(w,data,holdout_start,final,fee=.006,borrow=.001,eth=eth,initial_eth=collateral,conversion=not collateral)
        scenarios[name]={'normal':m,'stress':stress};curves[name]=np.cumprod(1+r).tolist()
    hold=np.zeros_like(y);hold[:,eth]=1.;r,benchmark=simulate(hold,data,holdout_start,final,fee=.003,eth=eth,initial_eth=True)
    cv=metrics(all_outer);positive=sum(f['outer']['return']>0 for f in cv_rows);stress_positive=sum(f['outer_doubled_costs']['return']>0 for f in cv_rows)
    passed=positive>=4 and stress_positive>=4 and cv['max_drawdown']<=.25 and scenarios['cash']['normal']['return']>0 and scenarios['cash']['stress']['return']>0
    result={'outer_cv':cv,'positive_outer_folds':positive,'positive_stress_folds':stress_positive,'folds':cv_rows,'final_candidate':chosen,'final_holdout':scenarios,'hold_eth_benchmark':benchmark,'research_gate_passed':passed,'runtime_promoted':False,'holdout_reused':True,'limits':declaration['warning']+'; daily candle fills lack historical spreads/order books; prior BitBank studies consumed some overlapping dates, so this is reused diagnostic year after v1, not untouched evidence'}
    (a.out/'results.json').write_text(json.dumps(result,indent=2));(a.out/'curves.json').write_text(json.dumps(curves));print(json.dumps({k:v for k,v in result.items() if k!='folds'},indent=2),flush=True)
if __name__=='__main__':main()
