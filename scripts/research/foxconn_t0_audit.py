#!/usr/bin/env python3
"""Bounded, reproducible open-to-close research. Runs only on GitHub Actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile
import numpy as np
import pandas as pd

ROOT = Path("research/foxconn_t0_20260913")
SOURCE = ROOT / "source"
OUT = ROOT / "results"
RULES = {
    "main_stage": "frozen_positive_v1_slope5_recentD20",
    "comparison_stage": "reverse_v3_slope1_repair_aboveMA20",
    "end": "2026-09-11",
    "primary_start": "2024-01-02",
    "old_end": "2026-06-25",
    "q": 1000,
    "commission": 0.0001354,
    "minimum_commission": 5,
    "transfer_scenario": 0.00001,
    "slippage_each_side": 0.0005,
    "mirror_threshold_pct": -0.5,
    "mirror_note": "Administrative inclusive flag, not a validated threshold; also flag all negative regions.",
    "trial_budget": "4 families, 18 single regions per stage, at most 4 predeclared pairs per stage; no adaptive search",
    "bootstrap": "calendar-month cluster resampling, seed=601138, 2000 draws; descriptive, not selection-adjusted",
    "frozen_at": "before first run; all prior historical windows already explored"
}

def stage(c, mode):
    ma20, ma60 = c.rolling(20).mean(), c.rolling(60).mean()
    slope = 5 if mode == "frozen" else 1
    r20, r5 = c/c.shift(20)-1, c/c.shift(5)-1
    u = (c > ma20) & (ma20 > ma60) & (ma20 > ma20.shift(slope)) & (r20 > 0)
    d = (c < ma20) & (ma20 < ma60) & (ma20 < ma20.shift(slope)) & (r20 < 0)
    if mode == "frozen":
        recent = d.shift(1).rolling(20, min_periods=20).max().eq(1)
        repair = recent & ((c > ma20) | (r5 > 0))
    else:
        repair = (c > ma20) & (ma20 < ma60) & (ma20 > ma20.shift(1)) & (r20 > 0)
    s = pd.Series(np.select([u,d,repair],["U","D","C"],default="R"), index=c.index)
    s[c.index < 80] = "UNKNOWN"
    return s.shift(1).fillna("UNKNOWN")

def cashflow(o, c, dates, direction="RT", slip=0.0005):
    sell = (o if direction=="RT" else c) * (1-slip) * 1000
    buy = (c if direction=="RT" else o) * (1+slip) * 1000
    tax = np.where(pd.to_datetime(dates) < pd.Timestamp("2023-08-28"), 0.001, 0.0005)
    fees = np.maximum(sell*0.0001354,5) + np.maximum(buy*0.0001354,5) + (sell+buy)*0.00001 + sell*tax
    return sell-buy-fees

def metrics(g, prefix="rt"):
    x = g[prefix+"_cash"].to_numpy(float)
    r = g[prefix+"_pct"].to_numpy(float)
    if not len(x):
        return dict(n=0,mean_pct=None,median_pct=None,win_pct=None,cash=0,pf_pct=None,pf_cash=None,worst_pct=None,mdd_cash=0,clusters=0)
    cum = np.r_[0,np.cumsum(x)]
    pf = lambda a: float(a[a>0].sum()/-a[a<0].sum()) if (a<0).any() else None
    clusters = int((g["ordinal"].diff().fillna(999)>5).sum())
    return dict(n=len(x),mean_pct=float(r.mean()),median_pct=float(np.median(r)),win_pct=float(100*(x>0).mean()),cash=float(x.sum()),pf_pct=pf(r),pf_cash=pf(x),worst_pct=float(r.min()),mdd_cash=float((cum-np.maximum.accumulate(cum)).min()),clusters=clusters)

def stress(g):
    if g.empty:
        return {}
    r=g.rt_pct.to_numpy()
    groups=[v.rt_pct.to_numpy() for _,v in g.groupby(g.date.dt.to_period("M"))]
    rng=np.random.default_rng(601138)
    draws=[]
    for _ in range(2000):
        pieces=[groups[i] for i in rng.integers(0,len(groups),len(groups))]
        draws.append(np.concatenate(pieces).mean())
    ids=(g.ordinal.diff().fillna(999)>5).cumsum()
    leave=[g.loc[ids!=k,"rt_pct"].mean() for k in ids.unique() if (ids!=k).any()]
    return dict(month_block_ci95=np.quantile(draws,[.025,.975]).tolist(),
                delete_top1_pct=float(np.sort(r)[:-1].mean()) if len(r)>1 else None,
                delete_top3_pct=float(np.sort(r)[:-3].mean()) if len(r)>3 else None,
                delete_top5_pct=float(np.sort(r)[:-5].mean()) if len(r)>5 else None,
                leave_cluster_min_pct=float(min(leave)) if leave else None)

def md_table(df):
    return df.to_markdown(index=False, floatfmt=".3f")

def load_inputs():
    SOURCE.mkdir(parents=True,exist_ok=True)
    archive=SOURCE/"601138-full-5min-history.zip"
    if not archive.exists():
        with archive.open("wb") as f:
            subprocess.run(["gh","api",f"repos/{os.environ['GITHUB_REPOSITORY']}/actions/artifacts/10273429024/zip"],stdout=f,check=True)
    assert hashlib.sha256(archive.read_bytes()).hexdigest()=="6decd5fbe5916d974d7897f9259de6dbe0c319722bd3972a85d780cf25c1c5ff", "Artifact hash differs"
    with zipfile.ZipFile(archive) as z:
        names=z.namelist()
        daily=pd.read_csv(z.open(next(n for n in names if n.endswith("601138_daily_raw.csv"))))
        minute=pd.read_csv(z.open(next(n for n in names if n.endswith("601138_5min_all.csv"))))
    return daily,minute

def prepare(raw):
    d=raw.copy()
    d["date"]=pd.to_datetime(d.date)
    assert not d.date.duplicated().any(), "Duplicate daily dates"
    d=d.sort_values("date").reset_index(drop=True)
    numeric=["open","high","low","close","preclose","volume","pctChg"]
    d[numeric]=d[numeric].apply(pd.to_numeric,errors="raise")
    d=d[d.date<=RULES["end"]].copy()
    valid=(d[numeric].notna().all(axis=1)&(d[["open","high","low","close","preclose"]]>0).all(axis=1)&
           (d.high>=d[["open","close","low"]].max(axis=1))&
           (d.low<=d[["open","close"]].min(axis=1)))
    assert valid.all(), "Invalid daily OHLC"
    assert d.tradestatus.astype(str).eq("1").all(), "Suspended rows need explicit review"
    # Vendor preclose return chain: corporate action adjustment convention audited below.
    d["signal_close"]=(d.close/d.preclose).cumprod()*100
    d["chain_return_error_pct"]=(100*(d.close/d.preclose-1)-d.pctChg).abs()
    assert d.chain_return_error_pct.max()<0.002, "Preclose/pctChg mismatch"
    d["action_ratio"]=d.preclose/d.close.shift(1)
    d["stage"]=stage(d.signal_close,"frozen")
    d["stage_v3"]=stage(d.signal_close,"v3")
    d["ordinal"]=np.arange(len(d))
    c=d.signal_close
    d["vr"]=(d.volume/d.volume.rolling(20).mean()).shift(1)
    d["r3"]=(c/c.shift(3)-1).shift(1)*100
    d["r5"]=(c/c.shift(5)-1).shift(1)*100
    d["clv"]=((d.close-d.low)/(d.high-d.low)).where(d.high!=d.low,.5).shift(1)
    d["upper"]=((d.high-d[["open","close"]].max(axis=1))/(d.high-d.low)).where(d.high!=d.low,0).shift(1)
    d["bias20"]=(c/c.rolling(20).mean()-1).shift(1)*100
    d["decelerate"]=((c/c.shift(1)-1)<(c.shift(1)/c.shift(2)-1)).shift(1).fillna(False)
    d["gap"]=100*(d.open/d.preclose-1)
    for p in ["rt","pt"]:
        d[p+"_cash"]=cashflow(d.open,d.close,d.date,p.upper())
        d[p+"_pct"]=100*d[p+"_cash"]/(1000*d.open)
    d["extra_cash_needed"]=np.maximum(0,-d.rt_cash)
    return d

def tests():
    dates=pd.Series(pd.to_datetime(["2026-01-01"]))
    rt=cashflow(pd.Series([100.]),pd.Series([90.]),dates)
    pt=cashflow(pd.Series([100.]),pd.Series([90.]),dates,"PT")
    assert rt.iloc[0]>0 and pt.iloc[0]<0 and (rt+pt).iloc[0]<0
    c=pd.Series(np.linspace(10,100,150))
    assert stage(c,"frozen").iloc[-1]=="U"
    altered=c.copy(); altered.iloc[-1]=1
    assert stage(c,"frozen").iloc[-1]==stage(altered,"frozen").iloc[-1]
    # Equity drawdown must include initial zero.
    g=pd.DataFrame(dict(rt_cash=[-10.,5.],rt_pct=[-1.,.5],ordinal=[1,2]))
    assert metrics(g)["mdd_cash"]==-10
    assert cashflow(pd.Series([10.]),pd.Series([10.]),dates).iloc[0]<0

def run():
    if os.environ.get("GITHUB_ACTIONS")!="true":
        raise RuntimeError("Run market-data processing only on GitHub Actions")
    OUT.mkdir(parents=True,exist_ok=True)
    tests()
    raw,minute=load_inputs()
    d=prepare(raw)
    minute["date"]=pd.to_datetime(minute.date)
    for c in ["open","close","high","low","volume"]:
        minute[c]=pd.to_numeric(minute[c],errors="raise")
    minute=minute.sort_values(["date","time"])
    mg=minute.groupby("date").agg(m_open=("open","first"),m_close=("close","last"),m_high=("high","max"),m_low=("low","min"),bars=("close","size"))
    joined=d.set_index("date").join(mg)
    calpath=Path("data/601138_intraday/pytdxdata_1min/daily_trade_calendar.csv")
    cal=pd.read_csv(calpath)
    datecol=next(c for c in cal if c.lower() in ["date","trade_date","calendar_date"])
    caldates=set(pd.to_datetime(cal[datecol]))
    snapshots=[]
    for p in sorted(Path("data/601138_intraday/pytdxdata_1min/snapshot_yearly").glob("*.csv")):
        s=pd.read_csv(p)
        dc=next(c for c in s if c.lower() in ["datetime","dt","time","timestamp"])
        s["dt"]=pd.to_datetime(s[dc])
        pc=next(c for c in s if c.lower() in ["price","close"])
        s[pc]=pd.to_numeric(s[pc],errors="raise")
        s["date"]=s.dt.dt.normalize()
        a=s.sort_values("dt").groupby("date").agg(s_open=(pc,"first"),s_close=(pc,"last"),rows=(pc,"size"))
        a["duplicate_dt"]=int(s.dt.duplicated().sum())
        snapshots.append(a)
    snap=pd.concat(snapshots).sort_index()
    joined=joined.join(snap)
    primary=d[d.date>=RULES["primary_start"]]
    validminute=joined.m_open.notna()
    audit={
        "data_cutoff":str(d.date.max().date()),"daily_days":len(d),"snapshot_days":len(snap),
        "daily_not_snapshot":[str(x.date()) for x in sorted(set(d.date)-set(snap.index))],
        "snapshot_not_daily":[str(x.date()) for x in sorted(set(snap.index)-set(d.date))],
        "calendar_columns":list(cal.columns),
        "daily_not_calendar":[str(x.date()) for x in sorted(set(d.date)-caldates)],
        "minute_days":len(mg),"minute_duplicate_timestamps":int(minute.duplicated(["date","time"]).sum()),
        "minute_open_mismatch_gt_001":int(((joined.open-joined.m_open).abs()>.01).sum()),
        "minute_close_mismatch_gt_001":int(((joined.close-joined.m_close).abs()>.01).sum()),
        "snapshot_open_mismatch_gt_001":int(((joined.open-joined.s_open).abs()>.01).sum()),
        "snapshot_close_mismatch_gt_001":int(((joined.close-joined.s_close).abs()>.01).sum()),
        "snapshot_row_counts":snap.rows.value_counts().to_dict(),
        "snapshot_duplicate_dt_total":int(snap.groupby(snap.index.year).duplicate_dt.first().sum()),
        "action_dates":d.loc[(d.action_ratio-1).abs()>.0001,["date","action_ratio"]].astype(str).to_dict("records"),
        "primary_stage_disagreement":int((primary.stage!=primary.stage_v3).sum()),
        "price_basis":"Unadjusted BaoStock artifact; features use close/preclose cumulative chain. Not independently exchange-certified; chain has not been independently checked against vendor adjustment factors.",
        "cost_basis":"Historical commission assumption; date-varying stamp scenario, constant transfer scenario. Not account-confirmed or fully historical tariff-verified.",
        "tests":"cashflow direction, roundtrip costs, stage temporal nonleakage, initial-loss drawdown passed"
    }
    windows={"primary":d.date.ge("2024-01-02"),"old_main":d.date.between("2024-01-02","2026-06-25"),
             "viewed_tail":d.date.between("2026-06-26",RULES["end"]),"2023":d.date.dt.year.eq(2023),
             "early_stress":d.date.lt("2023-01-01"),"2024":d.date.dt.year.eq(2024),
             "2025":d.date.dt.year.eq(2025),"2026_ytd":d.date.dt.year.eq(2026)}
    baselines=[]
    for w,mask in windows.items():
        for version in ["stage","stage_v3"]:
            for s in ["ALL","U","R","D","C"]:
                g=d[mask&d[version].ne("UNKNOWN")&(True if s=="ALL" else d[version].eq(s))]
                baselines.append(dict(window=w,version=version,stage=s,**metrics(g)))
    base=pd.DataFrame(baselines)
    regions={
        "volume_lt08":d.vr.lt(.8),"volume_08_12":d.vr.ge(.8)&d.vr.lt(1.2),
        "volume_12_15":d.vr.ge(1.2)&d.vr.lt(1.5),"volume_ge15":d.vr.ge(1.5),
        "r3_le0":d.r3.le(0),"r3_0_3":d.r3.gt(0)&d.r3.le(3),"r3_3_6":d.r3.gt(3)&d.r3.le(6),"r3_gt6":d.r3.gt(6),
        "clv_lt04":d.clv.lt(.4),"clv_04_07":d.clv.ge(.4)&d.clv.lt(.7),"clv_ge07":d.clv.ge(.7),
        "upper_ge03":d.upper.ge(.3),
        "bias20_le_m5":d.bias20.le(-5),"bias20_m5_0":d.bias20.gt(-5)&d.bias20.le(0),
        "bias20_0_5":d.bias20.gt(0)&d.bias20.le(5),"bias20_gt5":d.bias20.gt(5),
        "r5_positive_decelerate":d.r5.gt(0)&d.decelerate,
        "r5_negative":d.r5.lt(0),
        "pair_volume_ge15_clv_lt04":d.vr.ge(1.5)&d.clv.lt(.4),
        "pair_volume_ge15_upper_ge03":d.vr.ge(1.5)&d.upper.ge(.3),
        "pair_decelerate_upper_ge03":d.r5.gt(0)&d.decelerate&d.upper.ge(.3),
        "pair_r5negative_volume_lt08":d.r5.lt(0)&d.vr.lt(.8)
    }
    rows=[]; trials=[]
    for s in ["U","R","D","C"]:
        mother=d.stage.eq(s)
        for name,mask in regions.items():
            sid=s+"__"+name
            selected=mother&mask&windows["primary"]
            g=d[selected]
            row=dict(id=sid,stage=s,region=name,**metrics(g))
            row["mother_n"]=int((mother&windows["primary"]).sum())
            row["coverage_pct"]=100*len(g)/row["mother_n"] if row["mother_n"] else 0
            row["opposite_mean_pct"]=metrics(g,"pt")["mean_pct"]
            row["opposite_cash"]=metrics(g,"pt")["cash"]
            row["complement_mean_pct"]=metrics(d[mother&~mask&windows["primary"]])["mean_pct"]
            row["mirror_candidate"]=bool(len(g) and row["mean_pct"]<0)
            row["large_loss_mirror"]=bool(len(g) and row["mean_pct"]<=-.5)
            for yr in [2024,2025,2026]:
                v=metrics(g[g.date.dt.year.eq(yr)])
                row[f"n_{yr}"]=v["n"]; row[f"mean_{yr}"]=v["mean_pct"]; row[f"cash_{yr}"]=v["cash"]
            rows.append(row)
            trials.append(dict(id=sid,dates=d.loc[selected,"date"].dt.strftime("%Y-%m-%d").tolist()))
    scan=pd.DataFrame(rows)
    cand=[]
    main_masks={}
    for version in ["stage","stage_v3"]:
        m=d[version].isin(["U","R"])&d.vr.ge(1.5)
        main_masks[version]=m
        for w,wm in windows.items():
            g=d[m&wm]
            cand.append(dict(version=version,window=w,**metrics(g),**stress(g)))
    sensitivity=[]
    for threshold in [1.2,1.3,1.4,1.5,1.6,1.7,1.8,2.0]:
        m=d.stage.isin(["U","R"])&d.vr.ge(threshold)&windows["primary"]
        new=m&~main_masks["stage"]
        sensitivity.append(dict(threshold=threshold,**metrics(d[m]),new_n=int(new.sum()),new_cash=metrics(d[new])["cash"],new_mean_pct=metrics(d[new])["mean_pct"]))
    sliprows=[]
    for slip in [.0005,.001,.002]:
        g=d[main_masks["stage"]&windows["primary"]].copy()
        g.rt_cash=cashflow(g.open,g.close,g.date,slip=slip)
        g.rt_pct=100*g.rt_cash/(1000*g.open)
        sliprows.append(dict(slip_each_bp=slip*10000,**metrics(g)))
    # Matched dates used for direct open vs close proxy comparison.
    old=d[main_masks["stage_v3"]&windows["old_main"]].set_index("date").join(snap)
    old["proxy_rt_cash"]=cashflow(old.s_open,old.s_close,pd.Series(old.index,index=old.index))
    old["proxy_rt_pct"]=100*old.proxy_rt_cash/(1000*old.s_open)
    old.to_csv(OUT/"old_candidate_proxy_comparison.csv")
    d.to_csv(OUT/"daily_features_and_cashflows.csv",index=False)
    joined.to_csv(OUT/"daily_minute_snapshot_audit.csv")
    base.to_csv(OUT/"baselines.csv",index=False)
    scan.to_csv(OUT/"bounded_scan.csv",index=False)
    scan[scan.mirror_candidate].to_csv(OUT/"positive_mirror_candidates.csv",index=False)
    pd.DataFrame(cand).to_json(OUT/"candidate_windows.json",orient="records",indent=2)
    pd.DataFrame(sensitivity).to_csv(OUT/"volume_sensitivity.csv",index=False)
    pd.DataFrame(sliprows).to_csv(OUT/"cost_stress.csv",index=False)
    pd.crosstab(primary.stage,primary.stage_v3).to_csv(OUT/"stage_confusion.csv")
    (OUT/"audit.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2))
    (OUT/"trial_registry.json").write_text(json.dumps(trials,indent=2))
    (OUT/"rules.json").write_text(json.dumps(RULES,ensure_ascii=False,indent=2))
    # Causal mutation check across the complete feature pipeline.
    modified=raw.copy()
    last=modified.index[-1]
    modified.loc[last,["open","high","low","close"]]=[90.,100.,80.,95.]
    modified.loc[last,"pctChg"]=100*(95/float(modified.loc[last,"preclose"])-1)
    md=prepare(modified)
    for col in ["stage","stage_v3","vr","r3","r5","clv","upper","bias20","decelerate"]:
        pd.testing.assert_series_equal(d[col],md[col])
    selected=scan[(scan.n>=15)&(scan.mean_pct>0)].sort_values("cash",ascending=False)
    mirror=scan[scan.large_loss_mirror].sort_values("mean_pct")
    report=[
        "# 工业富联反T：GitHub首批审计与有限研究",
        "事实：计算在GitHub Actions运行；数据截至 "+RULES["end"]+"。全部历史均为探索/复核，不是独立前瞻。",
        "## 审计",json.dumps(audit,ensure_ascii=False,indent=2),
        "## 主定义四阶段基线（2024起）",md_table(base[(base.window=="primary")&(base.version=="stage")]),
        "## RT-UR-VOL 双阶段定义及窗口",md_table(pd.DataFrame(cand).drop(columns=["month_block_ci95"],errors="ignore")),
        "## 主定义量比邻域",md_table(pd.DataFrame(sensitivity)),
        "## 主定义成本压力",md_table(pd.DataFrame(sliprows)),
        "## 有限扫描：N至少15且均净为正的区域（并非通过验收）",
        md_table(selected[["id","n","coverage_pct","mean_pct","cash","worst_pct","mean_2024","mean_2025","mean_2026"]]),
        "## 明显反T亏损区域：独立扣费的正T候选",
        md_table(mirror[["id","n","mean_pct","opposite_mean_pct","opposite_cash"]]),
        "## 边界与下一步",
        "样本来自供应商日线及同供应商5分钟，跨频率一致不是独立认证。信号连续链须与复权因子交叉核验。",
        "88个预登记区域存在重叠及多重选择；N>=15只是展示条件，不能视为统计合格。全部试验与逐日底稿在results。",
        "Mirror -0.5%是宽松登记线，所有负区域也保留；反方向收益独立扣费，不直接取反净收益。",
        "收益率以当天开盘1000股市值为分母；现金PF和收益率PF分开。固定1000股收益非真实账户。",
        "回补额外现金需求逐日保存；尚未把有限现金及集合竞价成交转为真实可执行账户结果。",
        "未加入自适应止盈止损，snapshot不冒充分钟OHLC；暂无实际交易或前瞻记录。",
        "## 验证","现金流方向、正反费用不互为相反数、初始亏损回撤、阶段及全特征当日篡改不影响当日信号检查通过。"
    ]
    (ROOT/"REPORT.md").write_text("\n\n".join(report),encoding="utf-8")
    manifests={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name!="manifest.json"}
    (ROOT/"manifest.json").write_text(json.dumps({"code_sha":os.environ.get("GITHUB_SHA"),"run_id":os.environ.get("GITHUB_RUN_ID"),"sha256":manifests},indent=2))
    print((ROOT/"REPORT.md").read_text())



def export_all_mirrors(d):
    """Symmetric candidate registration; comparison direction always independently charged."""
    records=[]
    def register(identifier,g,scope,source_direction="rt"):
        opposite="pt" if source_direction=="rt" else "rt"
        a,b=metrics(g,source_direction),metrics(g,opposite)
        if not a["n"] or a["mean_pct"]>=0:
            return
        records.append(dict(id=identifier,scope=scope,source_direction=source_direction,
                            opposite_direction=opposite,n=a["n"],source_mean_pct=a["mean_pct"],
                            source_cash=a["cash"],opposite_mean_pct=b["mean_pct"],opposite_cash=b["cash"],
                            large_loss=a["mean_pct"]<=-.5,status="research_candidate_only",
                            start=str(g.date.min().date()),end=str(g.date.max().date())))
    trials=json.loads((OUT/"trial_registry.json").read_text())
    for t in trials:
        g=d[d.date.isin(pd.to_datetime(t["dates"]))]
        register(t["id"],g,"primary_bounded_scan")
    windows={"primary":d.date.ge("2024-01-02"),"old_main":d.date.between("2024-01-02","2026-06-25"),
             "viewed_tail":d.date.between("2026-06-26",RULES["end"]),"2023":d.date.dt.year.eq(2023),
             "early_stress":d.date.lt("2023-01-01"),"2024":d.date.dt.year.eq(2024),
             "2025":d.date.dt.year.eq(2025),"2026_ytd":d.date.dt.year.eq(2026)}
    for version in ["stage","stage_v3"]:
        for w,wm in windows.items():
            for s in ["ALL","U","R","D","C"]:
                m=wm&d[version].ne("UNKNOWN")&(True if s=="ALL" else d[version].eq(s))
                register(version+"_"+s,d[m],w+"_baseline")
            m=wm&d[version].isin(["U","R"])&d.vr.ge(1.5)
            register("RT_UR_VOL_"+version,d[m],w+"_candidate")
    primary=windows["primary"]
    base=d.stage.isin(["U","R"])&d.vr.ge(1.5)
    for threshold in [1.2,1.3,1.4,1.5,1.6,1.7,1.8,2.0]:
        m=primary&d.stage.isin(["U","R"])&d.vr.ge(threshold)
        register("UR_volume_ge_"+str(threshold),d[m],"primary_sensitivity")
        register("UR_volume_ge_"+str(threshold)+"_new",d[m&~base],"primary_increment_only")
    # Verify both registration directions using synthetic, deterministic cashflows.
    sample=pd.DataFrame({"date":pd.to_datetime(["2026-01-01"]),"ordinal":[0],
                         "rt_cash":[100.],"rt_pct":[1.],"pt_cash":[-140.],"pt_pct":[-1.4]})
    n=len(records)
    register("test",sample,"test","pt")
    assert records[-1]["opposite_direction"]=="rt" and records[-1]["opposite_mean_pct"]==1
    records=records[:n]
    pd.DataFrame(records).to_csv(OUT/"mirror_registry_all_scopes.csv",index=False)
    return records

def supplement():
    """No new candidate search: validate the fixed registry and execution proxies."""
    import sys
    d=pd.read_csv(OUT/"daily_features_and_cashflows.csv",parse_dates=["date"])
    scan=pd.read_csv(OUT/"bounded_scan.csv")
    trials=json.loads((OUT/"trial_registry.json").read_text())
    all_mirrors=export_all_mirrors(d)
    masks={t["id"]:d.date.isin(pd.to_datetime(t["dates"])) for t in trials}
    primary=d.date.ge("2024-01-02")
    masks["RT_UR_VOL_FROZEN"]=primary&d.stage.isin(["U","R"])&d.vr.ge(1.5)
    masks["RT_UR_VOL_V3"]=primary&d.stage_v3.isin(["U","R"])&d.vr.ge(1.5)
    original=masks["RT_UR_VOL_FROZEN"]
    robustness=[]
    for name,mask in masks.items():
        g=d[mask]
        v=dict(id=name,**metrics(g),**stress(g))
        for year in [2024,2025,2026]:
            v[f"exclude_{year}_pct"]=metrics(g[g.date.dt.year.ne(year)])["mean_pct"]
        v["new_n"]=int((mask&~original).sum())
        v["new_cash"]=metrics(d[mask&~original])["cash"]
        v["new_mean_pct"]=metrics(d[mask&~original])["mean_pct"]
        v["min_starting_reserve_ex_post"]=float(max(0,-np.r_[0,g.rt_cash.cumsum()].min()))
        v["max_single_day_topup"]=float(g.extra_cash_needed.max()) if len(g) else None
        robustness.append(v)
    robust=pd.DataFrame(robustness)
    robust.to_json(OUT/"all_candidate_robustness.json",orient="records",indent=2)
    selected=robust[(robust.n>=15)&(robust.mean_pct>0)].copy()
    selected["block_lo"]=selected.month_block_ci95.map(lambda x:x[0] if isinstance(x,list) else None)
    selected["block_hi"]=selected.month_block_ci95.map(lambda x:x[1] if isinstance(x,list) else None)
    # Independent vendor query checks the reconstructed return chain and archive freshness.
    qpath=SOURCE/"baostock_qfq_crosscheck.csv"
    querycode="""import baostock as bs
import pandas as pd
from pathlib import Path
p=Path("research/foxconn_t0_20260913/source")
lg=bs.login()
assert lg.error_code=="0",lg.error_msg
for flag,name in [("2","baostock_qfq_crosscheck.csv"),("3","baostock_raw_crosscheck.csv")]:
    rs=bs.query_history_k_data_plus("sh.601138","date,open,high,low,close,preclose,volume",start_date="2018-06-08",end_date="2026-09-11",frequency="d",adjustflag=flag)
    rows=[]
    while rs.error_code=="0" and rs.next(): rows.append(rs.get_row_data())
    assert rs.error_code=="0",rs.error_msg
    pd.DataFrame(rows,columns=rs.fields).to_csv(p/name,index=False)
bs.logout()
"""
    qc={"status":"unattempted"}
    if not qpath.exists():
        try:
            completed=subprocess.run([sys.executable,"-c",querycode],capture_output=True,text=True,timeout=180)
            (SOURCE/"vendor_query_log.txt").write_text(completed.stdout+"\n"+completed.stderr)
            qc["query_returncode"]=completed.returncode
        except subprocess.TimeoutExpired:
            qc={"status":"vendor_timeout_180s"}
    if qpath.exists():
        q=pd.read_csv(qpath,parse_dates=["date"]).set_index("date")
        z=d.set_index("date").join(q.close.rename("vendor_qfq"))
        complete=z.vendor_qfq.notna().all()
        normalized=z.vendor_qfq/z.vendor_qfq.iloc[-1]
        local=z.signal_close/z.signal_close.iloc[-1]
        qc.update(status="vendor_qfq_available",rows=len(q),all_dates_present=bool(complete),
                  max_normalized_difference=float((normalized-local).abs().max()))
        if complete:
            st=stage(pd.Series(z.vendor_qfq.to_numpy()),"frozen")
            qc["primary_stage_disagreement_with_vendor_qfq"]=int((st[primary.to_numpy()].to_numpy()!=d.loc[primary,"stage"].to_numpy()).sum())
        rp=SOURCE/"baostock_raw_crosscheck.csv"
        if rp.exists():
            r=pd.read_csv(rp,parse_dates=["date"]).set_index("date")
            rr=d.set_index("date").join(r[["open","close"]],rsuffix="_fresh")
            qc["fresh_raw_missing_dates"]=int(rr.open_fresh.isna().sum())
            qc["fresh_raw_open_different_gt001"]=int((abs(rr.open-rr.open_fresh)>.01).sum())
            qc["fresh_raw_close_different_gt001"]=int((abs(rr.close-rr.close_fresh)>.01).sum())
    (OUT/"vendor_crosscheck.json").write_text(json.dumps(qc,indent=2))
    raw,minute=load_inputs()
    minute["date"]=pd.to_datetime(minute.date)
    minute["stamp"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S")
    minute=minute.sort_values(["date","stamp"])
    mismatch=pd.read_csv(OUT/"daily_minute_snapshot_audit.csv",parse_dates=["date"])
    mismatch=mismatch[(mismatch.close-mismatch.m_close).abs()>.01]
    mismatch[["date","open","close","m_open","m_close","bars"]].to_csv(OUT/"minute_close_mismatch_dates.csv",index=False)
    execution=[]; account=[]
    # Fixed time alternatives, not optimized exits. The next bar Open is an indicative price.
    for name in ["RT_UR_VOL_FROZEN","RT_UR_VOL_V3"]:
        g=d[masks[name]].copy()
        for target in ["09:40","09:45"]:
            # Bar ending 09:40 starts at 09:35; bar ending 09:45 starts at 09:40.
            px=minute[minute.stamp.dt.strftime("%H:%M").eq(target)].set_index("date").open
            gg=g.set_index("date").join(px.rename("execution_open"))
            missing=int(gg.execution_open.isna().sum())
            if missing:
                execution.append(dict(id=name,next_bar_end=target,status="missing",missing_days=missing));continue
            gg["rt_cash"]=cashflow(gg.execution_open,gg.close,pd.Series(gg.index,index=gg.index))
            gg["rt_pct"]=100*gg.rt_cash/(1000*gg.open)
            execution.append(dict(id=name,next_bar_end=target,status="indicative_not_guaranteed",**metrics(gg),delta_cash=float(gg.rt_cash.sum()-g.rt_cash.sum())))
            gg.to_csv(OUT/(name+"_execution_"+target.replace(":","")+".csv"))
        # Finite-cash scenario: cease on first inability to restore inventory, never retrospectively skip.
        for reserve in [0.,2000.,float(d.loc[primary,"open"].iloc[0]*1000)]:
            balance=reserve; failure=None; done=0
            for _,row in g.iterrows():
                next_balance=balance+row.rt_cash
                if next_balance < -1e-8:
                    failure=str(row.date.date());break
                balance=next_balance;done+=1
            account.append(dict(id=name,initial_reserve=reserve,completed_roundtrips=done,
                                first_unfunded_rebuy_date=failure,ending_cash_if_completed=balance if failure is None else None,
                                incremental_pnl_if_completed=balance-reserve if failure is None else None))
    pd.DataFrame(execution).to_csv(OUT/"fixed_execution_proxies.csv",index=False)
    pd.DataFrame(account).to_csv(OUT/"finite_cash_scenarios.csv",index=False)
    # Broader candidate support is descriptive; do not optimize rules to pass this review.
    selected["status"]="insufficient_or_observation"
    parts=[
        "# 工业富联反T：候选复核与执行边界",
        "事实：固定首批88区域，没有新增搜索或重新挑阈值；所有结果都是已查看历史。",
        "## 供应商复权与原价交叉核验",json.dumps(qc,ensure_ascii=False,indent=2),
        "供应商复权序列与原价新查询可核查重建，但不是独立交易所认证。",
        "## 正收益区域的反证",
        md_table(selected[["id","n","mean_pct","cash","block_lo","block_hi","delete_top3_pct","delete_top5_pct","exclude_2024_pct","exclude_2025_pct","exclude_2026_pct","new_n","new_cash"]]),
        "## 固定时间执行价格敏感性",md_table(pd.DataFrame(execution)),
        "09:40结束bar的Open为09:35附近指示价，09:45结束bar同理；没有订单簿、排队与真实成交证据，不称已验证交易收益。",
        "## 有限现金回补场景",md_table(pd.DataFrame(account)),
        "持有1000旧仓，现金仅随成功反T往返变化。失败日不虚构买回，不把失败之后收益纳入完整账户。未处理差异化红利税、股权登记权利、其他持仓和利息；这些是模拟边界。",
        "## 分钟收盘异常日期",md_table(mismatch[["date","close","m_close","bars"]]),
        "## 双向线索登记",
        f"首批88区域中，反T负收益{int(scan.mirror_candidate.sum())}个，均净<=-0.5% {int(scan.large_loss_mirror.sum())}个。均是重叠研究区域，不能相加为独立机会。",
        "所有负区域的正T成本后结果已保留。未来正T研究采用相同镜像登记，不把负净收益机械取反。",
        "All-scope mirror entries: "+str(len(all_mirrors))+"; see mirror_registry_all_scopes.csv.",
        "## 收口",
        "现阶段不发布正式反T交易规则。保留原V3 RT-UR-VOL作为独立旧候选，主阶段版本单独登记；不能选择更漂亮阶段覆盖另一版。",
        "其余区域按完整反证保留观察或停止，不用分钟止损救活不稳定方向。隔夜未启动，正T未优化。",
        "## 前瞻规格（待实际运行）",
        "前一交易日完成后封存输入版本、stage两版、volume ratio及候选命中；集合竞价前记录计划。所有日期含无信号日记录；收盘后追加结果，事后补录独立标记。",
        "观察规则限两版RT-UR-VOL，彼此为对照不相加。仅纸面观察，不发送订单。新信号不足不调阈值；达到新增30个去重信号后阶段复核，这只是预设观察周期，不保证统计充分。",
        "目前未启动自动前瞻、未获得未来数据或真实交易。后续若继续事件探索，须另登记新批次和有限假设，不覆盖本批历史。"
    ]
    (ROOT/"REVIEW.md").write_text("\n\n".join(parts),encoding="utf-8")
    manifest={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.rglob("*")) if p.is_file() and p.name!="manifest.json"}
    (ROOT/"manifest.json").write_text(json.dumps({"code_sha":os.environ.get("GITHUB_SHA"),"run_id":os.environ.get("GITHUB_RUN_ID"),"sha256":manifest},indent=2))
    print((ROOT/"REVIEW.md").read_text())

if __name__=="__main__":
    p=argparse.ArgumentParser(); p.add_argument("--test",action="store_true"); args=p.parse_args()
    if args.test: tests()
    else:
        run()
        supplement()
