#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
工业富联 601138：RA-D1-V × 5分钟左侧卖点研究
================================================
目标：
1) 用日线（前复权）在 09:25~09:30 可知信息重建 RA-D1-V 候选日；
2) 用 BaoStock 不复权 5分钟K 真实回放盘中执行顺序；
3) 比较：
   - Open 直接卖；
   - Open 上方固定限价卖；
   - 冲高后回落确认（causal high-watermark pullback）；
   - 1.2/1.5/1.8% 提前回补；
   - 4% 灾难止损；
4) 严格扣交易成本，并输出逐笔、汇总和 Markdown 报告。

注意：
- 不使用当天 High/Low/Close 来生成 RA-D1-V 日线信号；
- 分钟执行只在信号生成后使用；
- 同一5分钟bar若止盈和止损都可能触发，按不利顺序（先止损）处理；
- BaoStock 分钟数据做 OHLC 对账，异常日不进入正式统计。
"""

from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Optional, Dict, List, Tuple

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

# 2023-08-28 起印花税减半
STAMP_OLD = 0.001
STAMP_NEW = 0.0005
STAMP_CUT_DATE = pd.Timestamp("2023-08-28")

FAST_SHOCK_VETO = 0.005   # 上证今日 Gap >= 0.5% 则 veto
DISASTER_STOP = 0.04      # 相对实际卖出价 4% 灾难止损，仅作为保险层


def _to_df(rs) -> pd.DataFrame:
    rows = []
    while (rs.error_code == "0") and rs.next():
        rows.append(rs.get_row_data())
    if rs.error_code != "0":
        raise RuntimeError(f"BaoStock error: {rs.error_code} {rs.error_msg}")
    return pd.DataFrame(rows, columns=rs.fields)


def query_daily(code: str, start: str, end: str, adjustflag: str) -> pd.DataFrame:
    fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,pctChg"
    rs = bs.query_history_k_data_plus(
        code, fields, start_date=start, end_date=end,
        frequency="d", adjustflag=adjustflag
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","preclose","volume","amount","pctChg"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def query_index_daily(start: str, end: str) -> pd.DataFrame:
    # 指数不使用分钟；这里只需要每日 Open / preclose 做 Fast Shock Veto。
    fields = "date,code,open,high,low,close,preclose,volume,amount,pctChg"
    rs = bs.query_history_k_data_plus(
        INDEX, fields, start_date=start, end_date=end,
        frequency="d", adjustflag="3"
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","preclose","volume","amount","pctChg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"])
    return df.sort_values("date").reset_index(drop=True)


def query_5m(day: pd.Timestamp) -> pd.DataFrame:
    ds = day.strftime("%Y-%m-%d")
    fields = "date,time,code,open,high,low,close,volume,amount,adjustflag"
    rs = bs.query_history_k_data_plus(
        STOCK, fields, start_date=ds, end_date=ds,
        frequency="5", adjustflag="3"
    )
    df = _to_df(rs)
    if df.empty:
        return df
    for c in ["open","high","low","close","volume","amount"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    # BaoStock time: YYYYMMDDHHMMSSsss，表示 bar 结束时间
    df["dt"] = pd.to_datetime(df["time"].str.slice(0, 14), format="%Y%m%d%H%M%S", errors="coerce")
    df = df.dropna(subset=["dt","open","high","low","close"]).sort_values("dt").reset_index(drop=True)
    return df


def build_signals(qfq: pd.DataFrame, raw: pd.DataFrame, index: pd.DataFrame,
                  research_start: str) -> pd.DataFrame:
    d = qfq.copy()
    d["ma5"] = d["close"].rolling(5).mean()
    d["ma20"] = d["close"].rolling(20).mean()
    d["ma60"] = d["close"].rolling(60).mean()
    d["ma20_prev"] = d["ma20"].shift(1)
    d["r20"] = d["close"] / d["close"].shift(20) - 1

    # 所有阶段变量在交易日 t 使用 t-1 完整日线。
    d["prev_open"] = d["open"].shift(1)
    d["prev_close"] = d["close"].shift(1)
    d["prev_ma5"] = d["ma5"].shift(1)
    d["prev_ma20"] = d["ma20"].shift(1)
    d["prev_ma60"] = d["ma60"].shift(1)
    d["prev_ma20_prev"] = d["ma20_prev"].shift(1)
    d["prev_r20"] = d["r20"].shift(1)

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

    raw_cols = raw[["date","open","high","low","close"]].rename(columns={
        "open":"raw_open","high":"raw_high","low":"raw_low","close":"raw_close"
    })
    d = d.merge(raw_cols, on="date", how="left")

    d["fast_shock_ok"] = d["sh_gap"] < FAST_SHOCK_VETO
    d["signal"] = d["D"] & d["C1_prev_up"] & d["C4_open_above_ma5"] & d["fast_shock_ok"]
    out = d[(d["date"] >= pd.Timestamp(research_start)) & d["signal"]].copy()
    keep = [
        "date","open","prev_close","prev_ma5","prev_ma20","prev_ma60","prev_r20",
        "sh_gap","raw_open","raw_high","raw_low","raw_close"
    ]
    return out[keep].reset_index(drop=True)


def qc_minute(day_df: pd.DataFrame, daily_row: pd.Series, tol: float = 0.03) -> Tuple[bool, str]:
    if day_df.empty:
        return False, "empty"
    # 正常A股全天5分钟应约48根。允许少量供应商差异，但低于46根直接剔除。
    if len(day_df) < 46:
        return False, f"too_few_bars:{len(day_df)}"
    agg = {
        "open": float(day_df.iloc[0]["open"]),
        "high": float(day_df["high"].max()),
        "low": float(day_df["low"].min()),
        "close": float(day_df.iloc[-1]["close"]),
    }
    ref = {
        "open": float(daily_row["raw_open"]),
        "high": float(daily_row["raw_high"]),
        "low": float(daily_row["raw_low"]),
        "close": float(daily_row["raw_close"]),
    }
    bad = [k for k in agg if abs(agg[k] - ref[k]) > tol]
    if bad:
        return False, "ohlc_mismatch:" + ",".join(f"{k}({agg[k]:.3f}!={ref[k]:.3f})" for k in bad)
    return True, "ok"


def commission(amount: float) -> float:
    return max(MIN_COMMISSION, amount * COMMISSION_RATE)


def account_pnl(sell_price_raw: float, buy_price_raw: float, day: pd.Timestamp) -> Dict[str, float]:
    # 保守滑点
    sell_px = sell_price_raw * (1 - SLIPPAGE)
    buy_px = buy_price_raw * (1 + SLIPPAGE)
    sell_amt = sell_px * SHARES
    buy_amt = buy_px * SHARES
    comm = commission(sell_amt) + commission(buy_amt)
    transfer = (sell_amt + buy_amt) * TRANSFER_RATE
    stamp_rate = STAMP_OLD if day < STAMP_CUT_DATE else STAMP_NEW
    stamp = sell_amt * stamp_rate
    pnl = sell_amt - buy_amt - comm - transfer - stamp
    return {
        "sell_exec": sell_px, "buy_exec": buy_px,
        "pnl": pnl, "net_ret": pnl / (sell_price_raw * SHARES),
        "fees": comm + transfer + stamp
    }


def find_entry_limit(df: pd.DataFrame, day_open: float, rise: float) -> Optional[Tuple[int,float,str]]:
    target = day_open * (1 + rise)
    hit = np.flatnonzero(df["high"].to_numpy() >= target)
    if len(hit) == 0:
        return None
    i = int(hit[0])
    return i, target, df.iloc[i]["dt"].isoformat()


def find_entry_pullback(df: pd.DataFrame, day_open: float, min_rise: float,
                        pullback: float, breakout_veto: Optional[float]) -> Optional[Tuple[int,float,str,str]]:
    """
    真正因果的左侧确认代理：
    1) 先看到 running_high >= Open*(1+min_rise)
    2) 再等待5分钟收盘价从 running_high 回落 pullback
    3) 若确认前直接冲到 Open*(1+breakout_veto)，取消反T
    卖出价用确认bar收盘价，不使用未来bar。
    """
    running_high = -np.inf
    armed = False
    for i, r in df.iterrows():
        running_high = max(running_high, float(r["high"]))
        if running_high >= day_open * (1 + min_rise):
            armed = True
        if armed and breakout_veto is not None and running_high >= day_open * (1 + breakout_veto):
            return None
        if armed and float(r["close"]) <= running_high * (1 - pullback):
            return int(i), float(r["close"]), r["dt"].isoformat(), f"runHigh={running_high:.3f}"
    return None


def simulate_exit(df: pd.DataFrame, entry_i: int, sell_price: float,
                  tp: Optional[float], stop: Optional[float]) -> Tuple[float,str,str,bool]:
    """
    entry_i 之后的 bar 才允许触发买回。
    同一bar同时触发 stop/tp：按不利假设 stop 先发生。
    """
    after = df.iloc[entry_i+1:].copy()
    if after.empty:
        r = df.iloc[-1]
        return float(r["close"]), "close", r["dt"].isoformat(), False

    for _, r in after.iterrows():
        stop_hit = stop is not None and float(r["high"]) >= sell_price * (1 + stop)
        tp_hit = tp is not None and float(r["low"]) <= sell_price * (1 - tp)
        if stop_hit:
            return sell_price * (1 + stop), "stop", r["dt"].isoformat(), bool(tp_hit)
        if tp_hit:
            return sell_price * (1 - tp), "tp", r["dt"].isoformat(), False
    r = df.iloc[-1]
    return float(r["close"]), "close", r["dt"].isoformat(), False


def strategy_specs():
    specs = []
    # 1) 开盘卖基线
    for tp in [None, 0.012, 0.015, 0.018]:
        specs.append(("open", 0.0, None, tp, None, None))

    # 2) 固定限价卖：重点验证 0.2~0.5%，不追求精确最优点
    for rise in [0.002, 0.003, 0.004, 0.005]:
        for tp in [None, 0.012, 0.015, 0.018]:
            specs.append(("limit", rise, None, tp, None, None))

    # 3) 冲高后回落确认：真正因果的左侧确认
    for rise in [0.003, 0.005, 0.008]:
        for pb in [0.002, 0.003, 0.004, 0.005]:
            for tp in [None, 0.015]:
                specs.append(("pullback", rise, pb, tp, None, None))
                # 同一结构 + 2% Open 加速突破 veto
                specs.append(("pullback", rise, pb, tp, None, 0.02))

    # 4) 4%灾难止损只做保险敏感性，不作为Alpha优化
    for rise in [0.003, 0.005]:
        specs.append(("limit", rise, None, 0.015, DISASTER_STOP, None))
    return specs


def run_one(day_df: pd.DataFrame, sigrow: pd.Series, spec) -> Optional[Dict]:
    kind, rise, pb, tp, stop, breakout_veto = spec
    day_open = float(day_df.iloc[0]["open"])

    if kind == "open":
        entry_i = 0
        sell_price = day_open
        sell_time = day_df.iloc[0]["dt"].isoformat()
        meta = "open"
    elif kind == "limit":
        found = find_entry_limit(day_df, day_open, rise)
        if found is None:
            return None
        entry_i, sell_price, sell_time = found
        meta = "limit"
    elif kind == "pullback":
        found = find_entry_pullback(day_df, day_open, rise, pb, breakout_veto)
        if found is None:
            return None
        entry_i, sell_price, sell_time, meta = found
    else:
        raise ValueError(kind)

    buy_price, exit_reason, buy_time, ambiguous = simulate_exit(day_df, entry_i, sell_price, tp, stop)
    acct = account_pnl(sell_price, buy_price, pd.Timestamp(sigrow["date"]))
    return {
        "date": pd.Timestamp(sigrow["date"]).strftime("%Y-%m-%d"),
        "kind": kind,
        "rise": rise,
        "pullback": pb,
        "tp": tp,
        "stop": stop,
        "breakout_veto": breakout_veto,
        "sell_time": sell_time,
        "sell_price_raw": sell_price,
        "buy_time": buy_time,
        "buy_price_raw": buy_price,
        "exit_reason": exit_reason,
        "same_bar_stop_tp_ambiguous": ambiguous,
        "pnl": acct["pnl"],
        "net_ret": acct["net_ret"],
        "fees": acct["fees"],
        "sh_gap": float(sigrow["sh_gap"]),
        "meta": meta,
    }


def max_losing_streak(pnls: List[float]) -> int:
    best = cur = 0
    for x in pnls:
        if x <= 0:
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def summarize(trades: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    rows = []
    group_cols = ["kind","rise","pullback","tp","stop","breakout_veto"]
    # pandas groupby 默认丢NA，先用 sentinel
    tmp = trades.copy()
    for c in ["pullback","tp","stop","breakout_veto"]:
        tmp[c] = tmp[c].fillna(-1.0)

    total_signals = len(signals)
    for keys, g in tmp.groupby(group_cols, dropna=False):
        g = g.sort_values("date")
        kind,rise,pb,tp,stop,bv = keys
        pnl = g["pnl"].astype(float)
        net = g["net_ret"].astype(float)
        wins = pnl[pnl > 0].sum()
        losses = abs(pnl[pnl < 0].sum())
        rows.append({
            "kind": kind,
            "rise": rise,
            "pullback": None if pb < 0 else pb,
            "tp": None if tp < 0 else tp,
            "stop": None if stop < 0 else stop,
            "breakout_veto": None if bv < 0 else bv,
            "signals": total_signals,
            "executed": len(g),
            "execution_rate": len(g)/total_signals if total_signals else np.nan,
            "net_win_rate": (pnl > 0).mean(),
            "avg_net_per_trade": net.mean(),
            "avg_net_per_signal": net.sum()/total_signals if total_signals else np.nan,
            "total_pnl_1000": pnl.sum(),
            "pf": wins/losses if losses > 0 else np.inf,
            "worst_pnl_1000": pnl.min(),
            "max_losing_streak": max_losing_streak(pnl.tolist()),
            "tp_count": int((g["exit_reason"]=="tp").sum()),
            "stop_count": int((g["exit_reason"]=="stop").sum()),
            "ambiguous_bar_count": int(g["same_bar_stop_tp_ambiguous"].sum()),
        })
    return pd.DataFrame(rows)


def format_pct(x):
    if pd.isna(x): return ""
    return f"{100*x:.2f}%"


def build_report(summary: pd.DataFrame, signals: pd.DataFrame, qc: pd.DataFrame,
                 start: str, end: str) -> str:
    s = summary.copy()
    # 主排序：机会级净收益 -> PF -> 执行样本；避免只优化“成交后的单笔收益”
    sr = s.sort_values(["avg_net_per_signal","pf","executed"], ascending=[False,False,False])

    lines = [
        "# 工业富联 601138｜RA-D1-V × 5分钟左侧卖点研究",
        "",
        f"- 研究区间：{start} ～ {end}",
        f"- RA-D1-V 候选信号：{len(signals)}",
        f"- 5分钟数据 QC 通过：{int((qc['qc_ok']==True).sum()) if len(qc) else 0}",
        f"- QC 未通过：{int((qc['qc_ok']!=True).sum()) if len(qc) else 0}",
        "- 成本：佣金万1.354(最低5元)、沪市过户费0.001%双边、印花税历史分段、双边0.05%滑点",
        "",
        "## Top 20（按每个候选信号的净收益贡献排序）",
        "",
        "|kind|rise|pullback|tp|stop|breakout veto|N|成交率|净胜率|平均净收益/成交|平均净收益/信号|PF|1000股累计PnL|最差单笔|",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for _, r in sr.head(20).iterrows():
        def p(v):
            return "" if pd.isna(v) else f"{100*v:.2f}%"
        pf = "∞" if math.isinf(float(r["pf"])) else f"{r['pf']:.2f}"
        lines.append(
            f"|{r['kind']}|{p(r['rise'])}|{p(r['pullback'])}|{p(r['tp'])}|{p(r['stop'])}|"
            f"{p(r['breakout_veto'])}|{int(r['executed'])}|{format_pct(r['execution_rate'])}|"
            f"{format_pct(r['net_win_rate'])}|{format_pct(r['avg_net_per_trade'])}|"
            f"{format_pct(r['avg_net_per_signal'])}|{pf}|{r['total_pnl_1000']:.0f}|{r['worst_pnl_1000']:.0f}|"
        )

    lines += [
        "",
        "## 解释规则",
        "",
        "1. `open`：第一根5分钟bar开盘卖。",
        "2. `limit`：仅当盘中先触达 `Open*(1+rise)` 才成交；未触达则当天不做。",
        "3. `pullback`：先达到最小冲高幅度，再等5分钟收盘价从当日running high回落指定比例，按确认bar收盘卖；整个过程只用当时已出现数据。",
        "4. `breakout_veto=2%`：若回落确认前直接加速到 Open+2%，取消反T，不把它做成事后硬止损。",
        "5. TP/Stop 从实际卖出后的下一根5分钟bar开始判断；同bar双触发按止损先发生处理。",
        "",
        "## 定版纪律",
        "",
        "- 不选单点最优参数，优先选择相邻阈值表现稳定的平台。",
        "- 现代窗口优先；2021~2023只做压力测试。",
        "- 单笔平均收益不是唯一目标：同时看 N、每个候选信号收益、PF、最差单笔和连续亏损。",
        "- 若 `pullback` 不显著优于 `limit`，就保留更简单的 `Open+0.3%~0.5%` 限价方案，不为了“形态好看”增加规则。",
        "",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default="2021-01-01")
    ap.add_argument("--research-start", default="2021-07-01")
    ap.add_argument("--end", default=pd.Timestamp.today().strftime("%Y-%m-%d"))
    ap.add_argument("--out", default="research/601138_intraday")
    ap.add_argument("--sleep", type=float, default=0.08)
    args = ap.parse_args()

    out = Path(args.out)
    minute_dir = out / "minute_raw"
    out.mkdir(parents=True, exist_ok=True)
    minute_dir.mkdir(parents=True, exist_ok=True)

    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"BaoStock login failed: {lg.error_code} {lg.error_msg}")
    try:
        # 多取一年，保证MA60/R20预热
        q_start = (pd.Timestamp(args.start) - pd.Timedelta(days=180)).strftime("%Y-%m-%d")
        qfq = query_daily(STOCK, q_start, args.end, adjustflag="2")
        raw = query_daily(STOCK, q_start, args.end, adjustflag="3")
        idx = query_index_daily(q_start, args.end)

        signals = build_signals(qfq, raw, idx, args.research_start)
        signals.to_csv(out / "signals.csv", index=False)

        all_trades = []
        qc_rows = []
        specs = strategy_specs()

        for n, (_, sig) in enumerate(signals.iterrows(), 1):
            day = pd.Timestamp(sig["date"])
            cache = minute_dir / f"{day:%Y-%m-%d}.csv"
            if cache.exists():
                m = pd.read_csv(cache)
                m["dt"] = pd.to_datetime(m["dt"])
            else:
                m = query_5m(day)
                if not m.empty:
                    m.to_csv(cache, index=False)
                time.sleep(args.sleep)

            ok, reason = qc_minute(m, sig)
            qc_rows.append({"date": day.strftime("%Y-%m-%d"), "bars": len(m), "qc_ok": ok, "reason": reason})
            print(f"[{n}/{len(signals)}] {day:%Y-%m-%d}: bars={len(m)} QC={ok} {reason}")
            if not ok:
                continue

            for spec in specs:
                tr = run_one(m, sig, spec)
                if tr is not None:
                    all_trades.append(tr)

        qc = pd.DataFrame(qc_rows)
        qc.to_csv(out / "minute_qc.csv", index=False)
        trades = pd.DataFrame(all_trades)
        trades.to_csv(out / "trades.csv", index=False)

        if trades.empty:
            raise RuntimeError("No executable trades generated. Check BaoStock minute coverage/QC.")

        # 输出全历史、现代、近期三套汇总
        packs = []
        for label, start in [
            ("full", pd.Timestamp(args.research_start)),
            ("modern_2024plus", pd.Timestamp("2024-01-01")),
            ("recent_2025plus", pd.Timestamp("2025-01-01")),
        ]:
            t = trades[pd.to_datetime(trades["date"]) >= start].copy()
            sg = signals[signals["date"] >= start].copy()
            if t.empty or sg.empty:
                continue
            sm = summarize(t, sg)
            sm.insert(0, "window", label)
            packs.append(sm)

        summary = pd.concat(packs, ignore_index=True)
        summary.to_csv(out / "summary.csv", index=False)

        modern = summary[summary["window"]=="modern_2024plus"].drop(columns=["window"])
        modern_signals = signals[signals["date"] >= pd.Timestamp("2024-01-01")]
        report = build_report(modern, modern_signals, qc, "2024-01-01", args.end)
        (out / "REPORT.md").write_text(report, encoding="utf-8")

        print("\n=== TOP modern ===")
        cols = ["kind","rise","pullback","tp","stop","breakout_veto","executed",
                "execution_rate","net_win_rate","avg_net_per_trade","avg_net_per_signal",
                "pf","total_pnl_1000","worst_pnl_1000"]
        print(modern.sort_values(["avg_net_per_signal","pf"], ascending=False)[cols].head(20).to_string(index=False))
        print(f"\nOutputs: {out.resolve()}")

    finally:
        bs.logout()


if __name__ == "__main__":
    main()
