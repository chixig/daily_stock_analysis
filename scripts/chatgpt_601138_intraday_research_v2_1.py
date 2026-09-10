#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业富联 601138｜RA-D1-V × 5分钟执行研究 V2.1

修订重点：
1. 修复 BaoStock 5分钟 High/Low 与日线 High/Low 不一致导致的误删：
   - 48根/46根以上 + 首Open + 末Close 是硬QC；
   - High/Low 差异只记 warning，不直接剔除。
2. 旧 pullback 只代表“第一次冲高后的回落确认”；
   新增 two_peak_fail：第一次高点 -> 回落 -> 第二次冲高失败 -> 再转弱。
3. 退出扩展：
   - Close
   - 固定 TP: 1.5 / 2.0 / 2.5 / 3.0%
   - 4%灾难止损
   - trailing buyback：盈利触发后等待从 running low 反弹0.5%再买回
4. 输出 2024 / 2025 / 2026 单年统计，防止现代窗口被单一年份贡献。
"""

from __future__ import annotations
import argparse, math, time
from pathlib import Path
from typing import Optional, Dict, Tuple
import baostock as bs
import numpy as np
import pandas as pd

STOCK = "sh.601138"
INDEX = "sh.000001"

COMMISSION_RATE = 0.0001354
MIN_COMMISSION = 5.0
TRANSFER_RATE = 0.00001
SLIPPAGE = 0.0005
SHARES = 1000

STAMP_OLD = 0.001
STAMP_NEW = 0.0005
STAMP_CUT_DATE = pd.Timestamp("2023-08-28")

FAST_SHOCK_VETO = 0.005
DISASTER_STOP = 0.04


def _to_df(rs):
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if rs.error_code != "0":
        raise RuntimeError(f"BaoStock error: {rs.error_code} {rs.error_msg}")
    return pd.DataFrame(rows, columns=rs.fields)


def query_daily(code, start, end, adjustflag):
    fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,pctChg"
    rs = bs.query_history_k_data_plus(
        code, fields, start_date=start, end_date=end, frequency="d", adjustflag=adjustflag
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","preclose","volume","amount","pctChg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def query_index_daily(start, end):
    fields = "date,code,open,high,low,close,preclose,volume,amount,pctChg"
    rs = bs.query_history_k_data_plus(
        INDEX, fields, start_date=start, end_date=end, frequency="d", adjustflag="3"
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","preclose","volume","amount","pctChg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def query_5m(day):
    ds = pd.Timestamp(day).strftime("%Y-%m-%d")
    fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"
    rs = bs.query_history_k_data_plus(
        STOCK, fields, start_date=ds, end_date=ds, frequency="5", adjustflag="3"
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","volume","amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["dt"] = pd.to_datetime(
        df["time"].str.slice(0,14), format="%Y%m%d%H%M%S", errors="coerce"
    )
    return df.dropna(subset=["dt","open","high","low","close"]).sort_values("dt").reset_index(drop=True)


def build_signals(qfq, raw, index, research_start):
    d = qfq.copy()
    d["ma5"] = d["close"].rolling(5).mean()
    d["ma20"] = d["close"].rolling(20).mean()
    d["ma60"] = d["close"].rolling(60).mean()
    d["ma20_prev"] = d["ma20"].shift(1)
    d["r20"] = d["close"] / d["close"].shift(20) - 1

    for c in ["open","close","ma5","ma20","ma60","ma20_prev","r20"]:
        d["prev_" + c] = d[c].shift(1)

    d["D"] = (
        (d["prev_close"] < d["prev_ma20"]) &
        (d["prev_ma20"] < d["prev_ma60"]) &
        (d["prev_ma20"] < d["prev_ma20_prev"]) &
        (d["prev_r20"] < 0)
    )
    d["C1_prev_up"] = d["prev_close"] > d["prev_open"]
    d["C4_open_above_ma5"] = d["open"] > d["prev_ma5"]

    idx = index[["date","open","preclose"]].copy()
    idx["sh_gap"] = idx["open"] / idx["preclose"] - 1
    d = d.merge(idx[["date","sh_gap"]], on="date", how="left")

    rr = raw[["date","open","high","low","close"]].rename(columns={
        "open":"raw_open","high":"raw_high","low":"raw_low","close":"raw_close"
    })
    d = d.merge(rr, on="date", how="left")

    d["signal"] = (
        d["D"] &
        d["C1_prev_up"] &
        d["C4_open_above_ma5"] &
        (d["sh_gap"] < FAST_SHOCK_VETO)
    )

    out = d[(d["date"] >= pd.Timestamp(research_start)) & d["signal"]].copy()
    return out[[
        "date","sh_gap","prev_close","prev_ma5","prev_ma20","prev_ma60","prev_r20",
        "raw_open","raw_high","raw_low","raw_close"
    ]].reset_index(drop=True)


def qc_minute(m, row, tol=0.03):
    if m.empty:
        return False, "empty"
    if len(m) < 46:
        return False, f"too_few_bars:{len(m)}"

    mo, mc = float(m.iloc[0]["open"]), float(m.iloc[-1]["close"])
    ro, rc = float(row["raw_open"]), float(row["raw_close"])
    if abs(mo-ro) > tol or abs(mc-rc) > tol:
        return False, f"hard_open_close_mismatch:open({mo:.3f}/{ro:.3f}),close({mc:.3f}/{rc:.3f})"

    mh, ml = float(m["high"].max()), float(m["low"].min())
    rh, rl = float(row["raw_high"]), float(row["raw_low"])
    warns = []
    if abs(mh-rh) > tol:
        warns.append(f"high({mh:.3f}!={rh:.3f})")
    if abs(ml-rl) > tol:
        warns.append(f"low({ml:.3f}!={rl:.3f})")
    if warns:
        return True, "ok_extreme_warning:" + ",".join(warns)
    return True, "ok"


def commission(amount):
    return max(MIN_COMMISSION, amount * COMMISSION_RATE)


def account_pnl(sell_raw, buy_raw, day):
    sell_px = sell_raw * (1-SLIPPAGE)
    buy_px = buy_raw * (1+SLIPPAGE)
    sa, ba = sell_px*SHARES, buy_px*SHARES
    comm = commission(sa) + commission(ba)
    transfer = (sa+ba) * TRANSFER_RATE
    stamp = sa * (STAMP_OLD if day < STAMP_CUT_DATE else STAMP_NEW)
    pnl = sa-ba-comm-transfer-stamp
    return pnl, pnl/(sell_raw*SHARES), comm+transfer+stamp


def find_limit(m, open_px, rise):
    target = open_px*(1+rise)
    hits = np.flatnonzero(m["high"].to_numpy() >= target)
    if not len(hits):
        return None
    i = int(hits[0])
    return i, target, m.iloc[i]["dt"].isoformat(), "limit"


def find_first_pullback(m, open_px, rise, pb, breakout_veto):
    running_high = -np.inf
    armed = False
    for i, r in m.iterrows():
        running_high = max(running_high, float(r["high"]))
        if running_high >= open_px*(1+rise):
            armed = True
        if armed and breakout_veto is not None and running_high >= open_px*(1+breakout_veto):
            return None
        if armed and float(r["close"]) <= running_high*(1-pb):
            return int(i), float(r["close"]), r["dt"].isoformat(), f"H={running_high:.3f}"
    return None


def find_two_peak_fail(m, open_px, rise, first_pb, breakout_veto=0.02,
                       retest_gap=0.003, second_drop=0.003):
    """
    真正二次冲高失败：
    第一高点 -> 回落 -> 第二次反抽接近P1 -> 未有效突破 -> 再回落确认。
    """
    p1 = None
    pulled = False
    p2 = None

    for i, r in m.iterrows():
        h, c = float(r["high"]), float(r["close"])

        if p1 is None:
            if h >= open_px*(1+rise):
                p1 = h
            continue

        if h >= open_px*(1+breakout_veto):
            return None

        if not pulled:
            if h > p1:
                p1 = h
            if c <= p1*(1-first_pb):
                pulled = True
            continue

        if p2 is None:
            if h > p1*1.001:
                p1, pulled = h, False
                continue
            if h >= p1*(1-retest_gap):
                p2 = h
            continue

        if h > p1*1.001:
            p1, pulled, p2 = h, False, None
            continue

        p2 = max(p2, h)
        if c <= p2*(1-second_drop):
            return int(i), c, r["dt"].isoformat(), f"P1={p1:.3f};P2={p2:.3f}"
    return None


def simulate_exit_fixed(m, entry_i, sell_px, tp=None, stop=None):
    after = m.iloc[entry_i+1:]
    if after.empty:
        r = m.iloc[-1]
        return float(r["close"]), "close", r["dt"].isoformat()

    for _, r in after.iterrows():
        stop_hit = stop is not None and float(r["high"]) >= sell_px*(1+stop)
        tp_hit = tp is not None and float(r["low"]) <= sell_px*(1-tp)
        if stop_hit:
            return sell_px*(1+stop), "stop", r["dt"].isoformat()
        if tp_hit:
            return sell_px*(1-tp), "tp", r["dt"].isoformat()

    r = m.iloc[-1]
    return float(r["close"]), "close", r["dt"].isoformat()


def simulate_exit_trail(m, entry_i, sell_px, activation, rebound=0.005, stop=DISASTER_STOP):
    """
    反T trailing buyback：
    先跌到 sell*(1-activation) 才激活；
    激活后记录 running low；
    以后某根5分钟收盘从 running low 反弹>=rebound，则买回。
    """
    after = m.iloc[entry_i+1:]
    armed = False
    running_low = None

    for _, r in after.iterrows():
        h, lo, c = float(r["high"]), float(r["low"]), float(r["close"])
        if stop is not None and h >= sell_px*(1+stop):
            return sell_px*(1+stop), "stop", r["dt"].isoformat()

        if not armed:
            if lo <= sell_px*(1-activation):
                armed = True
                running_low = lo
            continue

        running_low = min(running_low, lo)
        if c >= running_low*(1+rebound):
            return c, "trail_rebound", r["dt"].isoformat()

    r = m.iloc[-1]
    return float(r["close"]), "close_after_trail", r["dt"].isoformat()


def specs():
    out = []

    # baseline
    for tp in [None, .015, .020, .025, .030]:
        out.append(("open", 0.0, None, tp, None, None, "fixed"))

    # simple limit
    for rise in [.002,.003,.004,.005]:
        for tp in [None,.015,.020,.025,.030]:
            out.append(("limit", rise, None, tp, None, None, "fixed"))
        out.append(("limit", rise, None, .015, DISASTER_STOP, None, "fixed"))
        out.append(("limit", rise, None, None, DISASTER_STOP, None, "fixed"))

    # first pullback, with/without 2% pre-entry veto
    for rise in [.003,.005]:
        for pb in [.003,.004,.005]:
            for veto in [None,.02]:
                for tp in [None,.015,.020,.025,.030]:
                    out.append(("pullback", rise, pb, tp, None, veto, "fixed"))
            # trailing only on the economically sensible veto version
            out.append(("pullback", rise, pb, .015, DISASTER_STOP, .02, "trail005"))
            out.append(("pullback", rise, pb, .020, DISASTER_STOP, .02, "trail005"))

    # true two-peak failure
    for rise in [.003,.005]:
        for pb in [.003,.004]:
            for tp in [None,.015,.020,.025,.030]:
                out.append(("two_peak_fail", rise, pb, tp, None, .02, "fixed"))
            out.append(("two_peak_fail", rise, pb, .015, DISASTER_STOP, .02, "trail005"))
            out.append(("two_peak_fail", rise, pb, .020, DISASTER_STOP, .02, "trail005"))

    return out


def run_trade(m, sigrow, sp):
    kind,rise,pb,tp,stop,veto,exit_mode = sp
    open_px = float(m.iloc[0]["open"])

    if kind == "open":
        entry_i, sell_px, sell_time, meta = 0, open_px, m.iloc[0]["dt"].isoformat(), "open"
    elif kind == "limit":
        f = find_limit(m, open_px, rise)
        if f is None: return None
        entry_i,sell_px,sell_time,meta = f
    elif kind == "pullback":
        f = find_first_pullback(m, open_px, rise, pb, veto)
        if f is None: return None
        entry_i,sell_px,sell_time,meta = f
    elif kind == "two_peak_fail":
        f = find_two_peak_fail(m, open_px, rise, pb, veto or .02)
        if f is None: return None
        entry_i,sell_px,sell_time,meta = f
    else:
        raise ValueError(kind)

    if exit_mode == "fixed":
        buy_px,reason,buy_time = simulate_exit_fixed(m, entry_i, sell_px, tp, stop)
    else:
        buy_px,reason,buy_time = simulate_exit_trail(
            m, entry_i, sell_px, activation=tp, rebound=.005, stop=stop
        )

    day = pd.Timestamp(sigrow["date"])
    pnl,net,fees = account_pnl(sell_px,buy_px,day)
    return {
        "date":day.strftime("%Y-%m-%d"),
        "kind":kind,"rise":rise,"pullback":pb,"tp":tp,"stop":stop,
        "breakout_veto":veto,"exit_mode":exit_mode,
        "sell_time":sell_time,"sell_price_raw":sell_px,
        "buy_time":buy_time,"buy_price_raw":buy_px,"exit_reason":reason,
        "pnl":pnl,"net_ret":net,"fees":fees,"meta":meta
    }


def wilson_low(k,n,z=1.95996398454):
    if n == 0: return np.nan
    p = k/n
    den = 1+z*z/n
    center = (p+z*z/(2*n))/den
    half = z*math.sqrt((p*(1-p)+z*z/(4*n))/n)/den
    return center-half


def max_losing_streak(vals):
    best=cur=0
    for x in vals:
        if x <= 0:
            cur += 1
            best=max(best,cur)
        else:
            cur=0
    return best


def summarize(trades, signals, label):
    rows=[]
    tmp=trades.copy()
    for c in ["pullback","tp","stop","breakout_veto"]:
        tmp[c]=tmp[c].fillna(-1.0)

    groups=["kind","rise","pullback","tp","stop","breakout_veto","exit_mode"]
    for keys,g in tmp.groupby(groups,dropna=False):
        kind,rise,pb,tp,stop,veto,exit_mode=keys
        g=g.sort_values("date")
        pnl=g["pnl"].astype(float)
        net=g["net_ret"].astype(float)
        k=int((pnl>0).sum())
        gp=pnl[pnl>0].sum()
        gl=abs(pnl[pnl<0].sum())
        rows.append({
            "window":label,
            "kind":kind,"rise":rise,
            "pullback":np.nan if pb<0 else pb,
            "tp":np.nan if tp<0 else tp,
            "stop":np.nan if stop<0 else stop,
            "breakout_veto":np.nan if veto<0 else veto,
            "exit_mode":exit_mode,
            "signals":len(signals),
            "executed":len(g),
            "execution_rate":len(g)/len(signals) if len(signals) else np.nan,
            "net_win_rate":k/len(g),
            "win_wilson_low95":wilson_low(k,len(g)),
            "avg_net_per_trade":net.mean(),
            "median_net_per_trade":net.median(),
            "avg_net_per_signal":net.sum()/len(signals) if len(signals) else np.nan,
            "total_pnl_1000":pnl.sum(),
            "pf":gp/gl if gl>0 else np.inf,
            "worst_pnl_1000":pnl.min(),
            "max_losing_streak":max_losing_streak(pnl.tolist()),
            "tp_count":int((g["exit_reason"]=="tp").sum()),
            "trail_count":int(g["exit_reason"].astype(str).str.contains("trail").sum()),
            "stop_count":int((g["exit_reason"]=="stop").sum()),
        })
    return pd.DataFrame(rows)


def pct(x):
    return "" if pd.isna(x) else f"{100*x:.2f}%"


def make_report(summary, signals, qc, end):
    modern=summary[summary["window"]=="modern_2024plus"].copy()
    recent=summary[summary["window"]=="recent_2025plus"].copy()

    # robustness table: merge modern + recent by exact strategy key
    keys=["kind","rise","pullback","tp","stop","breakout_veto","exit_mode"]
    m=modern.copy(); r=recent.copy()
    m=m.rename(columns={c:"m_"+c for c in [
        "executed","execution_rate","net_win_rate","avg_net_per_trade",
        "avg_net_per_signal","pf","worst_pnl_1000","total_pnl_1000"
    ]})
    r=r.rename(columns={c:"r_"+c for c in [
        "executed","execution_rate","net_win_rate","avg_net_per_trade",
        "avg_net_per_signal","pf","worst_pnl_1000","total_pnl_1000"
    ]})
    rb=m.merge(r,on=keys,how="inner")
    rb["robust_ok"]=(
        (rb["m_executed"]>=12)&(rb["r_executed"]>=8)&
        (rb["m_avg_net_per_trade"]>0)&(rb["r_avg_net_per_trade"]>0)&
        (rb["m_pf"]>1.2)&(rb["r_pf"]>1.2)
    )
    rb=rb.sort_values(
        ["robust_ok","r_avg_net_per_signal","m_avg_net_per_signal"],
        ascending=[False,False,False]
    )

    q=qc.copy()
    q["date"]=pd.to_datetime(q["date"])
    q24=q[q["date"]>=pd.Timestamp("2024-01-01")]

    lines=[
        "# 工业富联601138｜RA-D1-V × 5分钟执行研究 V2.1",
        "",
        f"- 截止：{end}",
        f"- 2024+ 候选信号：{len(signals[signals['date']>=pd.Timestamp('2024-01-01')])}",
        f"- 2025+ 候选信号：{len(signals[signals['date']>=pd.Timestamp('2025-01-01')])}",
        f"- 2024+ QC通过：{int(q24['qc_ok'].sum())}/{len(q24)}",
        f"- High/Low warning：{int(q24['reason'].astype(str).str.contains('extreme_warning').sum())}",
        "",
        "## 第一优先：跨窗口稳健候选",
        "",
        "|策略|rise|pb|exit|tp/trigger|veto|N24+|净胜率24+|均净/笔24+|PF24+|N25+|净胜率25+|均净/笔25+|PF25+|稳健门禁|",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|"
    ]
    for _,x in rb.head(25).iterrows():
        pfm="∞" if math.isinf(x["m_pf"]) else f"{x['m_pf']:.2f}"
        pfr="∞" if math.isinf(x["r_pf"]) else f"{x['r_pf']:.2f}"
        lines.append(
            f"|{x['kind']}|{pct(x['rise'])}|{pct(x['pullback'])}|{x['exit_mode']}|"
            f"{pct(x['tp'])}|{pct(x['breakout_veto'])}|{int(x['m_executed'])}|"
            f"{pct(x['m_net_win_rate'])}|{pct(x['m_avg_net_per_trade'])}|{pfm}|"
            f"{int(x['r_executed'])}|{pct(x['r_net_win_rate'])}|"
            f"{pct(x['r_avg_net_per_trade'])}|{pfr}|{'PASS' if x['robust_ok'] else 'NO'}|"
        )

    lines += [
        "",
        "## 判定纪律",
        "",
        "- 先看 2025+，再看2024+；不允许2024单一年份把策略“抬漂亮”。",
        "- 平均净收益/笔若不到1%，不能只用胜率包装。",
        "- N<12（2024+）或N<8（2025+）只能 Research Only。",
        "- 固定TP与 trailing 比较的核心是：能否释放大赢家，而不是单纯提高胜率。",
        "- two_peak_fail 若没有明显超过 first pullback，则淘汰复杂规则。",
        "- High/Low warning 不作为删除依据，但必须保留在QC文件中供第二数据源复核。",
        ""
    ]
    return "\n".join(lines)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--start",default="2021-01-01")
    ap.add_argument("--research-start",default="2021-07-01")
    ap.add_argument("--end",default="2026-09-10")
    ap.add_argument("--out",default="research/601138_intraday_v2_1")
    ap.add_argument("--reuse-minute-dir",default="research/601138_intraday/minute_raw")
    args=ap.parse_args()

    out=Path(args.out); out.mkdir(parents=True,exist_ok=True)
    minute_dir=Path(args.reuse_minute_dir)
    minute_dir.mkdir(parents=True,exist_ok=True)

    lg=bs.login()
    if lg.error_code!="0":
        raise RuntimeError(f"BaoStock login failed {lg.error_code} {lg.error_msg}")

    try:
        warm=(pd.Timestamp(args.start)-pd.Timedelta(days=180)).strftime("%Y-%m-%d")
        qfq=query_daily(STOCK,warm,args.end,"2")
        raw=query_daily(STOCK,warm,args.end,"3")
        idx=query_index_daily(warm,args.end)
        signals=build_signals(qfq,raw,idx,args.research_start)
        signals.to_csv(out/"signals.csv",index=False)

        qc_rows=[]; trades=[]
        all_specs=specs()

        for n,(_,sig) in enumerate(signals.iterrows(),1):
            day=pd.Timestamp(sig["date"])
            cache=minute_dir/f"{day:%Y-%m-%d}.csv"
            if cache.exists():
                m=pd.read_csv(cache)
                m["dt"]=pd.to_datetime(m["dt"])
            else:
                m=query_5m(day)
                if not m.empty:
                    m.to_csv(cache,index=False)
                time.sleep(.08)

            ok,reason=qc_minute(m,sig)
            qc_rows.append({
                "date":day.strftime("%Y-%m-%d"),"bars":len(m),
                "qc_ok":ok,"reason":reason
            })
            print(f"[{n}/{len(signals)}] {day:%Y-%m-%d} bars={len(m)} QC={ok} {reason}")
            if not ok:
                continue

            for sp in all_specs:
                tr=run_trade(m,sig,sp)
                if tr is not None:
                    trades.append(tr)

        qc=pd.DataFrame(qc_rows)
        t=pd.DataFrame(trades)
        qc.to_csv(out/"minute_qc.csv",index=False)
        t.to_csv(out/"trades.csv",index=False)

        packs=[]
        td=pd.to_datetime(t["date"])
        windows=[
            ("full",pd.Timestamp(args.research_start),None),
            ("modern_2024plus",pd.Timestamp("2024-01-01"),None),
            ("recent_2025plus",pd.Timestamp("2025-01-01"),None),
            ("year_2024",pd.Timestamp("2024-01-01"),pd.Timestamp("2024-12-31")),
            ("year_2025",pd.Timestamp("2025-01-01"),pd.Timestamp("2025-12-31")),
            ("year_2026",pd.Timestamp("2026-01-01"),pd.Timestamp("2026-12-31")),
        ]
        for label,st,en in windows:
            if en is None:
                tt=t[td>=st].copy()
                ss=signals[signals["date"]>=st].copy()
            else:
                tt=t[(td>=st)&(td<=en)].copy()
                ss=signals[(signals["date"]>=st)&(signals["date"]<=en)].copy()
            if not tt.empty and not ss.empty:
                packs.append(summarize(tt,ss,label))

        summary=pd.concat(packs,ignore_index=True)
        summary.to_csv(out/"summary.csv",index=False)
        report=make_report(summary,signals,qc,args.end)
        (out/"REPORT.md").write_text(report,encoding="utf-8")
        print(report)

    finally:
        bs.logout()


if __name__=="__main__":
    main()
