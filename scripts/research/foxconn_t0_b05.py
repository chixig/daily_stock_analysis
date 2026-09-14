#!/usr/bin/env python3
"""Fixed causal conditional probability study, GitHub execution only."""
import os,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old
import foxconn_t0_b04 as b4
ROOT=Path("research/foxconn_t0_20260915_b05")
PRE=Path("research/foxconn_t0_20260913")
B2=Path("research/foxconn_t0_20260913_b02")
B4=Path("research/foxconn_t0_20260913_b04")
BASE=["clv","logvolume","intraday1","ret5","market1","relative5"]
COLS={"P6":BASE,"P9":BASE+["weak","weak_clv","weak_ret5"],
      "A8":BASE+["gap","gap_clv"],"A12":BASE+["weak","weak_clv","weak_ret5","gap","gap_clv","gap_weak"]}
def save(name,x):
    t=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x)
    t.to_csv(ROOT/name,index=False);return t
def dump(name,x):
    def clean(v):
        if isinstance(v,dict):return {str(k):clean(z) for k,z in v.items()}
        if isinstance(v,(list,tuple)):return [clean(z) for z in v]
        if isinstance(v,(np.integer,)):return int(v)
        if isinstance(v,(np.bool_,)):return bool(v)
        if isinstance(v,(float,np.floating)):return float(v) if np.isfinite(v) else None
        if isinstance(v,(pd.Timestamp,pd.Period)):return str(v)
        return v
    (ROOT/name).write_text(json.dumps(clean(x),indent=2,allow_nan=False))
def features(d,ix):
    c=d.signal_close
    clv=((d.close-d.low)/(d.high-d.low)).where(d.high!=d.low,.5).shift()
    vr=(d.volume/d.volume.rolling(20).mean()).shift()
    r5=(100*(c/c.shift(5)-1)).shift()
    weak=b4.causal(d).DD2.astype(float)
    f=pd.DataFrame(dict(clv=clv,logvolume=np.log(vr),intraday1=(100*np.log(d.close/d.open)).shift(),
        ret5=r5,market1=100*ix.pct_change().shift(),
        relative5=r5-(100*(ix/ix.shift(5)-1)).shift(),weak=weak,
        gap=100*(d.open/d.preclose-1)))
    f["weak_clv"]=weak*clv;f["weak_ret5"]=weak*r5
    f["gap_clv"]=f.gap*clv;f["gap_weak"]=f.gap*weak
    return f
def sigmoid(x):return 1/(1+np.exp(-np.clip(x,-35,35)))
def fit(x,y,z):
    mu=x.mean(axis=0);sd=x.std(axis=0);sd=np.where(sd<1e-8,1.,sd)
    X=np.column_stack([np.ones(len(x)),np.clip((x-mu)/sd,-5,5)])
    penalty=np.eye(X.shape[1])*10;penalty[0,0]=0
    w=np.zeros(X.shape[1]);p0=np.clip(y.mean(),1e-6,1-1e-6);w[0]=np.log(p0/(1-p0))
    for it in range(100):
        p=sigmoid(X@w)
        h=X.T@(X*np.maximum(p*(1-p),1e-8)[:,None])+penalty
        step=np.linalg.solve(h,X.T@(p-y)+penalty@w)
        w-=step
        if np.max(np.abs(step))<1e-8:break
    else:raise AssertionError("IRLS did not converge")
    v=np.linalg.solve(X.T@X+penalty,X.T@z)
    return mu,sd,w,v,it+1
def predict(state,x):
    mu,sd,w,v,_=state
    X=np.column_stack([np.ones(len(x)),np.clip((x-mu)/sd,-5,5)])
    return sigmoid(X@w),X@v
def forecast(d,f,y,z):
    pred=pd.DataFrame(index=d.index);folds=[];coefs=[]
    for key,cols in COLS.items():
        x=f[cols].to_numpy(float);valid=np.isfinite(x).all(axis=1)
        pp=np.full(len(d),np.nan);ev=pp.copy();base=pp.copy()
        for month in sorted(d.loc[d.date.ge("2020-01-01"),"date"].dt.to_period("M").unique()):
            test=np.flatnonzero(valid&d.date.dt.to_period("M").eq(month).to_numpy())
            train=np.flatnonzero(valid&d.date.lt(month.start_time).to_numpy())[-504:]
            if len(train)<252 or not len(test):continue
            assert d.date.iloc[train[-1]]<d.date.iloc[test[0]]
            state=fit(x[train],y[train],z[train])
            pp[test],ev[test]=predict(state,x[test]);base[test]=y[train].mean()
            folds.append(dict(model=key,month=str(month),train_n=len(train),
                train_start=d.date.iloc[train[0]],train_end=d.date.iloc[train[-1]],
                prediction_start=d.date.iloc[test[0]],n=len(test),iterations=state[-1]))
            for j,col in enumerate(["intercept"]+cols):
                coefs.append(dict(model=key,month=str(month),feature=col,logistic_coef=state[2][j],net_return_coef=state[3][j]))
        pred[key+"_p"]=pp;pred[key+"_ev"]=ev;pred[key+"_base"]=base
    return pred,folds,coefs
def probstats(g,full):
    if not len(g):return dict(n=0,down_pct=None,lift_pp=None)
    allmonths=sorted(full.date.dt.to_period("M").unique())
    def agg(x):
        return x.assign(month=x.date.dt.to_period("M")).groupby("month").down.agg(["sum","count"]).reindex(allmonths,fill_value=0).to_numpy()
    a,b=agg(g),agg(full)
    rng=np.random.default_rng(601138);ix=rng.integers(0,len(a),(2000,len(a)))
    aa=a[ix].sum(axis=1);bb=b[ix].sum(axis=1);ok=aa[:,1]>0
    rate=aa[ok,0]/aa[ok,1];lift=rate-bb[ok,0]/bb[ok,1]
    rateci=np.quantile(100*rate,[.025,.975]);liftci=np.quantile(100*lift,[.025,.975])
    wins=g[g.rt_cash>0];losses=g[g.rt_cash<=0]
    return dict(n=len(g),down_pct=float(100*g.down.mean()),baseline_down_pct=float(100*full.down.mean()),
        lift_pp=float(100*(g.down.mean()-full.down.mean())),down_ci_low=rateci[0],down_ci_high=rateci[1],
        lift_ci_low=liftci[0],lift_ci_high=liftci[1],net_RT_win_pct=float(100*(g.rt_cash>0).mean()),
        net_RT_mean_pct=float(g.rt_pct.mean()),net_RT_cash=float(g.rt_cash.sum()),
        mean_net_winner_pct=float(wins.rt_pct.mean()) if len(wins) else None,
        mean_net_loser_pct=float(losses.rt_pct.mean()) if len(losses) else None)
def scores(y,p):
    p=np.clip(p,1e-8,1-1e-8)
    n1=y.sum();n0=len(y)-n1
    auc=(pd.Series(p).rank().to_numpy()[y==1].sum()-n1*(n1+1)/2)/(n1*n0) if n1*n0 else None
    return dict(brier=float(np.mean((p-y)**2)),logloss=float(np.mean(-y*np.log(p)-(1-y)*np.log(1-p))),auc=auc)
def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true"
    ROOT.mkdir(parents=True,exist_ok=True)
    parents={}
    for root,file,key in [(PRE,"results/daily_features_and_cashflows.csv","sha256"),
                           (B2,"source/sse_index.csv","files"),(B4,"daily_audit.csv","files")]:
        p=root/file;h=hashlib.sha256(p.read_bytes()).hexdigest()
        assert h==json.loads((root/"manifest.json").read_text())[key][str(p)]
        parents[str(p)]=h
    d=pd.read_csv(PRE/"results/daily_features_and_cashflows.csv",parse_dates=["date"])
    a=pd.read_csv(B4/"daily_audit.csv",parse_dates=["date"])
    pd.testing.assert_series_equal(d.date,a.date)
    d["later_open"]=a.later_open
    ix=d.date.map(pd.read_csv(B2/"source/sse_index.csv",parse_dates=["date"]).set_index("date").close)
    assert len(d)==2007 and str(d.date.max().date())=="2026-09-11"
    d["down"]=(d.close<d.open).astype(int)
    f=features(d,ix)
    np.testing.assert_array_equal(f.weak,a.DD2.astype(float))
    for cut in [900,1600]:
        alt=d.copy();alt["volume"]=alt.volume.astype(float);alt.loc[cut:,["open","high","low","close","signal_close","volume"]]*=1.31
        fx=features(alt,ix)
        np.testing.assert_allclose(f.loc[cut,COLS["P9"]],fx.loc[cut,COLS["P9"]],atol=1e-12)
        np.testing.assert_allclose(features(d.iloc[:cut+1],ix.iloc[:cut+1]).iloc[-1],f.iloc[cut],atol=1e-12)
    old.tests()
    xx=np.linspace(-2,2,100)[:,None];yy=(xx[:,0]>0).astype(float)
    ss=fit(xx,yy,np.full(100,-.2));p,z=predict(ss,np.array([[-1.],[1.]]))
    assert p[0]<p[1];np.testing.assert_allclose(z,[-.2,-.2],atol=1e-8)
    y=d.down.to_numpy(float);z=d.rt_pct.to_numpy(float)
    pred,folds,coefs=forecast(d,f,y,z)
    # Real pipeline refit with future outcomes changed: past and cutoff predictions must agree.
    cut=d.index[d.date.ge("2025-01-02")][0]
    ya=y.copy();za=z.copy();ya[cut:]=1-ya[cut:];za[cut:]*=-5
    changed,_,_=forecast(d,f,ya,za)
    np.testing.assert_allclose(pred.iloc[:cut+1],changed.iloc[:cut+1],equal_nan=True)
    primary=d.date.ge("2024-01-02")
    assert pred.loc[primary].notna().all().all()
    assert (pred[[k+"_p" for k in COLS]].stack().between(0,1)).all()
    windows={"full_2020":d.date.ge("2020-01-01"),"primary":primary}
    windows.update({str(y):d.date.dt.year.eq(y) for y in [2024,2025,2026]})
    high=f.clv.ge(.8);low=f.clv.le(.2);vol=f.logvolume.ge(np.log(1.5));weak=f.weak.eq(1)
    gp=f.gap.ge(1);gn=f.gap.le(-1)
    cond={"ALL":pd.Series(True,index=d.index),"weak":weak,"notweak":~weak,"highCLV":high,"lowCLV":low,
          "highVolume":vol,"highCLV_highVolume":high&vol,"weak_highCLV":weak&high,"weak_lowCLV":weak&low,
          "gapDown1":gn,"gapUp1":gp,"gapUp1_highCLV":gp&high,"gapUp1_highVolume":gp&vol,"gapDown1_lowCLV":gn&low}
    assert len(cond)==14
    probs=[];cal=[];evals=[];rules={}
    for key,m in cond.items():
        for win,wm in windows.items():
            probs.append(dict(condition=key,timing="after_auction" if key.startswith("gap") else "previous_close",
                window=win,**probstats(d[m&wm],d[wm])))
    for key in COLS:
        for threshold in [.55,.6]:
            rules[key+"_"+str(round(threshold*100))]=(pred[key+"_p"]>=threshold)&pred[key+"_ev"].gt(0)
        for win,wm in windows.items():
            mask=wm&pred[key+"_p"].notna();yy=y[mask];pp=pred.loc[mask,key+"_p"].to_numpy()
            sc=scores(yy,pp);base=scores(yy,pred.loc[mask,key+"_base"].to_numpy())
            evals.append(dict(model=key,window=win,n=len(yy),predicted_down_pct=float(100*pp.mean()),
                actual_down_pct=float(100*yy.mean()),**sc,baseline_brier=base["brier"],baseline_logloss=base["logloss"],
                brier_improvement=base["brier"]-sc["brier"]))
            bins=[0,.4,.5,.55,.6,.65,1.000001]
            for left,right in zip(bins[:-1],bins[1:]):
                bm=mask&pred[key+"_p"].ge(left)&pred[key+"_p"].lt(right)
                cal.append(dict(model=key,window=win,bin=f"[{left},{min(right,1)})",
                    predicted_pct=float(100*pred.loc[bm,key+"_p"].mean()) if bm.any() else None,
                    **probstats(d[bm],d[mask])))
    assert len(rules)==8
    rows=[];mirrors=[]
    for key,m in dict(cond,**rules).items():
        for win,wm in windows.items():
            g=d[m&wm]
            rows.append(dict(id=key,kind="model_trade" if key in rules else "condition",
                timing="after_auction" if (key.startswith("gap") or (key in rules and key.startswith("A"))) else "previous_close",window=win,
                **{**probstats(g,d[wm]),**b4.metrics(g)}))
            for direction in ["rt","pt"]:
                v=old.metrics(g,direction)
                if v["n"] and v["mean_pct"]<0:
                    opp="pt" if direction=="rt" else "rt"
                    mirrors.append(dict(id=key,window=win,losing_direction=direction,large=v["mean_pct"]<=-.5,
                        losing_mean=v["mean_pct"],opposite_direction=opp,**old.metrics(g,opp)))
    stats=save("condition_and_trade_economics.csv",rows)
    prob=save("conditional_probabilities.csv",probs);ct=save("calibration.csv",cal);ev=save("model_evaluation.csv",evals)
    save("mirror_registry.csv",mirrors);save("monthly_training.csv",folds);coef=save("coefficients.csv",coefs)
    da=pd.concat([d[["date","open","close","down","rt_pct","rt_cash","pt_pct","pt_cash","later_open"]],f,pred],axis=1)
    for key,m in rules.items():da[key]=m
    save("daily_predictions.csv",da)
    baseline=b4.metrics(d[a.PT_frozen&primary],"pt")
    assert baseline["n"]==72 and abs(baseline["cash"]-45428.671)<.01
    stable=[]
    for key in cond:
        if key=="ALL":continue
        r=prob[(prob.condition==key)&prob.window.eq("primary")].iloc[0]
        yrs=prob[prob.condition.eq(key)&prob.window.isin(["2024","2025","2026"])]
        stable.append(dict(condition=key,n=int(r.n),historical_probability_signal=bool(r.n>=30 and r.lift_ci_low>0 and
             (yrs.n.ge(5)&yrs.lift_pp.gt(0)).all()),trade_profit_positive=bool(r.net_RT_mean_pct>0 and r.net_RT_cash>0)))
    st=save("condition_followup.csv",stable)
    audit=dict(data_end="2026-09-11",primary_days=int(primary.sum()),conditions=len(cond),models=len(COLS),trade_masks=len(rules),
        input_hashes=parents,all_primary_predictions_available=True,feature_mutation_and_prefix="passed900/1600",
        future_target_pipeline_invariance="passed through2025-01-02",synthetic_fit_and_costs="passed",
        fold_chronology="all train ends before prediction month",max_iterations=max(x["iterations"] for x in folds),
        frozen_PT=baseline,probability_followup=st[st.historical_probability_signal].condition.tolist(),
        negative_mirror_rows=len(mirrors),large_mirror_rows=sum(x["large"] for x in mirrors),
        limitations=["already-inspected history","descriptive month intervals not multiple-search adjusted",
            "auction-open features cannot certify auction execution","5minute proxy not fills","no current new data or live trading"])
    dump("audit.json",audit)
    report=["# B05 conditional open-to-close decline probability",
      "Historical data through2026-09-11. Probability target is close<open, not any intraday dip. All calculations on GitHub.",
      "## Primary conditional probabilities",old.md_table(prob[prob.window.eq("primary")]),
      "## Annual conditional probabilities",old.md_table(prob[prob.window.isin(["2024","2025","2026"])]),
      "## Primary model evaluation",old.md_table(ev[ev.window.eq("primary")]),
      "## Primary probability calibration",old.md_table(ct[ct.window.eq("primary")]),
      "## Primary model trade outcomes",old.md_table(stats[stats.window.eq("primary")&stats.kind.eq("model_trade")]),
      "## Primary condition economics",old.md_table(stats[stats.window.eq("primary")&stats.kind.eq("condition")]),
      "## Follow-up diagnostic, not statistical certification",old.md_table(st),
      "## Last fitted coefficients, standardized and observational",old.md_table(coef[coef.month.eq(coef.month.max())]),
      "## Audit",json.dumps(audit,indent=2,default=str)]
    (ROOT/"REPORT.md").write_text("\n\n".join(report))
    dump("manifest.json",dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],
        contract_sha256=hashlib.sha256(Path("DOCS/FOXCONN_T0_B05.md").read_bytes()).hexdigest(),
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!="manifest.json"}))
    print(json.dumps(audit,indent=2,default=str))
if __name__=="__main__":run()
