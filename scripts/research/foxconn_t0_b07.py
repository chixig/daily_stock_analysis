#!/usr/bin/env python3
"""B07 fixed environment splits over expanded history; GitHub execution only."""
import os,json,hashlib
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old
import foxconn_t0_b04 as b4
import foxconn_t0_b06 as b6
ROOT=Path("research/foxconn_t0_20260915_b07")
def save(name,rows):
    z=rows if isinstance(rows,pd.DataFrame) else pd.DataFrame(rows)
    z.to_csv(ROOT/name,index=False);return z
def features(d,ix):
    m=ix.pct_change(20)
    relative=d.signal_close.pct_change(20)-m
    vol=np.log(d.signal_close).diff().rolling(20).std()
    act=(d.close*d.volume).rolling(20).mean()
    return pd.DataFrame(dict(MKT20=m,REL20=relative,VOL=vol/vol.rolling(252).median()-1,
        ACT=act/act.rolling(252).median()-1)).shift()
def masks(d,ix):
    base,_=b6.masks(d,ix);f=features(d,ix);valid=f.notna().all(axis=1)
    r=pd.DataFrame({"BASE":base.BASE_HV&valid})
    for k in f:
        r[k+"_high"]=r.BASE&f[k].gt(0)
        r[k+"_low"]=r.BASE&f[k].le(0)
    return r,f,valid,base
def select(d,r,year):
    train=d.date.between("2020-01-01",str(year-1)+"-12-31")
    eligible=[];audit=[]
    for k in r:
        g=d[r[k]&train];m=b4.metrics(g)
        ys=g.groupby(g.date.dt.year).rt_pct.mean()
        passed=len(g)>=20 and m["mean_pct"]>0 and m["delete5_pct"]>0 and m["delete5_cash"]>0 and (ys>0).sum()>=2
        audit.append(dict(year=year,id=k,training_last=str(g.date.max()),eligible=bool(passed),**m))
        if passed:eligible.append((m["delete5_pct"],len(g),k))
    chosen=sorted(eligible,key=lambda z:(-z[0],-z[1],z[2]))[0][2] if eligible else "NONE"
    return chosen,audit
def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true"
    ROOT.mkdir(parents=True,exist_ok=True)
    parent=Path("research/foxconn_t0_20260915_b06")
    source=json.loads((parent/"audit.json").read_text())["input_hashes"]
    for name,h in source.items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==h
    d=pd.read_csv(b6.P1/"results/daily_features_and_cashflows.csv",parse_dates=["date"])
    a=pd.read_csv(b6.P4/"daily_audit.csv",parse_dates=["date"])
    pd.testing.assert_series_equal(d.date,a.date)
    d["later_open"]=a.later_open;d["down"]=d.close.lt(d.open).astype(int)
    ix=d.date.map(pd.read_csv(b6.P2/"source/sse_index.csv",parse_dates=["date"]).set_index("date").close)
    r,f,valid,base=masks(d,ix)
    assert d.date.max()==pd.Timestamp("2026-09-11")
    old.tests()
    np.testing.assert_allclose(old.cashflow(d.open,d.close,d.date),d.rt_cash,atol=1e-6)
    np.testing.assert_array_equal(old.stage(d.signal_close,"frozen"),d.stage)
    recent=d.date.ge("2024-01-02")
    assert (base.BASE_HV&recent).sum()==30
    assert abs(d.loc[base.BASE_HV&recent,"rt_cash"].sum()-13849.687)<.01
    assert (a.PT_frozen&recent).sum()==72
    assert abs(d.loc[a.PT_frozen&recent,"pt_cash"].sum()-45428.671)<.01
    for cut in [900,1600]:
        alt=d.copy();alt["volume"]=alt.volume.astype(float)
        alt.loc[cut:,["open","close","high","low","volume","signal_close"]]*=1.3
        ai=ix.copy();ai.iloc[cut:]*=1.2
        rr,ff,_,_=masks(alt,ai)
        pd.testing.assert_series_equal(r.iloc[cut],rr.iloc[cut])
        pd.testing.assert_series_equal(f.iloc[cut],ff.iloc[cut])
        pd.testing.assert_frame_equal(masks(d.iloc[:cut+1],ix.iloc[:cut+1])[0],r.iloc[:cut+1])
    for k in f:
        assert not (r[k+"_high"]&r[k+"_low"]).any()
        assert ((r[k+"_high"]|r[k+"_low"])==r.BASE).all()
        np.testing.assert_allclose(d.loc[r[k+"_high"],"rt_cash"].sum()+d.loc[r[k+"_low"],"rt_cash"].sum(),d.loc[r.BASE,"rt_cash"].sum())
    windows={"main2020":d.date.ge("2020-01-01"),"old2020_2023":d.date.between("2020-01-01","2023-12-31"),
        "recent2024":recent,"all_available":pd.Series(True,index=d.index)}
    windows.update({str(y):d.date.dt.year.eq(y) for y in range(2018,2027)})
    coverage=[];results=[];mirrors=[]
    for win,wm in windows.items():
        coverage.append(dict(window=win,all_days=int(wm.sum()),feature_valid_days=int((wm&valid).sum()),
            base_unrestricted=int((wm&base.BASE_HV).sum()),base_valid=int((wm&r.BASE).sum()),
            baseline_down_pct=float(100*d.loc[wm&valid,"down"].mean())))
    controls={k:base[k] for k in base}
    controls["PT_frozen"]=a.PT_frozen
    universe={**{k:r[k] for k in r},**controls}
    for k,mask in universe.items():
        for win,wm in windows.items():
            g=d[mask&wm]
            if k=="PT_frozen":
                m=old.metrics(g,"pt")
            else:m=b6.economy(g)
            results.append(dict(id=k,window=win,**m))
            for p in ["rt","pt"]:
                m=old.metrics(g,p)
                if m["n"] and m["mean_pct"]<0:
                    opp="pt" if p=="rt" else "rt"
                    mirrors.append(dict(id=k,window=win,losing=p,losing_mean=m["mean_pct"],
                        large=m["mean_pct"]<=-.5,opposite=opp,**old.metrics(g,opp)))
    stats=save("results.csv",results);cov=save("coverage.csv",coverage);mir=save("mirror_registry.csv",mirrors)
    choices=[];training=[];chosenmask=pd.Series(False,index=d.index)
    for year in range(2022,2027):
        chosen,logs=select(d,r,year);training.extend(logs)
        before=d.date.dt.year.lt(year)
        chosen2,_=select(d[before],r[before],year)
        assert chosen==chosen2
        test=d.date.dt.year.eq(year)
        selected=(r[chosen]&test) if chosen!="NONE" else pd.Series(False,index=d.index)
        chosenmask|=selected
        choices.append(dict(year=year,chosen=chosen,**old.metrics(d[selected])))
    choices.append(dict(year="combined",chosen="annual_fixed",**b6.economy(d[chosenmask])))
    wf=save("walkforward_results.csv",choices);save("walkforward_training.csv",training)
    save("daily_features_and_signals.csv",pd.concat([d,f.add_prefix("env_"),r.add_prefix("signal_"),valid.rename("feature_valid")],axis=1))
    save("walkforward_trades.csv",d[chosenmask])
    audit=dict(data_start=str(d.date.min().date()),data_end=str(d.date.max().date()),daily_n=len(d),
        first_complete_features=str(d.loc[valid,"date"].min().date()),rules=list(r),input_hashes=source,
        primary_BASE_reproduced=True,PT_reproduced=True,feature_mutation_prefix_passed=True,complement_cash_passed=True,
        annual_cutoff_passed=True,mirror_rows=len(mir),large_mirror_rows=int(mir.large.sum()),
        limitation="Historical exploratory splits and retrospective walk-forward, no new unseen forward sample. SSE is not industry. ACT close*volume proxy is not float turnover.")
    (ROOT/"audit.json").write_text(json.dumps(audit,indent=2))
    cols=["id","window","n","down_pct","win_pct","mean_pct","cash","delete5_pct","delete5_cash","double_slip_pct","matched_n","delayed_pct","month_ci_low","month_ci_high"]
    report=["# B07 expanded-history environment results",
        "## Coverage and warmup",old.md_table(cov),
        "## Main2020 and old/recent mandatory comparison",old.md_table(stats[stats.window.isin(["main2020","old2020_2023","recent2024"])][cols]),
        "## Annual fixed environment conditions",old.md_table(stats[stats.id.isin(r.columns)&stats.window.str.fullmatch(r"\d{4}")][cols]),
        "## Walk forward",old.md_table(wf),
        "## Main mirror registry",old.md_table(mir[mir.window.eq("main2020")]),
        "## Audit",json.dumps(audit,indent=2)]
    (ROOT/"REPORT.md").write_text("\n\n".join(report))
    manifest=dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],
        spec_sha256=hashlib.sha256(Path("DOCS/FOXCONN_T0_B07.md").read_bytes()).hexdigest(),
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.name!="manifest.json"})
    (ROOT/"manifest.json").write_text(json.dumps(manifest,indent=2))
    print(json.dumps(audit))
if __name__=="__main__":run()
