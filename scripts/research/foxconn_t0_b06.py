#!/usr/bin/env python3
"""B06 six frozen rules: execution, historical failures and external hypotheses."""
import os,json,hashlib,zipfile,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old
import foxconn_t0_b04 as b4
import foxconn_t0_b05 as b5
ROOT=Path("research/foxconn_t0_20260915_b06")
P1=Path("research/foxconn_t0_20260913")
P2=Path("research/foxconn_t0_20260913_b02")
P4=Path("research/foxconn_t0_20260913_b04")
P5=Path("research/foxconn_t0_20260915_b05")
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
def masks(d,ix):
    clv=((d.close-d.low)/(d.high-d.low)).where(d.high!=d.low,.5).shift()
    vr=(d.volume/d.volume.rolling(20).mean()).shift()
    intra=(100*(d.close/d.open-1)).shift()
    market=100*ix.pct_change().shift()
    gap=100*(d.open/d.preclose-1)
    f=pd.DataFrame(dict(clv=clv,vr=vr,previous_intraday=intra,previous_SSE=market,gap=gap))
    r=pd.DataFrame({
        "BASE_HV":clv.ge(.8)&vr.ge(1.5),
        "EXT_R1":gap.gt(.3)&intra.gt(.8)&market.gt(0),
        "EXT_R2":gap.gt(0)&intra.gt(.8)&market.gt(0),
        "EXT_R3":gap.gt(.5)&intra.gt(1),
        "EXT_R4":gap.gt(0)&intra.gt(1),
        "EXT_R5":gap.gt(.2)&intra.gt(1)&market.gt(0)})
    return r,f
def economy(g):
    m=b4.metrics(g)
    if not len(g):return m
    gross=100*(1-g.close/g.open)
    month=g.groupby(g.date.dt.to_period("M")).rt_cash.sum()
    m.update(down_pct=float(100*g.down.mean()),gross_mean_pct=float(gross.mean()),
        cost_drag_pct=float((gross-g.rt_pct).mean()),gross_cash=float((1000*(g.open-g.close)).sum()),
        cost_cash=float((1000*(g.open-g.close)-g.rt_cash).sum()),
        largest_month=str(month.idxmax()),largest_month_cash=float(month.max()),
        delete_largest_month_cash=float(g.rt_cash.sum()-month.max()))
    return m
def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true"
    ROOT.mkdir(parents=True,exist_ok=True)
    parents={}
    for root,paths,key in [(P1,["results/daily_features_and_cashflows.csv","source/601138-full-5min-history.zip"],"sha256"),
        (P2,["source/sse_index.csv"],"files"),(P4,["daily_audit.csv"],"files"),(P5,["candidate_trades.csv"],"files")]:
        man=json.loads((root/"manifest.json").read_text())
        for file in paths:
            p=root/file;h=hashlib.sha256(p.read_bytes()).hexdigest()
            assert h==man[key][str(p)]
            parents[str(p)]=h
    d=pd.read_csv(P1/"results/daily_features_and_cashflows.csv",parse_dates=["date"])
    a=pd.read_csv(P4/"daily_audit.csv",parse_dates=["date"])
    pd.testing.assert_series_equal(d.date,a.date)
    assert len(d)==2007 and d.date.max()==pd.Timestamp("2026-09-11")
    d["later_open"]=a.later_open;d["down"]=d.close.lt(d.open).astype(int)
    ix=d.date.map(pd.read_csv(P2/"source/sse_index.csv",parse_dates=["date"]).set_index("date").close)
    r,f=masks(d,ix);assert r.shape==(len(d),6)
    original=pd.read_csv(P5/"candidate_trades.csv",parse_dates=["date"])
    np.testing.assert_array_equal(d.loc[r.BASE_HV,"date"].to_numpy(),original.date.to_numpy())
    old.tests()
    np.testing.assert_allclose(old.cashflow(d.open,d.close,d.date),d.rt_cash,atol=1e-6)
    np.testing.assert_array_equal(d.stage,old.stage(d.signal_close,"frozen"))
    for cut in [900,1600]:
        alt=d.copy();alt["volume"]=alt.volume.astype(float)
        alt.loc[cut:,["high","low","close","signal_close","volume"]]*=1.27
        altered_ix=ix.copy();altered_ix.iloc[cut:]*=1.4
        rr,ff=masks(alt,altered_ix)
        pd.testing.assert_series_equal(r.iloc[cut],rr.iloc[cut])
        alt.loc[cut:,"open"]*=1.1
        rr,_=masks(alt,altered_ix)
        assert r.BASE_HV.iloc[cut]==rr.BASE_HV.iloc[cut]
        pd.testing.assert_frame_equal(masks(d.iloc[:cut+1],ix.iloc[:cut+1])[0],r.iloc[:cut+1])
    # Independent literal predicate checks, including strict external inequalities.
    for i in d.index:
        x=f.iloc[i]
        expected=[x.clv>=.8 and x.vr>=1.5,x.gap>.3 and x.previous_intraday>.8 and x.previous_SSE>0,
            x.gap>0 and x.previous_intraday>.8 and x.previous_SSE>0,x.gap>.5 and x.previous_intraday>1,
            x.gap>0 and x.previous_intraday>1,x.gap>.2 and x.previous_intraday>1 and x.previous_SSE>0]
        assert r.iloc[i].tolist()==expected
    with zipfile.ZipFile(P1/"source/601138-full-5min-history.zip") as z:
        minute=pd.read_csv(z.open(next(n for n in z.namelist() if n.endswith("601138_5min_all.csv"))))
    minute.date=pd.to_datetime(minute.date)
    minute["clock"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S").dt.strftime("%H:%M")
    minute=minute.sort_values(["date","clock"])
    first,last=minute.groupby("date").first(),minute.groupby("date").last()
    valid=(d.date.map(first.open)-d.open).abs().le(.01)&(d.date.map(last.close)-d.close).abs().le(.01)
    for name,label in [("0935","09:40"),("0945","09:50"),("1000","10:05")]:
        d["entry_"+name]=d.date.map(minute[minute.clock.eq(label)].set_index("date").open).where(valid)
    np.testing.assert_allclose(d.entry_0935,d.later_open,equal_nan=True,atol=1e-12)
    common=d[["entry_0935","entry_0945","entry_1000"]].notna().all(axis=1)
    primary=d.date.ge("2024-01-02")
    assert (r.BASE_HV&primary).sum()==30
    assert abs(d.loc[r.BASE_HV&primary,"rt_cash"].sum()-13849.687)<.01
    assert (a.PT_frozen&primary).sum()==72
    assert abs(d.loc[a.PT_frozen&primary,"pt_cash"].sum()-45428.671)<.01
    windows={"old_2020_2023":d.date.between("2020-01-01","2023-12-31"),"primary":primary,
        "full_2020":d.date.ge("2020-01-01")}
    windows.update({str(y):d.date.dt.year.eq(y) for y in [2024,2025,2026]})
    stats=[];execution=[];missing=[];mirrors=[];leaveyear=[];ledger=[]
    for key in r:
        for win,wm in windows.items():
            g=d[r[key]&wm]
            stats.append(dict(id=key,window=win,timing="previous_close" if key=="BASE_HV" else "after_auction",
                **{**b5.probstats(g,d[wm]),**economy(g)}))
            gg=d[r[key]&wm&common].copy()
            for time,col in [("open","open"),("09:35","entry_0935"),("09:45","entry_0945"),("10:00","entry_1000")]:
                for slip in [.0005,.001]:
                    temp=gg.copy()
                    temp["rt_cash"]=old.cashflow(gg[col],gg.close,gg.date,slip=slip)
                    temp["rt_pct"]=100*temp.rt_cash/(1000*gg.open)
                    execution.append(dict(id=key,window=win,time=time,slip=slip,
                        slip_bps=10000*slip,full_signal_n=len(g),excluded=len(g)-len(gg),**old.metrics(temp)))
            for p in ["rt","pt"]:
                m=old.metrics(g,p)
                if m["n"] and m["mean_pct"]<0:
                    opp="pt" if p=="rt" else "rt"
                    mirrors.append(dict(id=key,window=win,losing=p,losing_mean=m["mean_pct"],
                        large=m["mean_pct"]<=-.5,opposite=opp,**old.metrics(g,opp)))
            if win in ["full_2020","primary"]:
                for year in sorted(g.date.dt.year.unique()):
                    z=g[g.date.dt.year.ne(year)]
                    leaveyear.append(dict(id=key,window=win,excluded_year=int(year),**old.metrics(z)))
        for i,z in d[r[key]&~common].iterrows():
            missing.append(dict(id=key,date=z.date,opening_cash=z.rt_cash,
                missing0935=pd.isna(z.entry_0935),missing0945=pd.isna(z.entry_0945),missing1000=pd.isna(z.entry_1000)))
        for i,z in d[r[key]].iterrows():
            ledger.append(dict(id=key,date=z.date,stage=z.stage,open=z.open,close=z.close,
                rt_cash=z.rt_cash,rt_pct=z.rt_pct,pt_cash=z.pt_cash,pt_pct=z.pt_pct,**f.loc[i].to_dict()))
    stat=save("rule_results.csv",stats);ex=save("matched_execution.csv",execution)
    save("execution_exclusions.csv",missing)
    ly=save("leave_one_year_out.csv",leaveyear);lt=save("all_trades.csv",ledger)
    fail=save("BASE_losing_trades.csv",lt[lt.id.eq("BASE_HV")&lt.rt_cash.lt(0)])
    overlap=[]
    for win in ["primary","full_2020"]:
        wm=windows[win]
        for left,right in itertools.combinations(r.columns,2):
            inter=r[left]&r[right]&wm;lonly=r[left]&~r[right]&wm;ronly=r[right]&~r[left]&wm
            np.testing.assert_allclose(d.loc[inter|lonly,"rt_cash"].sum(),d.loc[r[left]&wm,"rt_cash"].sum(),atol=1e-6)
            for part,m in [("intersection",inter),("left_only",lonly),("right_only",ronly)]:
                overlap.append(dict(left=left,right=right,part=part,window=win,**old.metrics(d[m])))
                for p in ["rt","pt"]:
                    metric=old.metrics(d[m],p)
                    if metric["n"] and metric["mean_pct"]<0:
                        opp="pt" if p=="rt" else "rt"
                        mirrors.append(dict(id=left+"__"+right+"__"+part,window=win,losing=p,losing_mean=metric["mean_pct"],large=metric["mean_pct"]<=-.5,opposite=opp,scope="overlap_diagnostic",**old.metrics(d[m],opp)))
    ov=save("overlap_partitions.csv",overlap)
    relax=[]
    for broad,narrow in [("EXT_R2","EXT_R1"),("EXT_R4","EXT_R3"),("EXT_R2","EXT_R5")]:
        assert not (r[narrow]&~r[broad]).any()
        for win,wm in windows.items():
            g=d[r[broad]&~r[narrow]&wm]
            relax.append(dict(broad=broad,narrow=narrow,window=win,**economy(g)))
            for p in ["rt","pt"]:
                metric=old.metrics(g,p)
                if metric["n"] and metric["mean_pct"]<0:
                    opp="pt" if p=="rt" else "rt"
                    mirrors.append(dict(id=broad+"__outside__"+narrow,window=win,losing=p,losing_mean=metric["mean_pct"],large=metric["mean_pct"]<=-.5,opposite=opp,scope="relaxation_diagnostic",**old.metrics(g,opp)))
    ab=save("threshold_relaxation_diagnostics.csv",relax)
    mir=save("mirror_registry.csv",mirrors)
    failure_groups=[]
    for win,wm in windows.items():
        for stage in ["ALL","U","R","D","C"]:
            m=r.BASE_HV&wm
            if stage!="ALL":m&=d.stage.eq(stage)
            failure_groups.append(dict(window=win,stage=stage,**economy(d[m])))
    fg=save("BASE_history_and_stage.csv",failure_groups)
    claimed=pd.DataFrame([
        dict(id="EXT_R1",claimed_n=22,claimed_netwin=63.6,claimed_mean=1.,claimed_cash=15436),
        dict(id="EXT_R2",claimed_n=28,claimed_netwin=57.1,claimed_mean=.73,claimed_cash=14071),
        dict(id="EXT_R3",claimed_n=26,claimed_netwin=57.7,claimed_mean=.88,claimed_cash=14611),
        dict(id="EXT_R4",claimed_n=37,claimed_netwin=51.4,claimed_mean=.56,claimed_cash=12521),
        dict(id="EXT_R5",claimed_n=21,claimed_netwin=61.9,claimed_mean=.91,claimed_cash=13579)])
    save("external_claims_unverified.csv",claimed)
    comparison=claimed.merge(stat[stat.window.eq("primary")][["id","n","win_pct","mean_pct","cash"]],on="id")
    save("external_claims_vs_common_window.csv",comparison)
    audit=dict(data_end="2026-09-11",daily_n=len(d),primary_n=int(primary.sum()),rules=list(r),
        primary_common_execution_n=int((primary&common).sum()),input_hashes=parents,
        literal_predicates="passed all daily rows",signal_mutation_and_prefix="passed900/1600",
        BASE_reproduction="N30/cash13849.687 and full candidate dates matched",
        PT_reproduction="N72/cash45428.671",minute0935_reproduction=True,overlap_cash_reconciliation=True,
        mirror_rows=len(mir),large_mirror_rows=int(mir.large.sum()),
        source_limit="External period/fees/fills unknown; common-window comparison is not exact reproduction.",
        limits=["All history already inspected","No threshold tuning","No new independent forward sample",
                "After-auction gap cannot certify auction fill","Bar proxies not fills","Fixed q incremental cash not account return"])
    dump("audit.json",audit)
    summary=dict(audit=audit,primary=stat[stat.window.eq("primary")].to_dict("records"),
        annual=stat[stat.window.isin(["2024","2025","2026"])].to_dict("records"),
        old=stat[stat.window.eq("old_2020_2023")].to_dict("records"),
        primary_execution=ex[ex.window.eq("primary")].to_dict("records"),
        primary_BASE_overlap=ov[ov.window.eq("primary")&ov.left.eq("BASE_HV")].to_dict("records"),
        primary_relaxation=ab[ab.window.eq("primary")].to_dict("records"),comparison=comparison.to_dict("records"))
    dump("summary.json",summary)
    cols=["id","window","n","down_pct","win_pct","mean_pct","cash","pf_cash","gross_mean_pct","cost_drag_pct",
        "delete5_pct","delete5_cash","delete_largest_month_cash","month_ci_low","month_ci_high"]
    report=["# B06 fixed candidate and external AI hypotheses",
        "Data through2026-09-11. External claims unverified; no window search to match reported counts.",
        "## Primary",old.md_table(stat[stat.window.eq("primary")][cols]),
        "## Historical and annual",old.md_table(stat[~stat.window.eq("primary")][cols]),
        "## Primary matched execution, all times same dates",old.md_table(ex[ex.window.eq("primary")].drop(columns="slip")),
        "## External claims versus our common primary window",old.md_table(comparison),
        "## Primary overlap with BASE",old.md_table(ov[ov.window.eq("primary")&ov.left.eq("BASE_HV")]),
        "## Primary relaxation marginal dates, not new strategies",old.md_table(ab[ab.window.eq("primary")]),
        "## BASE primary losses",old.md_table(fail[fail.date.ge("2024-01-02")]),
        "## BASE historical decomposition",old.md_table(fg[fg.stage.eq("ALL")]),
        "## Primary leave-one-year-out",old.md_table(ly[ly.window.eq("primary")]),
        "## Primary mirrored regions",old.md_table(mir[mir.window.eq("primary")]),
        "## Audit",json.dumps(audit,indent=2)]
    (ROOT/"REPORT.md").write_text("\n\n".join(report))
    dump("manifest.json",dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],
        contract_sha256=hashlib.sha256(Path("DOCS/FOXCONN_T0_B06.md").read_bytes()).hexdigest(),
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!="manifest.json"}))
    print(json.dumps(audit,indent=2))
if __name__=="__main__":run()
