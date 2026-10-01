"""Retrained adaptations, not imports of sibling production weights."""
import json
import numpy as np
import pandas as pd


def rank_features(x):
    # Same-timestamp ranks only, with tied observations receiving equal ranks.
    return np.stack([pd.DataFrame(day).rank(pct=True).to_numpy()*2-1 for day in x]).astype('float32')


class RankModel:
    def __init__(self, kind, parameters=None):
        self.kind=kind
        self.parameters={} if parameters is None else dict(parameters)

    def fit(self,x,y):
        self.mean=x.mean(axis=(0,1)); self.scale=np.maximum(x.std(axis=(0,1)),1e-6)
        z=np.clip((x-self.mean)/self.scale,-10,10).astype('float32')
        if self.kind=='ridge':
            a=z.reshape(-1,z.shape[-1]); b=np.clip(y.ravel(),-3,3)
            self.bias=b.mean(); self.coef=np.linalg.solve(a.T@a+10*np.eye(a.shape[1]),a.T@(b-self.bias))
        elif self.kind=='lgbm_rank':
            import lightgbm as lgb
            labels=np.stack([pd.Series(v).rank(method='average').to_numpy()-1 for v in y]).astype(int)
            settings=dict(objective='lambdarank',n_estimators=100,num_leaves=7,max_depth=3,
                min_child_samples=24,learning_rate=.03,reg_lambda=10,reg_alpha=1,
                random_state=20260909,n_jobs=2,verbosity=-1,deterministic=True,force_col_wise=True)
            allowed={'n_estimators','num_leaves','max_depth','min_child_samples','learning_rate','reg_lambda','reg_alpha','random_state'}
            if set(self.parameters)-allowed:raise ValueError('unsupported ranker parameters')
            settings.update(self.parameters)
            self.model=lgb.LGBMRanker(**settings)
            self.model.fit(z.reshape(-1,z.shape[-1]),labels.ravel(),group=[z.shape[1]]*len(z))
        elif self.kind=='resmlp4':
            import torch
            torch.set_num_threads(2); torch.manual_seed(20260909)
            # Prediction2's linear residual + four tanh units; trained here with
            # Binancego-style timestamp-grouped ListNet ranking loss.
            f=z.shape[-1]
            self.linear=torch.nn.Linear(f,1,bias=False)
            self.hidden=torch.nn.Linear(f,4); self.output=torch.nn.Linear(4,1)
            params=list(self.linear.parameters())+list(self.hidden.parameters())+list(self.output.parameters())
            opt=torch.optim.AdamW(params,lr=.01,weight_decay=.03)
            tx=torch.tensor(z); target=torch.softmax(torch.tensor(np.clip(y,-3,3),dtype=torch.float32),dim=1)
            for _ in range(160):
                opt.zero_grad(); pred=self.linear(tx).squeeze(-1)+self.output(torch.tanh(self.hidden(tx/np.sqrt(f)))).squeeze(-1)
                loss=-(target*torch.log_softmax(pred,dim=1)).sum(dim=1).mean();loss.backward();opt.step()
        else: raise ValueError('unsupported ranker')
        return self

    def predict(self,x):
        z=np.clip((x-self.mean)/self.scale,-10,10).astype('float32')
        if self.kind=='ridge': pred=z@self.coef+self.bias
        elif self.kind=='lgbm_rank': pred=getattr(self.model,'booster_',self.model).predict(z.reshape(-1,z.shape[-1]),num_threads=2).reshape(z.shape[:2])
        else:
            import torch
            with torch.no_grad():
                tx=torch.tensor(z);pred=(self.linear(tx).squeeze(-1)+self.output(torch.tanh(self.hidden(tx/np.sqrt(z.shape[-1])))).squeeze(-1)).numpy()
        return (pred-pred.mean(axis=1,keepdims=True))/np.maximum(pred.std(axis=1,keepdims=True),1e-6)

    def save(self,path):
        meta=dict(kind=self.kind,parameters=self.parameters,mean=self.mean.tolist(),scale=self.scale.tolist())
        if self.kind=='ridge': meta.update(coef=self.coef.tolist(),bias=float(self.bias))
        elif self.kind=='lgbm_rank': self.model.booster_.save_model(str(path.with_suffix('.lgbm.txt')))
        else:
            meta['weights']={name:{k:v.detach().numpy().tolist() for k,v in model.state_dict().items()}
                for name,model in [('linear',self.linear),('hidden',self.hidden),('output',self.output)]}
        path.write_text(json.dumps(meta,indent=2))

    @classmethod
    def load(cls,path):
        raw=json.loads(path.read_text());self=cls(raw['kind'],raw.get('parameters'));self.mean=np.array(raw['mean']);self.scale=np.array(raw['scale'])
        if self.kind=='ridge': self.bias=raw['bias'];self.coef=np.array(raw['coef'])
        elif self.kind=='lgbm_rank':
            import lightgbm as lgb
            self.model=lgb.Booster(model_file=str(path.with_suffix('.lgbm.txt')))
        else:
            import torch
            self.linear=torch.nn.Linear(len(self.mean),1,bias=False);self.hidden=torch.nn.Linear(len(self.mean),4);self.output=torch.nn.Linear(4,1)
            for name in ('linear','hidden','output'):
                getattr(self,name).load_state_dict({k:torch.tensor(v,dtype=torch.float32) for k,v in raw['weights'][name].items()})
        return self


def features_at(ohlcv,starts):
    """Only closed bars before each decision; all volume is quote currency."""
    close=ohlcv[:,:,3]; result=[]
    names=['ret1','ret6','ret24','ret72','ret168','ret336','vol24','vol168','range','body','clv','volume_log',
           'volume_change','ma24_distance','residual24','residual168','market24','breadth24','downside168']
    for i in starts:
        if i<337: raise ValueError('insufficient feature warmup')
        last=ohlcv[i-1]; returns=np.diff(np.log(close[i-169:i]),axis=0)
        momentum=[close[i-1]/close[i-1-h]-1 for h in (1,6,24,72,168,336)]
        market=returns.mean(axis=1);beta=np.mean((returns-returns.mean(axis=0))* (market-market.mean())[:,None],axis=0)/max(market.var(),1e-10)
        beta=np.clip(beta,-4,4); span=np.maximum(last[:,1]-last[:,2],1e-10)
        result.append(np.stack([*momentum,returns[-24:].std(axis=0),returns.std(axis=0),span/last[:,3],last[:,3]/last[:,0]-1,
            (2*last[:,3]-last[:,1]-last[:,2])/span,np.log1p(ohlcv[i-24:i,:,4].mean(axis=0)),
            np.log1p(ohlcv[i-24:i,:,4].mean(axis=0))-np.log1p(ohlcv[i-168:i,:,4].mean(axis=0)),
            close[i-1]/close[i-24:i].mean(axis=0)-1,momentum[2]-beta*momentum[2].mean(),
            momentum[4]-beta*momentum[4].mean(),np.full(close.shape[1],momentum[2].mean()),
            np.full(close.shape[1],np.mean(momentum[2]>0)),np.sqrt(np.mean(np.minimum(returns,0)**2,axis=0))],axis=-1))
    x=np.asarray(result)
    if not np.isfinite(x).all(): raise ValueError('nonfinite causal features')
    return x,names
