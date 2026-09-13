#!/usr/bin/env python3
"""B04: frozen swing reference and causal detection. Market processing on GitHub only."""
import os
import json
import hashlib
import zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old

ROOT = Path("research/foxconn_t0_20260913_b04")
PRE = Path("research/foxconn_t0_20260913")
B2 = Path("research/foxconn_t0_20260913_b02")
SCALES = [.08, .12, .20]

def dump(name, obj):
    def clean(x):
        if isinstance(x, dict): return {str(k):clean(v) for k,v in x.items()}
        if isinstance(x, (list, tuple)): return [clean(v) for v in x]
        if isinstance(x, (np.integer,)): return int(x)
        if isinstance(x, (np.bool_,)): return bool(x)
        if isinstance(x, (float, np.floating)): return float(x) if np.isfinite(x) else None
        if isinstance(x, (pd.Timestamp, pd.Period)): return str(x)
        return x
    (ROOT/name).write_text(json.dumps(clean(obj), indent=2, allow_nan=False))

def save(name, rows):
    tab = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    tab.to_csv(ROOT/name, index=False)
    return tab

def causal(d):
    c=d.signal_close
    factor=c/d.close
    high,low=d.high*factor,d.low*factor
    tr=pd.concat([high-low,(high-c.shift()).abs(),(low-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(20).mean()
    ma5,ma10=c.rolling(5).mean(),c.rolling(10).mean()
    high20=c.rolling(20).max()
    out={"D":old.stage(c,"frozen").eq("D")}
    for k in [2,3]:
        active=False; bottom=0.; entryatr=0.; a=[]
        for i in range(len(d)):
            if i<79:
                a.append(False); continue
            if active:
                bottom=min(bottom,c.iloc[i])
                exit_rebound=c.iloc[i]-bottom>=1.5*entryatr
                exit_ma=c.iloc[i]>ma10.iloc[i] and c.iloc[i-1]>ma10.iloc[i-1]
                if exit_rebound or exit_ma: active=False
            elif (high20.iloc[i]-c.iloc[i])/atr.iloc[i]>=k and c.iloc[i]<ma5.iloc[i]:
                active=True;bottom=c.iloc[i];entryatr=atr.iloc[i]
            a.append(active)
        out[f"DD{k}"]=pd.Series(a,index=d.index).shift(1,fill_value=False)
    for n in [10,20]:
        lo=c.shift().rolling(n).min()
        hi=c.shift().rolling(5).max()
        slope=ma5<ma5.shift(3)
        active=False;a=[]
        for i in range(len(d)):
            if i<79:
                a.append(False);continue
            if active:
                if c.iloc[i]>hi.iloc[i]: active=False
            elif c.iloc[i]<lo.iloc[i] and slope.iloc[i]: active=True
            a.append(active)
        out[f"BR{n}"]=pd.Series(a,index=d.index).shift(1,fill_value=False)
    pressure=np.log(d.close/d.open).rolling(10).sum().shift(1)<0
    for key in list(out): out[key+"_I10"]=out[key]&pressure
    return pd.DataFrame(out).astype(bool)

def swings(c, reversal):
    """Extremum time and later confirmation time both retained, labels are hindsight."""
    vals=c.to_numpy(float); direction=0; hi=lo=0; piv=[]
    for i in range(1,len(vals)):
        if direction==0:
            if vals[i]>=vals[hi]:hi=i
            if vals[i]<=vals[lo]:lo=i
            if vals[i]>=vals[lo]*(1+reversal):
                piv.append((lo,i,"L"));direction=1;hi=i
            elif vals[i]<=vals[hi]*(1-reversal):
                piv.append((hi,i,"H"));direction=-1;lo=i
        elif direction==1:
            if vals[i]>=vals[hi]:hi=i
            elif vals[i]<=vals[hi]*(1-reversal):
                piv.append((hi,i,"H"));direction=-1;lo=i
        else:
            if vals[i]<=vals[lo]:lo=i
            elif vals[i]>=vals[lo]*(1+reversal):
                piv.append((lo,i,"L"));direction=1;hi=i
    return piv

def metrics(g,p="rt"):
    met=old.metrics(g,p)
    if not len(g):return met
    x=g[p+"_pct"]; cash=g[p+"_cash"]
    met["episodes"]=int(g.ordinal.diff().ne(1).sum())
    met["delete5_pct"]=float(x.sort_values().iloc[:-5].mean()) if len(g)>5 else None
    met["delete5_cash"]=float(cash.sort_values().iloc[:-5].sum()) if len(g)>5 else None
    double=old.cashflow(g.open,g.close,g.date,p.upper(),.001)
    met["double_slip_pct"]=float((100*double/(1000*g.open)).mean())
    met["double_slip_cash"]=float(double.sum())
    matched=g[g.later_open.notna()]
    met["matched_n"]=len(matched)
    met["excluded_n"]=len(g)-len(matched)
    met["matched_open_pct"]=float(matched[p+"_pct"].mean()) if len(matched) else None
    met["matched_open_cash"]=float(matched[p+"_cash"].sum())
    delayed=old.cashflow(matched.later_open,matched.close,matched.date,p.upper())
    met["delayed_pct"]=float((100*delayed/(1000*matched.open)).mean()) if len(matched) else None
    met["delayed_cash"]=float(delayed.sum())
    month=g.groupby(g.date.dt.to_period("M"))[p+"_pct"].agg(["sum","count"]).to_numpy()
    rng=np.random.default_rng(601138)
    ix=rng.integers(0,len(month),(2000,len(month)))
    b=month[ix].sum(axis=1)
    ci=np.quantile(b[:,0]/b[:,1],[.025,.975])
    met["month_ci_low"],met["month_ci_high"]=map(float,ci)
    return met

def attr(g):
    night=np.log(g.open/g.preclose)
    intra=np.log(g.close/g.open)
    day=np.log(g.close/g.preclose)
    action=np.log(g.action_ratio)
    # Linked attribution across noncontiguous days is not a portfolio return.
    return dict(n=len(g),overnight_log_pct=float(100*night.sum()),
        intraday_log_pct=float(100*intra.sum()),total_log_pct=float(100*day.sum()),
        linked_overnight_pct=float(100*np.expm1(night.sum())),
        linked_intraday_pct=float(100*np.expm1(intra.sum())),
        linked_total_pct=float(100*np.expm1(day.sum())),
        raw_overnight_log_pct=float(100*(night+action).sum()),
        action_adjustment_log_pct=float(100*action.sum()),
        gross_rt_cash=float((1000*(g.open-g.close)).sum()),
        rt_cash=float(g.rt_cash.sum()),rt_mean_pct=float(g.rt_pct.mean()) if len(g) else None,
        pt_cash=float(g.pt_cash.sum()),pt_mean_pct=float(g.pt_pct.mean()) if len(g) else None,
        cost_cash=float((1000*(g.open-g.close)-g.rt_cash).sum()))

def checks(d,masks):
    old.tests()
    for cut in [300,800,1600]:
        alter=d.copy()
        alter.loc[cut:,["open","close","high","low","signal_close"]]*=np.linspace(.5,1.5,len(d)-cut)[:,None]
        pd.testing.assert_series_equal(causal(alter).iloc[cut],masks.iloc[cut])
        pd.testing.assert_frame_equal(causal(d.iloc[:cut+1]),masks.iloc[:cut+1])
    test=pd.Series([100.,120.,110.,100.,80.,90.,100.,120.,105.])
    piv=swings(test,.1)
    assert piv[:3]==[(0,1,"L"),(1,3,"H"),(4,5,"L")],piv
    assert all(i<=confirm for i,confirm,_ in piv)
    toy=pd.DataFrame(dict(signal_close=np.r_[np.full(90,100.),90.,89.,110.,110.]))
    toy["open"]=toy.signal_close
    toy["close"]=toy.signal_close
    toy["high"]=toy.signal_close+1
    toy["low"]=toy.signal_close-1
    tm=causal(toy)
    assert not tm.loc[90,["DD2","DD3"]].any() and tm.loc[91,["DD2","DD3"]].all()
    assert tm.loc[92,["DD2","DD3"]].all() and not tm.loc[93,["DD2","DD3"]].any()
    np.testing.assert_allclose(np.log(d.close/d.preclose),np.log(d.open/d.preclose)+np.log(d.close/d.open),atol=1e-12)
    assert d.stage.equals(old.stage(d.signal_close,"frozen"))
    for p in ["rt","pt"]:
        np.testing.assert_allclose(old.cashflow(d.open,d.close,d.date,p.upper()),d[p+"_cash"],atol=1e-6)
    assert (d.rt_cash+d.pt_cash<0).all()

def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true","No local market computation"
    ROOT.mkdir(parents=True,exist_ok=True)
    inputs={}
    for root,names,key in [(PRE,["results/daily_features_and_cashflows.csv","source/601138-full-5min-history.zip"],"sha256"),
                           (B2,["source/sse_index.csv"],"files")]:
        manifest=json.loads((root/"manifest.json").read_text())
        for name in names:
            path=root/name; digest=hashlib.sha256(path.read_bytes()).hexdigest()
            assert digest==manifest[key][str(path)],str(path)
            inputs[str(path)]=digest
    d=pd.read_csv(PRE/"results/daily_features_and_cashflows.csv",parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    assert len(d)==2007 and d.date.max()==pd.Timestamp("2026-09-11") and not d.date.duplicated().any()
    with zipfile.ZipFile(PRE/"source/601138-full-5min-history.zip") as z:
        minute=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith("601138_5min_all.csv"))))
    minute.date=pd.to_datetime(minute.date)
    minute["clock"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S").dt.strftime("%H:%M")
    minute=minute.sort_values(["date","clock"])
    first=minute.groupby("date").first();last=minute.groupby("date").last()
    valid=(d.date.map(first.open)-d.open).abs().le(.01)&(d.date.map(last.close)-d.close).abs().le(.01)
    d["later_open"]=d.date.map(minute[minute.clock.eq("09:40")].set_index("date").open).where(valid)
    masks=causal(d)
    assert masks.shape==(len(d),10)
    checks(d,masks)
    primary=d.date.ge("2024-01-02")
    windows={"full_available":pd.Series(True,index=d.index),"full_2020":d.date.ge("2020-01-01"),"primary":primary}
    windows.update({str(y):d.date.dt.year.eq(y) for y in range(2020,2027)})
    # Full reference partition, independent of detector and P&L.
    segs=[];parts=[];labels={};ids={};phases={}
    for scale in SCALES:
        piv=swings(d.signal_close,scale)
        lab=np.full(len(d),"EDGE",dtype=object);sid=np.full(len(d),-1);phase=np.full(len(d),"EDGE",dtype=object)
        for j,((start,sc,st),(end,ec,et)) in enumerate(zip(piv[:-1],piv[1:])):
            assert start<end and st!=et
            gg=d.iloc[start+1:end+1]
            logs=np.log(gg.close/gg.preclose)
            change=float(np.log(d.signal_close.iloc[end]/d.signal_close.iloc[start]))
            efficiency=abs(change)/float(logs.abs().sum()) if logs.abs().sum()>0 else 0.
            typ=("U" if change>0 else "D") if end-start>=5 and efficiency>=.25 else "R"
            idx=np.arange(start+1,end+1)
            lab[idx]=typ;sid[idx]=j
            thirds=np.minimum(2,(np.arange(len(idx))*3//len(idx)))
            phase[idx]=np.array(["early","middle","late"])[thirds]
            row=dict(scale=scale,segment=j,label=typ,start=d.date.iloc[start],end=d.date.iloc[end],
                start_confirm=d.date.iloc[sc],end_confirm=d.date.iloc[ec],start_i=start,end_i=end,
                efficiency=efficiency,**attr(gg))
            segs.append(row)
            np.testing.assert_allclose(logs.sum(),change,atol=1e-12)
            for p in ["early","middle","late"]:
                parts.append(dict(scale=scale,segment=j,label=typ,phase=p,**attr(d.iloc[idx[phase[idx]==p]])))
        labels[scale]=pd.Series(lab,index=d.index)
        ids[scale]=pd.Series(sid,index=d.index)
        phases[scale]=pd.Series(phase,index=d.index)
        assert sum((labels[scale]==x).sum() for x in ["U","D","R","EDGE"])==len(d)
        allix=np.flatnonzero(sid>=0)
        if len(allix):assert np.all(np.diff(allix)==1)
    segtab=save("segments.csv",segs)
    save("segment_thirds.csv",parts)
    reference=[];legsummary=[]
    for scale in SCALES:
        for win,wm in windows.items():
            for lab in ["U","D","R","EDGE"]:
                gg=d[wm&labels[scale].eq(lab)]
                reference.append(dict(scale=scale,window=win,label=lab,**attr(gg)))
                if lab=="EDGE":continue
                startdate=d.loc[wm,"date"].min();enddate=d.loc[wm,"date"].max()
                ss=segtab[(segtab.scale==scale)&(segtab.label==lab)&(segtab.start>=startdate)&(segtab.end<=enddate)]
                legsummary.append(dict(scale=scale,window=win,label=lab,completed_legs=len(ss),
                    profitable_rt_legs=int(ss.rt_cash.gt(0).sum()),profitable_pt_legs=int(ss.pt_cash.gt(0).sum()),
                    both_negative_legs=int((ss.rt_cash.lt(0)&ss.pt_cash.lt(0)).sum()),
                    positive_net_rt_cash=float(ss.loc[ss.rt_cash.gt(0),"rt_cash"].sum()),
                    negative_net_rt_cash=float(ss.loc[ss.rt_cash.le(0),"rt_cash"].sum())))
            np.testing.assert_allclose(sum(r["rt_cash"] for r in reference if r["scale"]==scale and r["window"]==win),d.loc[wm,"rt_cash"].sum(),atol=1e-6)
    ref=save("reference_attribution.csv",reference)
    legsum=save("completed_leg_counts.csv",legsummary)
    ixraw=pd.read_csv(B2/"source/sse_index.csv",parse_dates=["date"]).set_index("date").close
    ix=d.date.map(ixraw)
    down=d.signal_close.pct_change().lt(0)
    streak=down.groupby((~down).cumsum()).cumsum().shift(1).fillna(0)
    ptm=(d.stage.eq("U")&d.clv.lt(.4)&d.gap.le(-1))|(d.stage.eq("R")&streak.ge(3)&d.vr.lt(.8))| \
        (d.stage.eq("D")&d.clv.lt(.4)&d.gap.le(-1))| \
        (d.stage.eq("C")&(d.close<d.open).shift(1,fill_value=False)&ix.pct_change().shift(1).lt(0)&d.gap.lt(0))
    assert int((ptm&primary).sum())==72
    assert abs(d.loc[ptm&primary,"pt_cash"].sum()-45428.671)<.01
    strategies={k:(masks[k],"rt") for k in masks}
    strategies["PT_frozen"]=(ptm,"pt")
    strategies["RT_UR_volume"]=(d.stage.isin(["U","R"])&d.vr.ge(1.5),"rt")
    stats=[];mirror=[];excluded=[]
    for key,(m,p) in strategies.items():
        for win,wm in windows.items():
            gg=d[m&wm];met=metrics(gg,p)
            stats.append(dict(id=key,direction=p,window=win,**met))
            for losing in ["rt","pt"]:
                lm=old.metrics(gg,losing)
                if lm["n"] and lm["mean_pct"]<0:
                    other="pt" if losing=="rt" else "rt";om=old.metrics(gg,other)
                    mirror.append(dict(id=key,window=win,losing=losing,n=lm["n"],losing_mean_pct=lm["mean_pct"],
                        losing_cash=lm["cash"],opposite=other,opposite_mean_pct=om["mean_pct"],opposite_cash=om["cash"],
                        large=lm["mean_pct"]<=-.5))
        for _,r in d[m&primary&d.later_open.isna()].iterrows():
            excluded.append(dict(id=key,date=r.date,net_pct=r[p+"_pct"],cash=r[p+"_cash"]))
    stat=save("strategy_results.csv",stats)
    mir=save("mirror_registry.csv",mirror)
    save("execution_exclusions.csv",excluded)
    # Full-path attribution by hindsight label. Never use label to choose actual trades.
    diagnostics=[];opportunities=[];episode_rows=[]
    for key in masks:
        m=masks[key]
        episode_id=(m&~m.shift(1,fill_value=False)).cumsum()
        for eid,g in d[m].groupby(episode_id[m]):
            episode_rows.append(dict(id=key,episode=int(eid),entry=g.date.iloc[0],last_trade=g.date.iloc[-1],
                signal_asof=d.date.iloc[int(g.ordinal.iloc[0])-1],n=len(g),cash=float(g.rt_cash.sum()),
                mean_pct=float(g.rt_pct.mean())))
        for scale in SCALES:
            for win in ["full_2020","primary"]:
                wm=windows[win]
                for lab in ["U","D","R","EDGE"]:
                    gg=d[m&wm&labels[scale].eq(lab)]
                    diagnostics.append(dict(id=key,scale=scale,window=win,label=lab,phase="ALL",**attr(gg)))
                    for phase in ["early","middle","late"]:
                        gg=d[m&wm&labels[scale].eq(lab)&phases[scale].eq(phase)]
                        diagnostics.append(dict(id=key,scale=scale,window=win,label=lab,phase=phase,**attr(gg)))
                chosen=d.loc[m&wm,"rt_cash"].sum()
                check=sum(r["rt_cash"] for r in diagnostics if r["id"]==key and r["scale"]==scale and r["window"]==win and r["phase"]=="ALL")
                np.testing.assert_allclose(chosen,check,atol=1e-6)
            for _,s in segtab[(segtab.scale==scale)&segtab.label.eq("D")].iterrows():
                a,b=int(s.start_i)+1,int(s.end_i)
                positions=np.arange(a,b+1)
                hit=positions[m.iloc[positions].to_numpy()]
                first=int(hit[0]) if len(hit) else None
                traded=d.iloc[hit]
                opportunities.append(dict(id=key,scale=scale,segment=int(s.segment),start=s.start,end=s.end,
                    n=int(s.n),oracle_profitable=bool(s.rt_cash>0),oracle_cash=float(s.rt_cash),
                    detected=bool(len(hit)),first_trade=d.date.iloc[first] if first is not None else None,
                    days_missed=first-a if first is not None else int(s.n),traded_days=len(hit),
                    cash_before_first=float(d.iloc[a:first if first is not None else b+1].rt_cash.sum()),
                    all_remaining_cash=float(d.iloc[first:b+1].rt_cash.sum()) if first is not None else 0.,
                    actual_mask_cash=float(traded.rt_cash.sum()),actual_mask_mean=float(traded.rt_pct.mean()) if len(hit) else None))
    diag=save("detector_phase_attribution.csv",diagnostics)
    opp=save("down_leg_detection.csv",opportunities)
    save("detector_episodes.csv",episode_rows)
    cover=[]
    for key in masks:
      for scale in SCALES:
       for win in ["full_2020","primary"]:
        start=d.loc[windows[win],"date"].min();end=d.loc[windows[win],"date"].max()
        x=opp[(opp.id==key)&(opp.scale==scale)&(opp.start>=start)&(opp.end<=end)&opp.oracle_profitable]
        cashinside=float(x.actual_mask_cash.sum())
        cover.append(dict(id=key,scale=scale,window=win,profitable_down_legs=len(x),
            detected_legs=int(x.detected.sum()),oracle_cash=float(x.oracle_cash.sum()),captured_cash=cashinside,
            remaining_after_first_cash=float(x.all_remaining_cash.sum()),
            missed_before_first_cash=float(x.cash_before_first.sum()),
            median_days_missed=float(x.days_missed.median()) if len(x) else None,
            other_dates_cash=float(d.loc[masks[key]&windows[win],"rt_cash"].sum()-cashinside)))
    coverage=save("opportunity_coverage.csv",cover)
    # Pure past-outcome selection; labels are not inputs and no forward-return labels cross folds.
    newkeys=[k for k in masks if k not in ["D","D_I10"]]
    wf=[];wfmask=pd.Series(False,index=d.index);wfl=[]
    for year in [2024,2025,2026]:
        train=d.date.between("2020-01-01",str(year-1)+"-12-31");test=d.date.dt.year.eq(year)
        pool=[]
        for key in newkeys:
            z=old.metrics(d[masks[key]&train])
            if z["n"]>=30 and z["mean_pct"]>0 and (z["pf_cash"] or 0)>=1.3:pool.append((z["mean_pct"],key,z))
        pool.sort(key=lambda x:(-x[0],x[1]))
        if pool:
            score,key,z=pool[0];sel=masks[key]&test;wfmask|=sel
            wf.append(dict(year=year,selected=key,train_n=z["n"],train_mean_pct=score,train_cash=z["cash"],**metrics(d[sel])))
            for _,r in d[sel].iterrows():wfl.append(dict(year=year,id=key,date=r.date,cash=r.rt_cash,net_pct=r.rt_pct))
        else:wf.append(dict(year=year,selected="NONE",n=0,cash=0))
    save("walk_forward.csv",wf);save("walk_forward_trades.csv",wfl)
    gates=[]
    for key in masks:
        row=stat[(stat.id==key)&stat.window.eq("primary")].iloc[0]
        yrs=stat[(stat.id==key)&stat.window.isin(["2024","2025","2026"])]
        checks_gate=dict(n=row.n>=30,episodes=row.get("episodes",0)>=12,mean=row.mean_pct>=.3,
            pf=row.pf_cash>=1.5,years=bool((yrs.n.ge(5)&yrs.mean_pct.gt(0)&yrs.cash.gt(0)).all()),
            delete5=bool(row.delete5_pct>0 and row.delete5_cash>0),
            double=bool(row.double_slip_pct>0 and row.double_slip_cash>0),
            delayed=bool(row.delayed_pct>0 and row.delayed_cash>0 and row.matched_n>=.95*row.n),
            ci=bool(row.month_ci_low>0))
        gates.append(dict(id=key,**checks_gate,followup_pass=all(checks_gate.values())))
    save("followup_hurdles.csv",gates)
    daily=d[["date","ordinal","open","close","signal_close","stage","rt_cash","rt_pct","pt_cash","pt_pct","later_open"]].copy()
    for scale in SCALES:
        suffix=str(round(scale*100))
        daily["hindsight_"+suffix]=labels[scale];daily["segment_"+suffix]=ids[scale];daily["phase_"+suffix]=phases[scale]
    for key in masks:daily[key]=masks[key]
    daily["PT_frozen"]=ptm
    save("daily_audit.csv",daily)
    audit=dict(data_start=str(d.date.min().date()),data_end=str(d.date.max().date()),daily_n=len(d),
        primary_n=int(primary.sum()),primary_minute_valid=int((primary&d.later_open.notna()).sum()),
        signal_variants=list(masks),new_variants=newkeys,scales=SCALES,
        prefix_and_mutation_cutoffs=[300,800,1600],synthetic_signal_and_pivot_tests="passed",
        frozen_stage_and_PT_reproduction="passed",log_and_fullpath_reconciliation="passed",
        followup_pass=[g["id"] for g in gates if g["followup_pass"]],
        walk_forward=wf,walk_forward_primary=metrics(d[wfmask&primary]),input_hashes=inputs,
        limitations=["Already-inspected history; descriptive month intervals not multiplicity adjusted",
            "Hindsight reference scale and EDGE censoring; no unique true trend labels",
            "Current vendor price vintage and inherited cost scenario",
            "09:35 next-bar proxy is not executable fill certification",
            "Fixed1000-share incremental T cash is not total account performance"])
    dump("audit.json",audit)
    report=["# B04: swing reference and causal reverse-T detection",
        "Data through 2026-09-11; all processing on GitHub. Hindsight labels are descriptive only.",
        "## Primary fixed-rule comparison",old.md_table(stat[stat.window.eq("primary")]),
        "## Complete down legs (fully contained in window)",old.md_table(legsum[legsum.label.eq("D")&legsum.window.isin(["full_2020","primary"])]),
        "## Reference attribution, primary",old.md_table(ref[ref.window.eq("primary")]),
        "## Primary capture of profitable hindsight down legs",old.md_table(coverage[coverage.window.eq("primary")]),
        "## Annual retrospective selection",old.md_table(pd.DataFrame(wf)),
        "## Follow-up hurdle (not trading approval)",old.md_table(pd.DataFrame(gates)),
        "## Audit",json.dumps(audit,default=str,indent=2),
        "No stage replacement. Negative RT/PT regions independently costed and registered. Main production path unchanged."]

    # Reporting-only summaries of preregistered outputs; no new detector or threshold.
    mirror_robust=[]
    for key in masks:
        g=d[masks[key]&primary]
        if len(g) and g.rt_pct.mean()<0:
            mirror_robust.append(dict(id=key,losing_RT_mean=float(g.rt_pct.mean()),
                large_RT_loss=bool(g.rt_pct.mean()<=-.5),**metrics(g,"pt")))
    mirror_robust=save("primary_PT_mirror_robustness.csv",mirror_robust)
    primary_ann=stat[stat.window.isin(["2024","2025","2026"])][["id","direction","window","n","mean_pct","cash"]]
    # Fully-contained reference legs only, separate from clipped day attribution.
    fullids=segtab[(segtab.start>=pd.Timestamp("2024-01-02"))&segtab.label.eq("D")][["scale","segment"]]
    parttab=pd.DataFrame(parts).merge(fullids,on=["scale","segment"],how="inner")
    thirdrows=[]
    for (scale,phase),g in parttab.groupby(["scale","phase"]):
        thirdrows.append(dict(scale=scale,phase=phase,n=int(g.n.sum()),rt_cash=float(g.rt_cash.sum()),
            overnight_log_pct=float(g.overnight_log_pct.sum()),intraday_log_pct=float(g.intraday_log_pct.sum())))
    thirdsum=save("primary_down_thirds_summary.csv",thirdrows)
    focused_diag=diag[(diag.window=="primary")&(diag.phase=="ALL")]
    summary=dict(
        primary_rule_n=len(masks.columns),
        primary_negative_RT_rules=int(stat[stat.id.isin(masks.columns)&stat.window.eq("primary")].mean_pct.lt(0).sum()),
        primary_large_negative_RT_rules=int(stat[stat.id.isin(masks.columns)&stat.window.eq("primary")].mean_pct.le(-.5).sum()),
        full_available_leg_counts=legsum[legsum.window.eq("full_available")].to_dict("records"),
        primary_leg_counts=legsum[legsum.window.eq("primary")].to_dict("records"),
        primary_annual=primary_ann.to_dict("records"),
        primary_mirrors=mirror_robust.to_dict("records"),
        primary_down_thirds=thirdsum.to_dict("records"),
        primary_phase_attribution=focused_diag.to_dict("records"),
        primary_coverage=coverage[coverage.window.eq("primary")].to_dict("records"),
        mirror_registry_rows=len(mir),mirror_large_rows=int(mir.large.sum()),
        causal_check_note="same/future mutation and prefix invariance passed; no model change during report expansion")
    dump("summary.json",summary)
    report.extend(["## Full available completed-leg counts",old.md_table(legsum[legsum.window.eq("full_available")]),
        "## Annual fixed rules",old.md_table(primary_ann),
        "## Primary independently costed PT mirrors (candidate registration only)",old.md_table(mirror_robust),
        "## Primary detector attribution by hindsight label at 8% scale",
        old.md_table(focused_diag[focused_diag.scale.eq(.08)][["id","label","n","rt_cash","rt_mean_pct","overnight_log_pct","intraday_log_pct"]]),
        "## Primary fully-contained down-leg thirds",old.md_table(thirdsum)])

    (ROOT/"REPORT.md").write_text("\n\n".join(report))
    paths=[p for p in ROOT.iterdir() if p.is_file() and p.name!="manifest.json"]
    dump("manifest.json",dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],
        contract_sha256=hashlib.sha256(Path("DOCS/FOXCONN_T0_B04.md").read_bytes()).hexdigest(),
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}))
    print(json.dumps({"daily_n":len(d),"variants":len(masks.columns),"followup_pass":audit["followup_pass"],
        "primary":stat[stat.window.eq("primary")][["id","n","mean_pct","cash"]].to_dict("records")},indent=2))
if __name__=="__main__":
    run()
