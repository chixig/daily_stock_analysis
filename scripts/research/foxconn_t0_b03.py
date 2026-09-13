#!/usr/bin/env python3
"""Batch03: fixed factor audit, paired PT comparison, and return attribution. GitHub only."""
import os,json,hashlib,zipfile,io,urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old

ROOT=Path("research/foxconn_t0_20260913_b03")
OUT=ROOT/"results"
SOURCE=ROOT/"source"
PRE=Path("research/foxconn_t0_20260913")
B2=Path("research/foxconn_t0_20260913_b02")
CONTRACT={
 "content_id":"foxconn-t0-20260913-b03","data_end":"2026-09-11",
 "primary":"2024-01-02 through 2026-09-11","historical_audit":"2020 onward; 2023 and 2021-22 separate",
 "stage":"unchanged frozen positive V1, known at previous close; V3 not used for selection",
 "factor_count":38,"tails":"causal rolling 252 available observations, min126, <=20th and >=80th percentile ranks",
 "scopes":["ALL","U","R","D","C"],"composites":6,
 "max_rules":410,"selection":"no threshold search, all results retained, no true new OOS",
 "screen":{"n":30,"event_clusters_gap5":12,"mean_net_pct":0.3,"cash_pf":1.5,
           "each_2024_2025_2026_n":5,"each_year_net_mean":"positive","delete_top5_net_mean_and_cash":"positive",
           "double_slippage":"positive","delayed_0935_proxy":"positive","month_wild_maxT_p":0.05},
 "screen_meaning":"research promotion hurdle fixed before run, not proof all other strategies impossible",
 "multiplicity":"5000 calendar-month shared Rademacher wild draws, centered monthly scores; maxT across all eligible rules; within-batch only",
 "walk_forward":"for each 2024/25/26 train only 2020..prior year, n>=30 and PF>=1.3; choose highest mean, tie id; top1 only, no retuning",
 "price_models":"O-C benchmark and 09:35 approximate next-bar open; after-open factors cannot trade at auction O",
 "US":"latest NY16:00 close before Shanghai09:25, max7 days stale; FRED or identical Yahoo index fallback, current vintage; historical publication timestamps unverified",
 "PT":"frozen U1/R1/D1/C1 direction layer only; fixed1000 shares for comparison, not original position schedule or discretionary confirmation",
 "attribution":"log(C/preclose)=log(O/preclose)+log(C/O); raw prior actual close and corporate-action adjustment separately",
 "mirror":"all negative cells paired with independently costed opposite direction; large flag <=-0.5pct",
 "stop":"if no qualifying literal-open RT rule, conclude not adopted in this defined scope, not universal mathematical impossibility"
}

def save(name,obj):
    (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str),encoding="utf8")

def safe_corr(a,b):
    x=pd.concat([a,b],axis=1).dropna()
    return float(x.iloc[:,0].rank().corr(x.iloc[:,1].rank())) if len(x)>=15 and x.iloc[:,0].nunique()>2 else np.nan

def us_source(d,series):
    fred=f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series}&cosd=2018-01-01&coed=2026-09-11"
    symbol="%5EIXIC" if series=="NASDAQCOM" else "%5ESOX"
    t1=int(pd.Timestamp("2018-01-01",tz="UTC").timestamp())
    t2=int(pd.Timestamp("2026-09-12",tz="UTC").timestamp())
    yahoo=f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}?period1={t1}&period2={t2}&interval=1d"
    attempts=[]
    a=None
    # Two prior FRED attempts timed out; try a fixed alternate source for the same index, not a new factor.
    for provider,url in [("Yahoo same Nasdaq index",yahoo),("FRED",fred)]:
      try:
        req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"})
        data=urllib.request.urlopen(req,timeout=20).read()
        if provider=="FRED":
            a=pd.read_csv(io.BytesIO(data));a.columns=["date","value"]
        else:
            j=json.loads(data)["chart"]["result"][0]
            a=pd.DataFrame({"date":pd.to_datetime(j["timestamp"],unit="s",utc=True).tz_convert("America/New_York").date,
               "value":j["indicators"]["quote"][0]["close"]})
            (SOURCE/(series+"_yahoo.json")).write_bytes(data)
        a.date=pd.to_datetime(a.date);a.value=pd.to_numeric(a.value,errors="coerce")
        a=a.dropna().sort_values("date")
        a=a[a.date.le("2026-09-11")]
        assert len(a)>500 and not a.date.duplicated().any()
        a.to_csv(SOURCE/(series+".csv"),index=False)
        attempts.append(dict(provider=provider,status="available",source=url))
        break
      except Exception as e:
        a=None;attempts.append(dict(provider=provider,status="unavailable",reason=str(e)[:250],source=url))
    if a is None:
        return pd.Series(np.nan,index=d.index),dict(series=series,status="unavailable",attempts=attempts)
    a["ret"]=a.value.pct_change()
    a["available"]=(a.date+pd.Timedelta(hours=16)).dt.tz_localize("America/New_York").dt.tz_convert("UTC")
    q=pd.DataFrame({"decision":(d.date+pd.Timedelta(hours=9,minutes=25)).dt.tz_localize("Asia/Shanghai").dt.tz_convert("UTC")})
    z=pd.merge_asof(q,a[["available","ret"]],left_on="decision",right_on="available",direction="backward",tolerance=pd.Timedelta(days=7))
    assert (z.available.dropna()<z.loc[z.available.notna(),"decision"]).all()
    z.to_csv(OUT/(series+"_alignment.csv"),index=False)
    return z.ret.set_axis(d.index),dict(series=series,status="available",rows=len(a),attempts=attempts,vintage="current vendor, not publication-vintage certified")

def build_features(d,ix,mp,us):
    c=d.signal_close;o=d.open*c/d.close;h=d.high*c/d.close;l=d.low*c/d.close;v=d.volume
    r=c.pct_change();rng=(h-l).replace(0,np.nan)
    tr=pd.concat([h-l,(h-c.shift()).abs(),(l-c.shift()).abs()],axis=1).max(axis=1)
    m20=c.rolling(20).mean()
    cc=np.log(d.close/d.preclose);oc=np.log(d.close/d.open);ng=np.log(d.open/d.preclose)
    retix=ix.pct_change()
    clv=((c-l)/rng).fillna(.5)
    raw={}
    for n in [1,3,5,10,20]:raw["ret"+str(n)]=c.pct_change(n)
    raw.update(bias5=c/c.rolling(5).mean()-1,bias20=c/m20-1,
       ma20slope5=m20/m20.shift(5)-1,range_pos20=(c-l.rolling(20).min())/(h.rolling(20).max()-l.rolling(20).min()),
       drawdown60=c/c.rolling(60).max()-1,
       overnight5=ng.rolling(5).sum(),intraday5=oc.rolling(5).sum(),overnight_minus_intraday5=(ng-oc).rolling(5).sum(),
       volume_ratio=v/v.rolling(20).mean(),volume_trend=v.rolling(5).mean()/v.rolling(20).mean(),
       signed_volume5=(np.sign(r)*v).rolling(5).sum()/v.rolling(5).sum(),
       volume_price_corr20=r.rolling(20).corr(v.pct_change()),
       amihud20=(r.abs()/(d.close*v).replace(0,np.nan)).rolling(20).mean(),
       atr20=tr.rolling(20).mean()/c,rv5_20=r.rolling(5).std()/r.rolling(20).std(),
       downside_share20=r.clip(upper=0).pow(2).rolling(20).sum()/r.pow(2).rolling(20).sum(),
       range_expansion=(h-l)/tr.rolling(20).mean(),
       body=(c-o)/rng,clv=clv,upper_shadow=(h-pd.concat([c,o],axis=1).max(axis=1))/rng,
       lower_shadow=(pd.concat([c,o],axis=1).min(axis=1)-l)/rng,clv3=clv.rolling(3).mean(),
       market_ret1=retix,market_ret5=ix.pct_change(5),relative_ret5=c.pct_change(5)-ix.pct_change(5),
       beta_residual1=r-(r.rolling(60).cov(retix)/retix.rolling(60).var()).shift(1)*retix)
    # Each domestic feature formed at the previous close.
    f=pd.DataFrame(raw,index=d.index).shift(1)
    # Daily aligned minute values must shift by one stock trading day, never skip missing dates.
    f["prev_late_return"]=mp.late.shift(1)
    f["prev_am_return"]=mp.am.shift(1)
    f["prev_pm_minus_am"]=(mp.pm-mp.am).shift(1)
    for k,val in us.items():f[k]=val
    f["current_gap"]=d.open/d.preclose-1
    f["gap_over_atr"]=f.current_gap/(tr.rolling(20).mean()/c).shift(1)
    return f.replace([np.inf,-np.inf],np.nan)

def decompose(d):
    a=d.copy()
    a["log_day"]=np.log(a.close/a.preclose)
    a["log_night"]=np.log(a.open/a.preclose)
    a["log_intraday"]=np.log(a.close/a.open)
    a["log_raw_night"]=np.log(a.open/a.close.shift(1))
    a["log_action"]=np.log(a.preclose/a.close.shift(1))
    assert np.max(np.abs(a.log_day-a.log_night-a.log_intraday))<1e-12
    assert np.nanmax(np.abs(a.log_raw_night-a.log_night-a.log_action))<1e-12
    a["stage_contemporaneous_hindsight"]=old.stage(a.signal_close,"frozen").shift(-1)
    # This label includes today's close and is strictly descriptive.
    rows=[]
    for w,mw in windows(a).items():
      for label in ["stage","stage_contemporaneous_hindsight"]:
       for st in ["ALL","U","R","D","C"]:
        g=a[mw&(a[label].eq(st) if st!="ALL" else True)]
        if g.empty:continue
        row=dict(window=w,label=label,stage=st,n=len(g),previous20_mean_pct=float((100*(a.signal_close/a.signal_close.shift(20)-1).shift(1))[g.index].mean()))
        for col in ["day","night","intraday","raw_night","action"]:
            x=g["log_"+col]
            row[col+"_mean_log_bp"]=float(x.mean()*10000)
            row[col+"_linked_pct"]=float(np.expm1(x.sum())*100)
        row["daily_down_pct"]=float(g.log_day.lt(0).mean()*100)
        row["intraday_down_pct"]=float(g.log_intraday.lt(0).mean()*100)
        row["night_down_pct"]=float(g.log_night.lt(0).mean()*100)
        row["rt_net_mean_pct"]=float(g.rt_pct.mean());row["pt_net_mean_pct"]=float(g.pt_pct.mean())
        row["gross_rt_arith_mean_pct"]=float((100*(1-g.close/g.open)).mean())
        row["remove5_worst_daily_mean_log_bp"]=float(g.log_day.sort_values().iloc[5:].mean()*10000) if len(g)>5 else None
        rows.append(row)
    pd.DataFrame(rows).to_csv(OUT/"return_attribution.csv",index=False)
    episodes=[]
    ids=a.stage.ne(a.stage.shift()).cumsum()
    for _,g in a.groupby(ids):
        if g.stage.iloc[0]!="D" or g.date.iloc[-1]<pd.Timestamp("2020-01-01"):continue
        episodes.append(dict(start=str(g.date.iloc[0].date()),end=str(g.date.iloc[-1].date()),n=len(g),
             day_pct=float(np.expm1(g.log_day.sum())*100),night_pct=float(np.expm1(g.log_night.sum())*100),
             intraday_pct=float(np.expm1(g.log_intraday.sum())*100),rt_cash=float(g.rt_cash.sum())))
    pd.DataFrame(episodes).to_csv(OUT/"D_causal_episodes.csv",index=False)
    # Non-overlapping running-peak drawdowns, ranked ex post only for attribution.
    z=a[a.date.ge("2020-01-01")].copy()
    events=[];peak=z.index[0];trough=peak
    for idx in z.index[1:]:
        if z.loc[idx,"signal_close"]>=z.loc[peak,"signal_close"]:
            if trough!=peak:events.append((peak,trough,idx))
            peak=idx;trough=idx
        elif z.loc[idx,"signal_close"]<z.loc[trough,"signal_close"]:trough=idx
    if trough!=peak:events.append((peak,trough,None))
    events.sort(key=lambda e:z.loc[e[1],"signal_close"]/z.loc[e[0],"signal_close"])
    dd=[]
    for peak,trough,recovered in events[:8]:
        g=a.loc[peak+1:trough]
        dd.append(dict(peak=str(a.loc[peak,"date"].date()),trough=str(a.loc[trough,"date"].date()),n=len(g),
          decline_pct=float(np.expm1(g.log_day.sum())*100),night_pct=float(np.expm1(g.log_night.sum())*100),
          intraday_pct=float(np.expm1(g.log_intraday.sum())*100),night_log_sum=float(g.log_night.sum()),
          intraday_log_sum=float(g.log_intraday.sum()),D_days=int(g.stage.eq("D").sum()),
          non_D_days=int((~g.stage.eq("D")).sum()),
          D_day_log=float(g.loc[g.stage.eq("D"),"log_day"].sum()),
          non_D_day_log=float(g.loc[~g.stage.eq("D"),"log_day"].sum()),
          first_D_date=str(g.loc[g.stage.eq("D"),"date"].iloc[0].date()) if g.stage.eq("D").any() else None,
          before_first_D_days=int((g.index<g.loc[g.stage.eq("D")].index[0]).sum()) if g.stage.eq("D").any() else len(g),
          before_first_D_log=float(g.loc[g.index<g.loc[g.stage.eq("D")].index[0],"log_day"].sum()) if g.stage.eq("D").any() else float(g.log_day.sum()),
          hindsight_only=True))
    pd.DataFrame(dd).to_csv(OUT/"hindsight_drawdown_attribution.csv",index=False)
    a[["date","stage","stage_contemporaneous_hindsight","log_day","log_night","log_intraday","log_raw_night","log_action"]].to_csv(OUT/"daily_attribution.csv",index=False)
    return pd.DataFrame(rows),pd.DataFrame(dd)

def windows(d):
    return {"primary":d.date.ge("2024-01-02"),"2023":d.date.dt.year.eq(2023),
       "2021_2022":d.date.dt.year.between(2021,2022),"2024":d.date.dt.year.eq(2024),
       "2025":d.date.dt.year.eq(2025),"2026":d.date.dt.year.eq(2026),
       "original_PT_window":d.date.between("2023-01-03","2026-09-04")}

def boot(g,p="rt"):
    if len(g)<2:return [None,None]
    # Month bootstrap of selected event sums/counts, preserves within-month dependency.
    t=g.groupby(g.date.dt.to_period("M"))[p+"_pct"].agg(["sum","count"]).to_numpy()
    rng=np.random.default_rng(601138)
    ix=rng.integers(0,len(t),(2000,len(t)))
    b=t[ix].sum(axis=1)
    return np.quantile(b[:,0]/b[:,1],[.025,.975]).tolist()

def summarize(d,mask,p="rt",expensive=False):
    g=d[mask];m=old.metrics(g,p)
    m["months"]=int(g.date.dt.to_period("M").nunique())
    if not len(g):return m
    x=g[p+"_pct"];cash=g[p+"_cash"]
    m["delete5_pct"]=float(x.sort_values().iloc[:-5].mean()) if len(g)>5 else np.nan
    m["delete5_cash"]=float(cash.sort_values().iloc[:-5].sum()) if len(g)>5 else np.nan
    m["stress10bp_pct"]=float((100*old.cashflow(g.open,g.close,g.date,p.upper(),.001)/(1000*g.open)).mean())
    delayed=g[g.later_open.notna()]
    m["delayed_n"]=len(delayed)
    m["delayed_pct"]=float((100*old.cashflow(delayed.later_open,delayed.close,delayed.date,p.upper())/(1000*delayed.open)).mean()) if len(delayed) else np.nan
    m["delayed_cash"]=float(old.cashflow(delayed.later_open,delayed.close,delayed.date,p.upper()).sum()) if len(delayed) else np.nan
    m["max_cash_loss"]=float(min(cash.min(),0))
    if expensive:m["month_ci"]=boot(g,p)
    return m

def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true","Market processing must run on GitHub"
    OUT.mkdir(parents=True,exist_ok=True);SOURCE.mkdir(exist_ok=True)
    (ROOT/"CONTRACT.json").write_text(json.dumps(CONTRACT,indent=2))
    old.tests()
    parents={}
    for root,names,key in [(PRE,["results/daily_features_and_cashflows.csv","source/601138-full-5min-history.zip"],"sha256"),(B2,["source/sse_index.csv"],"files")]:
        man=json.loads((root/"manifest.json").read_text())
        for name in names:
            path=root/name;sha=hashlib.sha256(path.read_bytes()).hexdigest()
            assert sha==man[key][str(path)],str(path)
            parents[str(path)]=sha
    d=pd.read_csv(PRE/"results/daily_features_and_cashflows.csv",parse_dates=["date"])
    d=d.sort_values("date").reset_index(drop=True)
    assert d.date.max()==pd.Timestamp("2026-09-11") and not d.date.duplicated().any()
    assert d.stage.equals(old.stage(d.signal_close,"frozen"))
    ixraw=pd.read_csv(B2/"source/sse_index.csv",parse_dates=["date"]).set_index("date").close
    ix=d.date.map(ixraw).astype(float)
    assert ix[d.date.ge("2020-01-01")].notna().all()
    with zipfile.ZipFile(PRE/"source/601138-full-5min-history.zip") as z:
        minute=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith("601138_5min_all.csv"))))
    minute.date=pd.to_datetime(minute.date)
    minute["clock"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S").dt.strftime("%H:%M")
    minute=minute.sort_values(["date","clock"])
    minute[["open","high","low","close"]]=minute[["open","high","low","close"]].apply(pd.to_numeric,errors="raise")
    piv=minute.pivot(index="date",columns="clock",values="close")
    first=minute.groupby("date").first();last=minute.groupby("date").last()
    quality=pd.DataFrame(index=pd.DatetimeIndex(d.date))
    for col in ["open","close"]:quality[col]=(first.open if col=="open" else last.close).reindex(quality.index).to_numpy()
    quality["valid"]=(abs(quality.open.to_numpy()-d.open.to_numpy())<=.01)&(abs(quality.close.to_numpy()-d.close.to_numpy())<=.01)
    mp=pd.DataFrame(index=d.index)
    for name,end,start in [("late","15:00","14:30"),("am","11:30",None),("pm","15:00","11:30")]:
        e=d.date.map(piv[end])
        s=d.open if start is None else d.date.map(piv[start])
        mp[name]=np.log(e/s).where(quality.valid.to_numpy())
    px=minute[minute.clock.eq("09:40")].set_index("date").open
    d["later_open"]=d.date.map(px).where(quality.valid.to_numpy())
    us={};logs=[]
    for sid in ["NASDAQCOM","NASDAQSOX"]:
        v,log=us_source(d,sid);us["us_"+sid]=v;logs.append(log)
    save("US_sources.json",logs)
    f=build_features(d,ix,mp,us)
    assert f.shape[1]==38,f.columns.tolist()
    # Domestic previous-close features: mutate current/future inputs, preserve today's feature.
    previous=[c for c in f if c not in ["current_gap","gap_over_atr","us_NASDAQCOM","us_NASDAQSOX"]]
    for cut in [500,1200,len(d)-1]:
        alt=d.copy()
        alt.loc[cut:,["open","high","low","close","volume","signal_close"]]*=1.27
        fx=build_features(alt,ix,mp,us)
        np.testing.assert_allclose(f.loc[cut,previous].astype(float),fx.loc[cut,previous].astype(float),equal_nan=True)
    ranks=f.rolling(252,min_periods=126).rank(pct=True)
    f.insert(0,"date",d.date)
    f.to_csv(OUT/"daily_factors.csv",index=False)
    ranks.to_csv(OUT/"causal_factor_ranks.csv",index=False)
    rules={};meta={}
    for st in CONTRACT["scopes"]:
      sm=d.stage.eq(st) if st!="ALL" else d.stage.isin(["U","R","D","C"])
      for col in ranks:
       for tail in ["low","high"]:
        key=st+"__"+col+"__"+tail
        rules[key]=sm&(ranks[col].le(.2) if tail=="low" else ranks[col].ge(.8))
        meta[key]=dict(stage=st,factor=col,tail=tail,timing="after_open" if col in ["current_gap","gap_over_atr"] else ("US_preopen_publication_unverified" if col.startswith("us_") else "previous_close"))
      combos={
        "exhaustion":ranks.ret5.ge(.8)&ranks.volume_ratio.ge(.8),
        "distribution":ranks.upper_shadow.ge(.8)&ranks.volume_ratio.ge(.8),
        "weak_rebound":ranks.ret3.ge(.8)&ranks.bias20.le(.2),
        "persistent_sell":ranks.intraday5.le(.2)&ranks.signed_volume5.le(.2),
        "market_relative_weak":ranks.relative_ret5.le(.2)&ranks.market_ret5.le(.2),
        "late_distribution":ranks.prev_late_return.le(.2)&ranks.volume_ratio.ge(.8)}
      for name,mask in combos.items():
        key=st+"__combo_"+name
        rules[key]=sm&mask;meta[key]=dict(stage=st,factor="combo_"+name,tail="fixed",timing="previous_close")
    assert len(rules)==410
    save("rule_registry.json",meta)
    primary=windows(d)["primary"]
    metrics=[];periods=[];mirrors=[];ics=[];bucket=[]
    for key,m in rules.items():
        v=summarize(d,m&primary)
        row=dict(id=key,**meta[key],**v)
        for year in [2024,2025,2026]:
            g=d[m&d.date.dt.year.eq(year)]
            row[str(year)+"_n"]=len(g);row[str(year)+"_pct"]=float(g.rt_pct.mean()) if len(g) else np.nan
        row["basic_pass"]=bool(v["n"]>=30 and v.get("clusters",0)>=12 and v.get("mean_pct",-999)>=.3
          and (v.get("pf_cash") or 0)>=1.5 and v.get("delete5_pct",-999)>0 and v.get("delete5_cash",-999)>0
          and v.get("stress10bp_pct",-999)>0 and v.get("delayed_pct",-999)>0 and v.get("delayed_n",0)==v["n"]
          and all(row[str(y)+"_n"]>=5 and row[str(y)+"_pct"]>0 for y in [2024,2025,2026]))
        metrics.append(row)
        for w,wm in windows(d).items():
            for p in ["rt","pt"]:
                x=old.metrics(d[m&wm],p)
                periods.append(dict(id=key,window=w,direction=p,**x))
                if x["n"] and x["mean_pct"]<0:
                    opp="pt" if p=="rt" else "rt";other=old.metrics(d[m&wm],opp)
                    mirrors.append(dict(id=key,window=w,losing_direction=p,n=x["n"],losing_mean=x["mean_pct"],
                           opposite_mean=other["mean_pct"],opposite_cash=other["cash"],large=x["mean_pct"]<=-.5))
    tab=pd.DataFrame(metrics).set_index("id")
    # Within-batch familywise adjustment shared calendar-month wild bootstrap.
    valid=tab[(tab.n>=30)&(tab.months>=12)].index.tolist()
    g=d[primary];month=pd.get_dummies(g.date.dt.to_period("M"),dtype=float).to_numpy()
    M=np.column_stack([rules[k][primary].to_numpy(float) for k in valid])
    y=g.rt_pct.to_numpy()[:,None];counts=M.sum(axis=0);means=(M*y).sum(axis=0)/counts
    scores=month.T@(M*(y-means))
    se=np.sqrt((scores*scores).sum(axis=0)*len(month.T)/(len(month.T)-1))
    t=np.divide((M*y).sum(axis=0),se,out=np.zeros(len(valid)),where=se>1e-12)
    rng=np.random.default_rng(601138)
    wild=rng.choice([-1.,1.],size=(5000,scores.shape[0]))
    bt=wild@scores/np.where(se>1e-12,se,np.inf)
    maxnull=bt.max(axis=1)
    for j,k in enumerate(valid):
        tab.loc[k,"cluster_t"]=t[j]
        tab.loc[k,"maxT_p"]=(1+np.sum(maxnull>=t[j]))/5001
    tab["statistical_pass"]=tab.basic_pass&tab.maxT_p.lt(.05)
    tab["literal_open_pass"]=tab.statistical_pass&tab.timing.eq("previous_close")
    tab.sort_values(["literal_open_pass","basic_pass","mean_pct"],ascending=False).to_csv(OUT/"factor_rule_results.csv")
    pd.DataFrame(periods).to_csv(OUT/"all_rule_periods_paired.csv",index=False)
    pd.DataFrame(mirrors).to_csv(OUT/"symmetric_mirror_registry.csv",index=False)
    # Continuous predictive ranks and all five fixed buckets; do not select a new threshold.
    for col in ranks:
      for w,wm in windows(d).items():
       for st in ["ALL","U","R","D","C"]:
        m=wm&(d.stage.eq(st) if st!="ALL" else True)&ranks[col].notna()
        ics.append(dict(factor=col,window=w,stage=st,n=int(m.sum()),spearman_rt=safe_corr(ranks.loc[m,col],d.loc[m,"rt_pct"])))
        if w=="primary":
         for b in range(5):
            bm=m&(ranks[col]>b/5)&(ranks[col]<=(b+1)/5)
            bucket.append(dict(factor=col,stage=st,bucket=b+1,**old.metrics(d[bm])))
    pd.DataFrame(ics).to_csv(OUT/"factor_rank_IC.csv",index=False)
    pd.DataFrame(bucket).to_csv(OUT/"factor_quintiles.csv",index=False)
    pd.DataFrame(bucket)[lambda x:x.factor.isin(["clv","clv3","volume_ratio"])&x.stage.eq("ALL")].to_csv(OUT/"interpretable_factor_quintiles.csv",index=False)
    # Detailed robustness for top 12 N>=30 plus all hurdle-pass rows, without promoting them automatically.
    selected=list(dict.fromkeys(tab[tab.n>=30].nlargest(12,"mean_pct").index.tolist()+tab[tab.basic_pass].index.tolist()))
    details=[]
    for key in selected:
        x=summarize(d,rules[key]&primary,expensive=True)
        x["id"]=key;x["maxT_p"]=float(tab.loc[key,"maxT_p"]);details.append(x)
    save("top_rule_robustness.json",details)
    # Yearly causal re-selection is retrospective walk-forward, not unobserved OOS.
    walk=[];wftrades=[]
    for p in ["rt","pt"]:
      for year in [2024,2025,2026]:
        train=d.date.between("2020-01-01",str(year-1)+"-12-31")
        test=d.date.dt.year.eq(year);candidates=[]
        for key,m in rules.items():
            if meta[key]["timing"]!="previous_close":continue
            met=old.metrics(d[m&train],p)
            if met["n"]>=30 and met["mean_pct"]>0 and (met["pf_cash"] or 0)>=1.3:candidates.append((met["mean_pct"],key))
        candidates.sort(key=lambda x:(-x[0],x[1]))
        if candidates:
            best=candidates[0][1];gg=d[rules[best]&test]
            walk.append(dict(direction=p,year=year,selected=best,train_mean=candidates[0][0],**old.metrics(gg,p)))
            for idx,r in gg.iterrows():wftrades.append(dict(direction=p,year=year,id=best,date=r.date,net_pct=r[p+"_pct"],cash=r[p+"_cash"]))
        else:walk.append(dict(direction=p,year=year,selected="NONE",n=0,cash=0))
    pd.DataFrame(walk).to_csv(OUT/"walk_forward_selection.csv",index=False)
    pd.DataFrame(wftrades).to_csv(OUT/"walk_forward_trades.csv",index=False)
    # Frozen positive-T direction matrix; no discretionary confirmation/position sizing reconstructed.
    down=d.signal_close.pct_change().lt(0)
    streak=down.groupby((~down).cumsum()).cumsum().shift(1).fillna(0)
    masksPT={
      "U1":d.stage.eq("U")&d.clv.lt(.4)&d.gap.le(-1),
      "R1":d.stage.eq("R")&streak.ge(3)&d.vr.lt(.8),
      "D1":d.stage.eq("D")&d.clv.lt(.4)&d.gap.le(-1),
      "C1":d.stage.eq("C")&(d.close<d.open).shift(1).fillna(False)&ix.pct_change().shift(1).lt(0)&d.gap.lt(0)}
    masksPT["PT_matrix"]=pd.DataFrame(masksPT).any(axis=1)
    comparisons=[]
    bases={"PT_"+k:(m,"pt") for k,m in masksPT.items()}
    bases.update(RT_UR_volume=(d.stage.isin(["U","R"])&d.vr.ge(1.5),"rt"),
      RT_R_deceleration=(d.stage.eq("R")&d.r5.gt(0)&d.decelerate.astype(bool),"rt"),
      PT_unconditional=(d.stage.isin(["U","R","D","C"]),"pt"),
      RT_unconditional=(d.stage.isin(["U","R","D","C"]),"rt"))
    ledger=[]
    for name,(mask,p) in bases.items():
      for w,wm in windows(d).items():
        z=summarize(d,mask&wm,p,expensive=w=="primary")
        # Serialize intervals separately; no new sizing/margin assumptions hidden in return percentages.
        z["name"]=name;z["window"]=w;z["direction"]=p
        comparisons.append(z)
      for _,r in d[mask&primary].iterrows():
        ledger.append(dict(name=name,date=r.date,stage=r.stage,net_pct=r[p+"_pct"],cash=r[p+"_cash"]))
    pd.DataFrame(comparisons).to_csv(OUT/"PT_RT_comparison.csv",index=False)
    pd.DataFrame(ledger).to_csv(OUT/"comparison_trades.csv",index=False)
    # Same budget scenario: 1000 old shares + a fixed common cash reserve, q1000, no borrowing.
    initial_cash=float((d.loc[primary,"open"]*1000*(1.0005)+np.maximum(d.loc[primary,"open"]*1000*(1.0005)*.0001354,5)+d.loc[primary,"open"]*1000*(1.0005)*.00001).max())
    # Ex-post sufficient-cash benchmark, explicitly not deployable initial-budget advice.
    accounts=[]
    account_bases={k:v for k,v in bases.items() if k in ["PT_PT_matrix","RT_UR_volume","RT_R_deceleration","PT_unconditional","RT_unconditional"]}
    for key in selected[:3]:account_bases["RT_factor_"+key]=(rules[key],"rt")
    for name,(mask,p) in account_bases.items():
        cash=initial_cash;skipped=0;flows=[]
        for _,r in d[primary].iterrows():
            flow=0.
            if mask.loc[r.name]:
                buycost=1000*r.open*1.0005
                buycost+=max(buycost*.0001354,5)+buycost*.00001
                needed=buycost if p=="pt" else max(0,-r.rt_cash)
                if cash+1e-8>=needed:flow=float(r[p+"_cash"])
                else:skipped+=1
            cash+=flow;flows.append(flow)
        acc=np.r_[0,np.cumsum(flows)]
        accounts.append(dict(name=name,initial_common_cash=initial_cash,cash_increment=float(sum(flows)),
              incremental_return_on_initial_stock_plus_cash_pct=float(100*sum(flows)/(initial_cash+1000*d.loc[primary,"open"].iloc[0])),
              skipped=skipped,T_cash_mdd=float((acc-np.maximum.accumulate(acc)).min()),
              boundary="ex-post sufficient reserve; stock/dividend baseline shared, not total account return"))
    pd.DataFrame(accounts).to_csv(OUT/"common_cash_scenario.csv",index=False)

    # Matched-sample execution sensitivity: retain the dropped-date ledger, compare identical dates.
    matched=[];missing=[]
    for name,(mask,p) in bases.items():
        if name in ["PT_unconditional","RT_unconditional"]:continue
        m=mask&primary
        mm=m&d.later_open.notna()
        base=summarize(d,mm,p)
        matched.append(dict(name=name,n=int(mm.sum()),excluded=int((m&~mm).sum()),
          open_mean=base.get("mean_pct"),open_cash=base.get("cash"),
          delayed_mean=base.get("delayed_pct"),delayed_cash=base.get("delayed_cash")))
        for _,r in d[m&~mm].iterrows():
            missing.append(dict(name=name,date=r.date,open=r.open,close=r.close,net_pct=r[p+"_pct"],cash=r[p+"_cash"]))
    pd.DataFrame(matched).to_csv(OUT/"matched_execution_comparison.csv",index=False)
    pd.DataFrame(missing).to_csv(OUT/"execution_excluded_dates.csv",index=False)
    factor_audit=[]
    for col in ranks:
        n=int((primary&ranks[col].notna()).sum())
        ic=safe_corr(ranks.loc[primary,col],d.loc[primary,"rt_pct"])
        factor_audit.append(dict(factor=col,primary_rank_available=n,primary_IC=ic,
             primary_factor_available=int((primary&f[col].notna()).sum()),
             IC2024=safe_corr(ranks.loc[d.date.dt.year.eq(2024),col],d.loc[d.date.dt.year.eq(2024),"rt_pct"]),
             IC2025=safe_corr(ranks.loc[d.date.dt.year.eq(2025),col],d.loc[d.date.dt.year.eq(2025),"rt_pct"]),
             IC2026=safe_corr(ranks.loc[d.date.dt.year.eq(2026),col],d.loc[d.date.dt.year.eq(2026),"rt_pct"])))
    pd.DataFrame(factor_audit).to_csv(OUT/"factor_coverage_IC_summary.csv",index=False)
    gatecounts={
       "n30":int(tab.n.ge(30).sum()),
       "n30_positive":int((tab.n.ge(30)&tab.mean_pct.gt(0)).sum()),
       "n30_mean_ge03":int((tab.n.ge(30)&tab.mean_pct.ge(.3)).sum()),
       "n30_positive_delete5_mean":int((tab.n.ge(30)&tab.mean_pct.gt(0)&tab.delete5_pct.gt(0)).sum()),
       "n30_positive_all3years":int((tab.n.ge(30)&tab.mean_pct.gt(0)&tab["2024_pct"].gt(0)&tab["2025_pct"].gt(0)&tab["2026_pct"].gt(0)).sum()),
       "available_factors":sum(z["primary_rank_available"]>0 for z in factor_audit)}
    save("screen_funnel.json",gatecounts)

    attribution,drawdowns=decompose(d)
    audit=dict(factor_n=38,rule_n=len(rules),nonempty=int(tab.n.gt(0).sum()),n30=int(tab.n.ge(30).sum()),
       basic_pass=int(tab.basic_pass.sum()),statistical_pass=int(tab.statistical_pass.sum()),literal_open_pass=int(tab.literal_open_pass.sum()),
       negative_mean=int(tab.mean_pct.lt(0).sum()),large_negative=int(tab.mean_pct.le(-.5).sum()),
       input_hashes=parents,feature_mutation_tests="passed at 3 historical cutoffs",stage_match=True,
       attribution_identity="passed 1e-12",minute_primary_valid=int((primary&d.later_open.notna()).sum()),
       US=logs,limitations=["history already inspected","current vendor vintage","within-batch multiplicity only","bar proxy not fills","PT direction layer, not discretionary implementation"])
    save("audit.json",audit)
    compact=tab[tab.n.ge(30)].sort_values("mean_pct",ascending=False).head(15).reset_index()
    report=["# Foxconn batch03: factor audit and intraday/overnight attribution",
       "All data processing on GitHub. Data through 2026-09-11. Historical research, not actual trading.",
       "## Audit",json.dumps(audit,indent=2),
       "## Highest RT means among N>=30, not validated recommendations",old.md_table(compact[["id","n","mean_pct","cash","pf_cash","2024_pct","2025_pct","2026_pct","delete5_pct","delayed_pct","maxT_p","basic_pass"]]),
       "## Causal-stage return attribution (primary)",old.md_table(attribution[(attribution.window=="primary")&(attribution.label=="stage")]),
       "## Hindsight peak-trough decomposition (not tradable labels)",old.md_table(drawdowns),
       "## PT versus RT, primary same q1000/cost window",old.md_table(pd.DataFrame(comparisons)[lambda x:x.window.eq("primary")]),
       "## Matched execution (identical dates)",old.md_table(pd.DataFrame(matched)),
       "## Screening funnel",json.dumps(gatecounts,indent=2),
       "## CLV / 3day CLV / volume quintiles, ALL, RT net",old.md_table(pd.DataFrame(bucket)[lambda x:x.factor.isin(["clv","clv3","volume_ratio"])&x.stage.eq("ALL")]),
       "## Retrospective walk-forward",old.md_table(pd.DataFrame(walk)),
       "## Common cash benchmark",old.md_table(pd.DataFrame(accounts)),
       "## Limitations",
       "After-open gap factors must use post-open proxy; US economic closes are time-aligned but FRED historic publication availability is not certified. No literal auction strategy promotion for either category.",
       "Contemporaneous D and peak/trough labels use outcomes and are descriptive only. Linked returns across disjoint D days are attribution, not a contiguous stock/account return.",
       "No qualified rule means not adopted in this tested scope; it does not prove every possible factor fails. Existing positive-T ratings are not certified by this direction-only comparison."]
    (ROOT/"REPORT.md").write_text("\n\n".join(report))
    files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*") if p.is_file() and p.name!="manifest.json"}
    (ROOT/"manifest.json").write_text(json.dumps(dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],files=files),indent=2))
    print((ROOT/"REPORT.md").read_text())

if __name__=="__main__":run()
