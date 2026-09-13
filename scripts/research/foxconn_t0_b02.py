#!/usr/bin/env python3
"""Batch 02: fixed hypotheses, candidate failures. GitHub-only computation."""
import os,json,hashlib,subprocess,sys,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_t0_audit as old

ROOT=Path("research/foxconn_t0_20260913_b02")
OUT=ROOT/"results"
SOURCE=ROOT/"source"
PRE=Path("research/foxconn_t0_20260913")
CONTRACT={
"batch":"foxconn-t0-20260913-b02","cutoff":"2026-09-11",
"parent_result":"ac5b6e3af988b609a40f6cf16737b4dcf2c8871b",
"stage":"frozen positive stage; no re-optimization",
"hypotheses":{
"failed_breakout":"Previous adjusted high exceeds preceding 20 highs, previous close returns below that old high.",
"failed_rebound":"Previous 3-day return positive, previous candle red, previous close below MA20.",
"distribution3":"Previous 3-day average volume >=1.2 times preceding 20-day average (excludes these 3 days), previous R3<=0.",
"relative_weak":"Previous stock close-to-close return <0 while SSE composite return >0.",
"gapdown_red":"Today gap<=-1%, previous red candle. Open-dependent; benchmark and 09:35 indicative execution separate.",
"gapup_weak":"Today gap>=1%, previous CLV<0.4. Open-dependent; benchmark and 09:35 indicative execution separate."
},
"trial_budget":"6 hypotheses x 4 stages =24; unavailable index is UNKNOWN, not false",
"validation":"All history explored. Chronological slices/blocks describe stability, not untouched OOS.",
"mirror":"All negative same-date source outcomes registered; <=-0.5% inclusive emphasis only.",
"failure_audit":"Three pre-existing candidates; ex-ante fields separate from future MAE/MFE. No adaptive veto.",
"stop":"No parameter expansion this batch. Preserve sparse and failed cells.",
"fees":"Reuse exact parent scenario; actual commissions/dividend taxes/orderbook not certified."
}

def hypotheses(d,index=None):
    c=d.signal_close
    scale=c/d.close
    hi=d.high*scale
    prev20hi=hi.shift(1).rolling(20).max()
    v3=d.volume.rolling(3).mean()
    vref=d.volume.shift(3).rolling(20).mean()
    m={}
    m["failed_breakout"]=((hi>prev20hi)&(c<=prev20hi)).shift(1).fillna(False)
    m["failed_rebound"]=((c/c.shift(3)>1)&(d.close<d.open)&(c<c.rolling(20).mean())).shift(1).fillna(False)
    m["distribution3"]=((v3>=1.2*vref)&(c/c.shift(3)<=1)).shift(1).fillna(False)
    m["relative_weak"]=pd.Series(False,index=d.index)
    if index is not None:
        ic=d.date.map(index.set_index("date").close)
        m["relative_weak"]=((c/c.shift(1)<1)&(ic/ic.shift(1)>1)).shift(1).fillna(False)
    m["gapdown_red"]=d.gap.le(-1)&(d.close<d.open).shift(1).fillna(False)
    m["gapup_weak"]=d.gap.ge(1)&d.clv.lt(.4)
    return m

def fetch_index():
    code="""import baostock as bs,pandas as pd
from pathlib import Path
lg=bs.login();assert lg.error_code=="0"
rs=bs.query_history_k_data_plus("sh.000001","date,close",start_date="2018-06-08",end_date="2026-09-11",frequency="d",adjustflag="3")
rows=[]
while rs.error_code=="0" and rs.next(): rows.append(rs.get_row_data())
assert rs.error_code=="0",rs.error_msg
pd.DataFrame(rows,columns=rs.fields).to_csv("research/foxconn_t0_20260913_b02/source/sse_index.csv",index=False)
bs.logout()
"""
    p=SOURCE/"sse_index.csv"
    try:
        r=subprocess.run([sys.executable,"-c",code],capture_output=True,text=True,timeout=90)
        (SOURCE/"index_log.txt").write_text(r.stdout+"\n"+r.stderr)
        if r.returncode: return None
    except subprocess.TimeoutExpired:
        (SOURCE/"index_log.txt").write_text("timeout 90s")
        return None
    x=pd.read_csv(p,parse_dates=["date"])
    x.close=pd.to_numeric(x.close,errors="raise")
    assert not x.date.duplicated().any()
    return x

def run():
    assert os.environ.get("GITHUB_ACTIONS")=="true","Data processing restricted to GitHub"
    SOURCE.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    old.tests()
    # Verify parent evidence before reuse.
    manifest=json.loads((PRE/"manifest.json").read_text())
    for name in ["daily_features_and_cashflows.csv","bounded_scan.csv","trial_registry.json"]:
        p=PRE/"results"/name
        assert hashlib.sha256(p.read_bytes()).hexdigest()==manifest["sha256"][str(p)]
    d=pd.read_csv(PRE/"results/daily_features_and_cashflows.csv",parse_dates=["date"])
    ix=fetch_index()
    if ix is not None:
        assert d.date.isin(ix.date).all(),"Index date coverage incomplete"
    masks=hypotheses(d,ix)
    # Mutate the final OHLC and volume: yesterday-only signal masks must not change.
    z=d.copy();z.loc[z.index[-1],["open","high","low","close","signal_close","volume"]]=[100,120,90,110,300,1e12]
    zm=hypotheses(z,ix)
    for name in ["failed_breakout","failed_rebound","distribution3","relative_weak"]:
        pd.testing.assert_series_equal(masks[name],zm[name])
    (ROOT/"CONTRACT.json").write_text(json.dumps(CONTRACT,ensure_ascii=False,indent=2))
    primary=d.date.ge("2024-01-02")
    with zipfile.ZipFile(PRE/"source/601138-full-5min-history.zip") as f:
        minute=pd.read_csv(f.open(next(n for n in f.namelist() if n.endswith("601138_5min_all.csv"))))
    minute["date"]=pd.to_datetime(minute.date)
    minute["dt"]=pd.to_datetime(minute.time.astype(str).str[:14],format="%Y%m%d%H%M%S")
    minute=minute.sort_values(["date","dt"])
    minute[["open","high","low","close"]]=minute[["open","high","low","close"]].apply(pd.to_numeric,errors="raise")
    px=minute[minute.dt.dt.strftime("%H:%M").eq("09:40")].set_index("date").open
    prior=d.stage.isin(["U","R"])&d.vr.ge(1.5)
    rows=[];mirrors=[];ledger=[];periods=[];diag=[]
    windows={"primary":primary,"2023":d.date.dt.year.eq(2023),"early":d.date.lt("2023-01-01"),
             "2024":d.date.dt.year.eq(2024),"2025":d.date.dt.year.eq(2025),"2026_ytd":d.date.dt.year.eq(2026)}
    for stage in ["U","R","D","C"]:
        for name,m in masks.items():
            sid=stage+"__"+name
            if name=="relative_weak" and ix is None:
                rows.append(dict(id=sid,status="UNKNOWN_index_unavailable",n=None));continue
            full=d.stage.eq(stage)&m
            g=d[full&primary].copy()
            stats=old.metrics(g)
            row=dict(id=sid,status="historical_exploration",**stats)
            row["mother_n"]=int((d.stage.eq(stage)&primary).sum())
            row["coverage_pct"]=100*len(g)/row["mother_n"]
            row["new_n"]=int((full&primary&~prior).sum())
            row["new_cash"]=old.metrics(d[full&primary&~prior])["cash"]
            row["new_mean_pct"]=old.metrics(d[full&primary&~prior])["mean_pct"]
            st=old.stress(g)
            row["block_low"]=st.get("month_block_ci95",[None,None])[0]
            row["block_high"]=st.get("month_block_ci95",[None,None])[1]
            row["delete_top3_pct"]=st.get("delete_top3_pct")
            for w,wm in windows.items():
                gg=d[full&wm]
                v=old.metrics(gg)
                periods.append(dict(id=sid,window=w,**v))
                if w in ["2024","2025","2026_ytd"]:
                    row[w+"_n"]=v["n"];row[w+"_pct"]=v["mean_pct"]
                if v["n"] and v["mean_pct"]<0:
                    p=old.metrics(gg,"pt")
                    mirrors.append(dict(id=sid,scope=w,n=v["n"],rt_pct=v["mean_pct"],pt_pct=p["mean_pct"],pt_cash=p["cash"],large_loss=v["mean_pct"]<=-.5))
            # Open dependent signals cannot assume a completed auction entry.
            gg=g.set_index("date").join(px.rename("later_open"))
            if len(gg) and gg.later_open.notna().all():
                gg["rt_cash"]=old.cashflow(gg.later_open,gg.close,pd.Series(gg.index,index=gg.index))
                gg["rt_pct"]=100*gg.rt_cash/(1000*gg.open)
                v=old.metrics(gg)
                row["indicative_0935_pct"]=v["mean_pct"];row["indicative_0935_cash"]=v["cash"]
            else:
                row["indicative_0935_pct"]=None;row["indicative_0935_cash"]=None
            row["decision_time"]="after_open" if name.startswith("gap") else "previous_close"
            rows.append(row)
            for _,r in g.iterrows():
                ledger.append(dict(id=sid,date=str(r.date.date()),stage=stage,open=r.open,close=r.close,
                                   rt_pct=r.rt_pct,rt_cash=r.rt_cash,gap=r.gap,vr=r.vr,clv=r.clv,r3=r.r3))
    results=pd.DataFrame(rows)
    results.to_csv(OUT/"hypothesis_matrix.csv",index=False)
    pd.DataFrame(periods).to_csv(OUT/"period_results.csv",index=False)
    pd.DataFrame(mirrors).to_csv(OUT/"positive_mirror_candidates.csv",index=False)
    pd.DataFrame(ledger).to_csv(OUT/"new_hypothesis_trades.csv",index=False)
    # Review three old candidates without deriving filters from realized failures.
    candidates={
        "UR_VOL_frozen":primary&prior,
        "UR_VOL_v3":primary&d.stage_v3.isin(["U","R"])&d.vr.ge(1.5),
        "R_deceleration":primary&d.stage.eq("R")&d.r5.gt(0)&d.decelerate.astype(bool)
    }
    extreme=[];profiles=[];paths=[]
    for name,m in candidates.items():
        g=d[m].copy()
        for _,r in g.iterrows():
            bars=minute[minute.date.eq(r.date)]
            # Future extrema for diagnosis only, not entry features or executable stop fills.
            item=dict(candidate=name,date=str(r.date.date()),stage=r.stage,stage_v3=r.stage_v3,
                      rt_pct=r.rt_pct,rt_cash=r.rt_cash,gap=r.gap,vr=r.vr,clv=r.clv,r3=r.r3,
                      future_mae_pct=100*(bars.high.max()/r.open-1) if len(bars) else None,
                      future_mfe_pct=100*(1-bars.low.min()/r.open) if len(bars) else None)
            paths.append(item)
        for tag,mask in {"gap_negative":g.gap.lt(0),"gap_nonnegative":g.gap.ge(0),
                         "clv_lt04":g.clv.lt(.4),"clv_ge04":g.clv.ge(.4),
                         "year2024":g.date.dt.year.eq(2024),"year2025":g.date.dt.year.eq(2025),
                         "year2026":g.date.dt.year.eq(2026)}.items():
            v=old.metrics(g[mask])
            profiles.append(dict(candidate=name,tag=tag,**v))
        for kind,gg in [("worst",g.nsmallest(5,"rt_cash")),("best",g.nlargest(5,"rt_cash"))]:
            for _,r in gg.iterrows():
                extreme.append(dict(candidate=name,kind=kind,date=str(r.date.date()),rt_cash=r.rt_cash,rt_pct=r.rt_pct,
                                    gap=r.gap,vr=r.vr,clv=r.clv,r3=r.r3))
    pd.DataFrame(paths).to_csv(OUT/"old_candidate_path_diagnostics.csv",index=False)
    pd.DataFrame(profiles).to_csv(OUT/"old_candidate_exante_profiles.csv",index=False)
    pd.DataFrame(extreme).to_csv(OUT/"old_candidate_best_worst.csv",index=False)
    # Historical leave-one-calendar-year-out; no new independent OOS claim.
    for name,m in candidates.items():
        g=d[m]
        wins=g.rt_cash[g.rt_cash>0].sum()
        diag.append(dict(candidate=name,n=len(g),losers=int(g.rt_cash.lt(0).sum()),
                         best3_cash_share_of_positive=float(g.nlargest(3,"rt_cash").rt_cash.clip(lower=0).sum()/wins) if wins else None,
                         max_single_topup=float(g.extra_cash_needed.max()),
                         **{f"exclude_{year}_cash":old.metrics(g[g.date.dt.year.ne(year)])["cash"] for year in [2024,2025,2026]}))
    pd.DataFrame(diag).to_csv(OUT/"candidate_concentration.csv",index=False)

    path_summary=[]
    for name,m in candidates.items():
        g=d[m]
        net=float(g.rt_cash.sum())
        record=dict(candidate=name,n=len(g),best1_share_net=float(g.rt_cash.max()/net) if net else None,
                    best3_share_net=float(g.nlargest(3,"rt_cash").rt_cash.sum()/net) if net else None,
                    year2026_share_net=float(g.loc[g.date.dt.year.eq(2026),"rt_cash"].sum()/net) if net else None)
        path_rows=[]
        for _,r in g.iterrows():
            b=minute[minute.date.eq(r.date)].reset_index(drop=True)
            if b.empty or abs(float(b.close.iloc[-1])-r.close)>.01:
                path_rows.append(dict(date=str(r.date.date()),quality="unavailable_or_daily_close_mismatch"));continue
            adverse=np.flatnonzero((b.high/r.open-1).to_numpy()>=.02)
            favorable=np.flatnonzero((1-b.low/r.open).to_numpy()>=.01)
            ai=int(adverse[0]) if len(adverse) else None
            fi=int(favorable[0]) if len(favorable) else None
            if ai is not None and fi is not None:
                order="same_bar_unknown" if ai==fi else ("favorable_first" if fi<ai else "adverse_first")
            elif ai is not None:order="adverse_only"
            elif fi is not None:order="favorable_only"
            else:order="neither"
            path_rows.append(dict(date=str(r.date.date()),quality="ok",net_loser=bool(r.rt_cash<0),adverse2=ai is not None,
                                  favorable1=fi is not None,order=order))
        pp=pd.DataFrame(path_rows)
        pp.to_csv(OUT/(name+"_path_threshold_diagnosis.csv"),index=False)
        ok=pp[pp.quality.eq("ok")].copy()
        ok["net_loser"]=ok.net_loser.astype(bool)
        record["path_valid_n"]=len(ok)
        for label,gg in [("loser",ok[ok.net_loser]),("winner",ok[~ok.net_loser])]:
            record[label+"_n"]=len(gg)
            record[label+"_touched_favorable1"]=int(gg.favorable1.sum())
            record[label+"_touched_adverse2"]=int(gg.adverse2.sum())
            record[label+"_adverse_before_favorable"]=int(gg.order.isin(["adverse_first","adverse_only"]).sum())
            record[label+"_same_bar_unknown"]=int(gg.order.eq("same_bar_unknown").sum())
        path_summary.append(record)
    ps=pd.DataFrame(path_summary)
    ps.to_csv(OUT/"path_diagnosis_summary.csv",index=False)


    # Diagnostic follow-up: thresholds selected after path audit, explicitly exploratory.
    exit_rows=[];exit_trades=[]
    for name,m in candidates.items():
        g=d[m].copy()
        for mode in ["stop2","stop2_tp1"]:
            for execution in ["bar_touch_gap_aware","confirm_bar_then_next_open"]:
                h=g.copy()
                used=[];unavailable=0
                for idx,r in g.iterrows():
                    bars=minute[minute.date.eq(r.date)].reset_index(drop=True)
                    if bars.empty or abs(float(bars.close.iloc[-1])-r.close)>.01:
                        unavailable+=1;continue
                    stop=r.open*1.02;tp=r.open*.99
                    buy=r.close;reason="close";ambiguous=False;exit_at="15:00"
                    for k,b in bars.iterrows():
                        sl=b.high>=stop
                        take=mode=="stop2_tp1" and b.low<=tp
                        if not sl and not take:continue
                        ambiguous=bool(sl and take)
                        reason="stop" if sl else "tp"
                        if execution=="confirm_bar_then_next_open":
                            if k+1<len(bars):
                                buy=float(bars.iloc[k+1].open)
                                exit_at=str(bars.iloc[k+1].dt)
                            else:
                                # No post-close executable bar; scheduled closing fallback only.
                                buy=r.close;exit_at="scheduled_close"
                        else:
                            if b.open>=stop:buy=float(b.open);reason="stop_gap"
                            elif mode=="stop2_tp1" and b.open<=tp:buy=float(b.open);reason="tp_gap"
                            else:buy=float(stop if sl else tp)
                            exit_at=str(b.dt)
                        break
                    cash=float(old.cashflow(pd.Series([r.open]),pd.Series([buy]),pd.Series([r.date])).iloc[0])
                    h.loc[idx,"rt_cash"]=cash
                    h.loc[idx,"rt_pct"]=100*cash/(1000*r.open)
                    used.append(idx)
                    exit_trades.append(dict(candidate=name,mode=mode,execution=execution,date=str(r.date.date()),
                                            buy_base=buy,exit_at=exit_at,reason=reason,same_bar_ambiguous=ambiguous,
                                            rt_cash=cash,baseline_cash=r.rt_cash,delta_cash=cash-r.rt_cash))
                h=h.loc[used]
                ref=g.loc[used]
                v=dict(candidate=name,mode=mode,execution=execution,unavailable=unavailable,**old.metrics(h))
                v["baseline_cash"]=float(ref.rt_cash.sum())
                v["delta_cash"]=v["cash"]-v["baseline_cash"]
                v["baseline_winner_to_loss"]=int(((ref.rt_cash>0)&(h.rt_cash<0)).sum())
                for year in [2024,2025,2026]:
                    v["delta_"+str(year)]=float(h.loc[h.date.dt.year.eq(year),"rt_cash"].sum()-ref.loc[ref.date.dt.year.eq(year),"rt_cash"].sum())
                exit_rows.append(v)
    exits=pd.DataFrame(exit_rows)
    exits.to_csv(OUT/"fixed_exit_exploration.csv",index=False)
    pd.DataFrame(exit_trades).to_csv(OUT/"fixed_exit_trades.csv",index=False)
    (OUT/"fixed_exit_spec.json").write_text(json.dumps({
        "status":"post-diagnostic exploratory, not independently validated",
        "rules":["stop2","stop2_tp1"],"thresholds_frozen":[.02,.01],
        "base":"same old three candidates, same signals, no new event selection",
        "models":["gap-aware bar touch, stop first if ambiguous","bar-end confirmation then next bar open"],
        "fees":"same parent costs; price is simulation, no queue/orderbook guarantee",
        "limits":"same-bar chronology unknown; final-bar scheduled-close fallback is not post-close execution"
    },indent=2))

    coverage=[
        ["single day returns/volume/candle/location","all4","batch01 88 regions","covered narrowly; not exhaustive"],
        ["multi-day failed breakout","all4","batch02 fixed definition","tested; exact daily failure, not intraday breakout"],
        ["weak rebound under MA20","all4","batch02 fixed definition","tested; structural zero cells remain"],
        ["3day volume without price progress","all4","batch02 fixed definition","tested; no threshold tuning"],
        ["stock/index previous-day divergence","all4","batch02 fixed definition","tested" if ix is not None else "data unavailable"],
        ["opening gap interactions","all4","batch02 two fixed events","benchmark and after-open indicative prices split"],
        ["intraday reversal/TP/SL","all4","old E1 failure; first batch fixed times","not comprehensively tested; cannot infer fills from snapshots"],
        ["announcements/industry/US shocks","all4","historical partial evidence only","not covered this batch; needs point-in-time event data"],
        ["auction imbalance/orderflow","all4","no orderbook data","unavailable, not falsified"],
        ["true future validation","all4","no future samples","not started; never substitute historic resampling"]
    ]
    cov=pd.DataFrame(coverage,columns=["family","stages","evidence","boundary"])
    cov.to_csv(OUT/"coverage_register.csv",index=False)
    report=["# 反T第二批：假设覆盖与失败原因复核",
            "事实：全部计算在GitHub；数据至2026-09-11；六个预登记假设×四阶段，无参数扩展。",
            "## 覆盖边界",old.md_table(cov),
            "## 24个研究单元",
            old.md_table(results[["id","n","mean_pct","cash","coverage_pct","new_n","new_cash","2024_pct","2025_pct","2026_ytd_pct","decision_time","indicative_0935_pct"]]),
            "## 正收益区域的历史反证",
            old.md_table(results[results.mean_pct.gt(0)][["id","n","mean_pct","block_low","block_high","delete_top3_pct","new_mean_pct","indicative_0935_cash"]]),
            "## 原候选集中度",old.md_table(pd.DataFrame(diag)),
            "## 原候选事前字段分组（诊断，不自动过滤）",
            old.md_table(pd.DataFrame(profiles)[["candidate","tag","n","mean_pct","cash","worst_pct"]]),
            "## 最大亏损与盈利个案",
            old.md_table(pd.DataFrame(extreme)),
            "## 反方向候选",
            old.md_table(pd.DataFrame(mirrors)[lambda x:(x.scope=="primary")&x.large_loss][["id","n","rt_pct","pt_pct","pt_cash"]]),
            "## 路径诊断（非止盈止损回测）",old.md_table(ps),
            "固定诊断线为向下1%有利空间、向上2%不利空间；同5分钟bar不判断先后，触价不等于成交。阈值只作失败归因描述，不新建优化策略。",
            "## 固定退出的探索性比较",old.md_table(exits),
            "本比较在看完路径诊断后提出，属于新增样本内探索。固定2%止损及2%止损+1%止盈，不搜索其他阈值；两种执行价格假设都不是成交认证。",
            "## 解释限制",
            "亏损交易的MAE/MFE只用于事后路径描述，不可拿来作为当时知道的过滤条件。开盘后指示价不是成交认证。",
            "24个单元不是24条独立策略；六类机制的定义可能交叠。区间是历史描述，未校正历次选择；零样本不是机制失败。",
            "未搜索自适应止损阈值；补做固定退出探索，单列执行假设。正T仅登记，未启动真实交易、前瞻自动化或隔夜。",
            "## 验证",
            "父批次输入哈希、现金流确定性测试、前日假设的当日OHLC及成交量变动不影响当日信号测试通过。",
            "指数可用="+str(ix is not None)+"；全部行及失败记录见results。"]
    (ROOT/"REPORT.md").write_text("\n\n".join(report),encoding="utf-8")
    files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.rglob("*") if p.is_file() and p.name!="manifest.json"}
    (ROOT/"manifest.json").write_text(json.dumps(dict(code_sha=os.environ["GITHUB_SHA"],run_id=os.environ["GITHUB_RUN_ID"],parent_manifest=manifest,files=files),indent=2))
    print((ROOT/"REPORT.md").read_text())

if __name__=="__main__":run()
