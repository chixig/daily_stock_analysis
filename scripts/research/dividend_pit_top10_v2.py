#!/usr/bin/env python3
"""
A股红利核心股 PIT 动态 Top10 V2.0 — Industry Routed

目标：修复 V1 的两个结构性问题：
1) 全行业共用一套 Quality/Value/Dividend 公式导致周期股在利润峰值被误判；
2) 银行没有接入已经验证过的 BankQV / BankCore 专模。

V2 冻结原则（在看到 V2 回测结果前写死）：
- 2012–2025 逐年 PIT；2026 仅做代表性检查。
- 银行：BankQV（65% Quality + 35% Valuation），使用银行专属 F10 字段。
- 公用事业 / 交通基础设施 / 周期 / 稳定资产 / 普通稳定行业分路由评分。
- 周期股使用“正常化 PE = 当前 PE × 当前利润/5Y中位利润”，并限制集中度。
- 不根据回测收益反向调整权重。
- 2012–2017 由 BaoStock 2007+ 年报与当日 PE/PB 补齐；2018+ 继续使用 V1 的严格 PIT Tushare 快照。

注意：行业标签来自数据包的静态行业字段，仅用于宽行业路由；若历史行业变更，存在轻微元数据回看风险。
因此 V2 仍是可复现研究模型，不宣称等于人工尽调后的冻结 Top10。
"""
from __future__ import annotations

import importlib.util
import inspect
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Import the already-audited V1 data/return engine from the same repository.
# OUT_DIR is set by the V2 workflow before this import, so V1 helpers write into
# the V2 run directory rather than the V1 directory.
# -----------------------------------------------------------------------------
HERE = Path(__file__).resolve().parent
V1_PATH = HERE / "dividend_pit_top10_v1.py"
spec = importlib.util.spec_from_file_location("pit_v1", V1_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import {V1_PATH}")
v1 = importlib.util.module_from_spec(spec)
sys.modules["pit_v1"] = v1
spec.loader.exec_module(v1)

ROOT = Path(os.environ.get("OUT_DIR", "_dividend_pit_top10_v2"))
OUT = ROOT / "out"
REPORTS = ROOT / "reports"
CACHE = ROOT / "cache"
for p in [OUT, REPORTS, CACHE]:
    p.mkdir(parents=True, exist_ok=True)

START_YEAR = 2012
END_BACKTEST_YEAR = 2025
END_SELECTION_YEAR = 2026
TOPN = 10
TOPN20 = 20
HARD_BENCHMARK_CAGR = 0.121
MIN_LISTED_YEARS = 3.0
MIN_DY = 1.5
MIN_ROE = 5.0
LIQ_KEEP = 0.80
EARLY_LAST_YEAR = 2017

OFFICIAL_2026 = v1.OFFICIAL_2026
BANK_CODES = v1.BANK_CODES

ROUTE_CAPS_10 = {
    "BANK": 3,
    "UTILITY": 3,
    "TRANSPORT": 3,
    "CYCLICAL": 1,
    "OTHER_FIN": 1,
    "ASSET_STABLE": 2,
    "STABLE": 6,
}
ROUTE_CAPS_20 = {
    "BANK": 6,
    "UTILITY": 5,
    "TRANSPORT": 5,
    "CYCLICAL": 3,
    "OTHER_FIN": 2,
    "ASSET_STABLE": 3,
    "STABLE": 12,
}


def log(*a):
    print(*a, flush=True)


def pct_rank(s: pd.Series, higher=True):
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().sum() <= 1:
        return pd.Series(0.5, index=s.index)
    r = x.rank(pct=True, method="average")
    if higher:
        return r
    return 1.0 - r + 1.0 / x.notna().sum()


def winsor(s: pd.Series, lo=.05, hi=.95):
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().sum() < 10:
        return x
    qlo, qhi = x.quantile([lo, hi])
    return x.clip(qlo, qhi)


def cagr3(vals: pd.Series):
    z = pd.to_numeric(vals, errors="coerce").dropna()
    if len(z) < 3 or z.iloc[0] <= 0 or z.iloc[-1] <= 0:
        return np.nan
    return float((z.iloc[-1] / z.iloc[0]) ** (1 / (len(z) - 1)) - 1)


def normalize_ratio(v):
    v = pd.to_numeric(pd.Series([v]), errors="coerce").iloc[0]
    if pd.isna(v):
        return np.nan
    # BaoStock ratios such as ROE/liabilityToAsset/CFOToNP are normally decimals.
    return float(v)


def load_metadata(paths) -> pd.DataFrame:
    basic = pd.read_parquet(paths["parquet/tushare_stock_basic.parquet"])
    basic = v1.normalize_code_col(basic)
    name_col = next((c for c in ["name", "NAME", "fullname", "symbol"] if c in basic.columns), None)
    industry_col = next((c for c in ["industry", "INDUSTRY", "industry_name"] if c in basic.columns), None)
    if industry_col is None:
        raise RuntimeError(
            "V2 requires an industry column in tushare_stock_basic.parquet; "
            "refusing to silently collapse Industry Routing back to the V1 all-industry model."
        )
    out = pd.DataFrame({"code6": basic["code6"]})
    out["name"] = basic[name_col].astype("string") if name_col else pd.NA
    out["industry"] = basic[industry_col].astype("string") if industry_col else pd.NA
    return out.drop_duplicates("code6", keep="last")


def route_from_metadata(row) -> str:
    code = str(row.get("code6", ""))
    if code in BANK_CODES:
        return "BANK"
    industry = str(row.get("industry", "") or "")
    name = str(row.get("name", "") or "")
    text = industry + " " + name

    utility_kw = ["水务", "供水", "污水", "环保", "电力", "燃气", "供热", "公用事业"]
    transport_kw = ["港口", "高速公路", "机场", "铁路", "公交", "仓储", "物流"]
    cyclical_kw = ["煤炭", "钢铁", "有色", "石油", "石化", "化工", "化纤", "水泥", "建材", "采掘", "矿业", "航运"]
    realestate_kw = ["房地产", "地产", "园区开发", "商业物业"]
    other_fin_kw = ["证券", "保险", "多元金融", "金融服务", "信托"]

    if any(k in text for k in utility_kw):
        return "UTILITY"
    if any(k in text for k in transport_kw):
        return "TRANSPORT"
    if any(k in text for k in other_fin_kw):
        return "OTHER_FIN"
    if any(k in text for k in realestate_kw):
        return "REAL_ESTATE_PENDING"
    if any(k in text for k in cyclical_kw):
        return "CYCLICAL"
    return "STABLE"


def add_route(fin_market: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    x = fin_market.merge(meta, on="code6", how="left")
    x["route"] = [route_from_metadata(r) for _, r in x.iterrows()]
    # Distinguish genuinely stable rental/asset operators from leveraged developers
    # without naming any specific company. This avoids treating all real estate alike.
    is_re = x["route"].eq("REAL_ESTATE_PENDING")
    stable_asset = (
        is_re
        & x["debt_assets_latest"].lt(0.60)
        & x["roe_std_5y"].lt(4.0)
        & x["cfo_ni_median_3y"].gt(0.5)
    )
    x.loc[stable_asset, "route"] = "ASSET_STABLE"
    x.loc[is_re & ~stable_asset, "route"] = "CYCLICAL"
    return x


# -----------------------------------------------------------------------------
# 2012-2017 strict PIT backfill via BaoStock.
# -----------------------------------------------------------------------------
def bs_collect(rs):
    rows = []
    if rs.error_code != "0":
        raise RuntimeError(f"{rs.error_code}: {rs.error_msg}")
    while rs.next():
        rows.append(rs.get_row_data())
    return pd.DataFrame(rows, columns=rs.fields)


def bs_code(code6):
    return ("sh." if str(code6).startswith("6") else "sz.") + str(code6)


def early_candidate_plan(market: pd.DataFrame) -> Dict[int, List[str]]:
    plan = {}
    for y in range(START_YEAR, EARLY_LAST_YEAR + 1):
        m = market[market["year"].eq(y)].copy()
        if m.empty:
            plan[y] = []
            continue
        amt_cut = m["avg_amount_252"].quantile(1.0 - LIQ_KEEP)
        z = m[
            m["listed_years"].ge(MIN_LISTED_YEARS)
            & m["three_year_dividend"].fillna(False)
            & m["dy_ttm"].ge(MIN_DY)
            & m["avg_amount_252"].ge(amt_cut)
        ].copy()
        # Broad by design. Financial filters are applied after PIT statements arrive.
        plan[y] = sorted(z["code6"].dropna().astype(str).unique().tolist())
        log("EARLY PLAN", y, len(plan[y]))
    return plan


def fetch_early_baostock(market: pd.DataFrame, q) -> Tuple[Dict[int, pd.DataFrame], Dict[Tuple[int, str], dict]]:
    import baostock as bs

    plan = early_candidate_plan(market)
    pair_need = set()
    signal_need = []
    for y, codes in plan.items():
        sig, _ = q.may_dates(y)
        for code in codes:
            signal_need.append((y, code, sig))
            for fy in range(y - 5, y):
                pair_need.add((code, fy))

    log("BaoStock early code-year pairs", len(pair_need), "signal valuations", len(signal_need))
    lg = bs.login()
    if lg.error_code != "0":
        raise RuntimeError(f"BaoStock login failed {lg.error_code}: {lg.error_msg}")

    annual_rows = []
    failures = []

    def retry_query(kind, code, fy):
        last = None
        for attempt in range(1, 5):
            try:
                if kind == "profit":
                    return bs_collect(bs.query_profit_data(code=bs_code(code), year=int(fy), quarter=4))
                if kind == "balance":
                    return bs_collect(bs.query_balance_data(code=bs_code(code), year=int(fy), quarter=4))
                if kind == "cash":
                    return bs_collect(bs.query_cash_flow_data(code=bs_code(code), year=int(fy), quarter=4))
            except Exception as e:
                last = e
                time.sleep(min(3, attempt))
        raise RuntimeError(last)

    for i, (code, fy) in enumerate(sorted(pair_need), 1):
        parts = {}
        for kind in ["profit", "balance", "cash"]:
            try:
                d = retry_query(kind, code, fy)
            except Exception as e:
                failures.append({"code6": code, "year": fy, "kind": kind, "error": repr(e)})
                d = pd.DataFrame()
            if not d.empty:
                d["pubDate"] = pd.to_datetime(d["pubDate"], errors="coerce")
                d["statDate"] = pd.to_datetime(d["statDate"], errors="coerce")
                d = d[d["statDate"].dt.month.eq(12) & d["statDate"].dt.day.eq(31)]
                if not d.empty:
                    d = d.sort_values("pubDate").iloc[0]
            parts[kind] = d
        p = parts["profit"]
        if isinstance(p, pd.Series):
            b = parts["balance"] if isinstance(parts["balance"], pd.Series) else pd.Series(dtype=object)
            c = parts["cash"] if isinstance(parts["cash"], pd.Series) else pd.Series(dtype=object)
            pub = p.get("pubDate", pd.NaT)
            stat = p.get("statDate", pd.NaT)
            roe = normalize_ratio(p.get("roeAvg", np.nan))
            roe_pct = roe * 100 if np.isfinite(roe) and abs(roe) <= 2 else roe
            liab = normalize_ratio(b.get("liabilityToAsset", np.nan))
            if np.isfinite(liab) and liab > 2:
                liab /= 100.0
            cfo_np = normalize_ratio(c.get("CFOToNP", np.nan))
            annual_rows.append({
                "code6": code,
                "financial_year": fy,
                "pubDate": pub,
                "statDate": stat,
                "roe_pct": roe_pct,
                "net_profit": pd.to_numeric(p.get("netProfit", np.nan), errors="coerce"),
                "revenue": pd.to_numeric(p.get("MBRevenue", p.get("operatingRevenue", np.nan)), errors="coerce"),
                "eps": pd.to_numeric(p.get("epsTTM", np.nan), errors="coerce"),
                "total_share": pd.to_numeric(p.get("totalShare", np.nan), errors="coerce"),
                "debt_assets": liab,
                "cfo_ni": cfo_np,
            })
        if i % 200 == 0:
            log("BaoStock annual", i, "/", len(pair_need), "failures", len(failures))

    ann = pd.DataFrame(annual_rows)
    ann.to_csv(OUT / "baostock_early_annual.csv.gz", index=False, compression="gzip")
    (REPORTS / "baostock_early_failures.json").write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")

    # Signal-date PE/PB from BaoStock daily history.
    val_map = {}
    for i, (y, code, sig) in enumerate(signal_need, 1):
        ds = sig.strftime("%Y-%m-%d")
        try:
            rs = bs.query_history_k_data_plus(
                bs_code(code),
                "date,code,peTTM,pbMRQ,isST",
                start_date=ds,
                end_date=ds,
                frequency="d",
                adjustflag="3",
            )
            d = bs_collect(rs)
            if not d.empty:
                r = d.iloc[-1]
                val_map[(y, code)] = {
                    "pe_ttm_bs": pd.to_numeric(r.get("peTTM", np.nan), errors="coerce"),
                    "pb_bs": pd.to_numeric(r.get("pbMRQ", np.nan), errors="coerce"),
                    "isST_bs": str(r.get("isST", "0")) == "1",
                }
        except Exception as e:
            failures.append({"code6": code, "signal_year": y, "kind": "valuation", "error": repr(e)})
        if i % 300 == 0:
            log("BaoStock valuation", i, "/", len(signal_need))

    try:
        bs.logout()
    except Exception:
        pass

    fin_by_year = {}
    for y in range(START_YEAR, EARLY_LAST_YEAR + 1):
        sig, _ = q.may_dates(y)
        codes = set(plan[y])
        sub = ann[
            ann["code6"].isin(codes)
            & ann["financial_year"].between(y - 5, y - 1)
            & ann["pubDate"].notna()
            & ann["pubDate"].le(sig)
        ].copy()
        rows = []
        for code, g in sub.groupby("code6"):
            g = g.sort_values("financial_year").drop_duplicates("financial_year", keep="first")
            latest = g[g["financial_year"].eq(y - 1)]
            if latest.empty:
                continue
            last = latest.iloc[-1]
            last3 = g.tail(3)
            profits = pd.to_numeric(g["net_profit"], errors="coerce")
            revenues = pd.to_numeric(g["revenue"], errors="coerce")
            roe = pd.to_numeric(g["roe_pct"], errors="coerce")
            median_profit = float(profits.median()) if profits.notna().any() else np.nan
            latest_profit = float(last["net_profit"]) if pd.notna(last["net_profit"]) else np.nan
            peak = latest_profit / median_profit if np.isfinite(latest_profit) and np.isfinite(median_profit) and median_profit > 0 else np.nan
            shares = float(last["total_share"]) if pd.notna(last["total_share"]) else np.nan
            rows.append({
                "code6": code,
                "fin_year_latest": int(last["financial_year"]),
                "annual_count": int(g["financial_year"].nunique()),
                "roe_median_5y": float(roe.median()) if roe.notna().any() else np.nan,
                "roe_std_5y": float(roe.std(ddof=1)) if roe.notna().sum() >= 2 else np.nan,
                "profit_cagr": cagr3(profits.tail(3)),
                "revenue_cagr": cagr3(revenues.tail(3)),
                "cfo_ni_median_3y": float(pd.to_numeric(last3["cfo_ni"], errors="coerce").median()),
                "positive_profit_3y": int((pd.to_numeric(last3["net_profit"], errors="coerce") > 0).sum()),
                "positive_cfo_3y": int((pd.to_numeric(last3["cfo_ni"], errors="coerce") > 0).sum()),
                "debt_assets_latest": float(last["debt_assets"]) if pd.notna(last["debt_assets"]) else np.nan,
                "eps_latest": float(last["eps"]) if pd.notna(last["eps"]) else np.nan,
                "shares_estimate_latest": shares,
                "equity_per_share_latest": np.nan,
                "profit_median_5y": median_profit,
                "profit_latest": latest_profit,
                "profit_peak_ratio": peak,
            })
        fin_by_year[y] = pd.DataFrame(rows, columns=[
            "code6", "fin_year_latest", "annual_count", "roe_median_5y",
            "roe_std_5y", "profit_cagr", "revenue_cagr", "cfo_ni_median_3y",
            "positive_profit_3y", "positive_cfo_3y", "debt_assets_latest",
            "eps_latest", "shares_estimate_latest", "equity_per_share_latest",
            "profit_median_5y", "profit_latest", "profit_peak_ratio",
        ])

    return fin_by_year, val_map


# -----------------------------------------------------------------------------
# 2018+ Tushare PIT snapshot augmentation for cycle normalization.
# -----------------------------------------------------------------------------
def augment_hf_snapshot(payload: dict, sig: pd.Timestamp, fin: pd.DataFrame) -> pd.DataFrame:
    if fin.empty:
        return fin
    p = payload["profit"].copy()
    target = sig.year - 1
    p = p[
        p["ann_date_n"].notna()
        & p["ann_date_n"].le(sig)
        & p["end_date_n"].dt.month.eq(12)
        & p["end_date_n"].dt.day.eq(31)
        & p["end_date_n"].dt.year.le(target)
    ].copy()
    p["fy"] = p["end_date_n"].dt.year
    p = p.sort_values(["code6", "fy", "ann_date_n"]).drop_duplicates(["code6", "fy"], keep="last")
    p = p.groupby("code6", group_keys=False).tail(5)
    rows = []
    for code, g in p.groupby("code6"):
        g = g.sort_values("fy")
        profits = pd.to_numeric(g["net_profit_n"], errors="coerce")
        latest = g[g["fy"].eq(target)]
        if latest.empty:
            continue
        lp = pd.to_numeric(latest.iloc[-1]["net_profit_n"], errors="coerce")
        mp = profits.median()
        peak = float(lp / mp) if pd.notna(lp) and pd.notna(mp) and mp > 0 else np.nan
        rows.append({"code6": code, "profit_median_5y": mp, "profit_latest": lp, "profit_peak_ratio": peak})
    extra = pd.DataFrame(rows)
    return fin.merge(extra, on="code6", how="left")


def merge_valuation(market_y: pd.DataFrame, fin_y: pd.DataFrame, val_map, year: int) -> pd.DataFrame:
    x = market_y.merge(fin_y, on="code6", how="left")
    price = pd.to_numeric(x["raw_price_signal"], errors="coerce")
    eps = pd.to_numeric(x.get("eps_latest"), errors="coerce")
    shares = pd.to_numeric(x.get("shares_estimate_latest"), errors="coerce")
    eps_book = pd.to_numeric(x.get("equity_per_share_latest"), errors="coerce")
    avg_price = pd.to_numeric(x["avg_raw_price_252"], errors="coerce")

    derived_pe = np.where((price > 0) & (eps > 0), price / eps, np.nan)
    derived_pb = np.where((price > 0) & (eps_book > 0), price / eps_book, np.nan)
    derived_mv = np.where((avg_price > 0) & (shares > 0), avg_price * shares, np.nan)

    x["pe_ttm"] = pd.to_numeric(x.get("pe_ttm"), errors="coerce")
    x["pb"] = pd.to_numeric(x.get("pb"), errors="coerce")
    x["avg_mv_252"] = pd.to_numeric(x.get("avg_mv_252"), errors="coerce")
    x["pe_ttm"] = x["pe_ttm"].where(x["pe_ttm"].gt(0), derived_pe)
    x["pb"] = x["pb"].where(x["pb"].gt(0), derived_pb)
    x["avg_mv_252"] = x["avg_mv_252"].where(x["avg_mv_252"].gt(0), derived_mv)

    # Early BaoStock valuation overrides derived proxies because it is an actual PIT PE/PB observation.
    if year <= EARLY_LAST_YEAR:
        pe_bs = []
        pb_bs = []
        isst = []
        for code in x["code6"].astype(str):
            d = val_map.get((year, code), {})
            pe_bs.append(d.get("pe_ttm_bs", np.nan))
            pb_bs.append(d.get("pb_bs", np.nan))
            isst.append(d.get("isST_bs", False))
        pe_bs = pd.Series(pe_bs, index=x.index, dtype=float)
        pb_bs = pd.Series(pb_bs, index=x.index, dtype=float)
        x["pe_ttm"] = pe_bs.where(pe_bs.gt(0), x["pe_ttm"])
        x["pb"] = pb_bs.where(pb_bs.gt(0), x["pb"])
        x["isST"] = isst
    else:
        x["isST"] = False

    x["payout_proxy"] = np.where((x["dy_ttm"] > 0) & (x["pe_ttm"] > 0), x["dy_ttm"] * x["pe_ttm"] / 100.0, np.nan)
    return x


# -----------------------------------------------------------------------------
# Bank-specific F10 / BankQV.
# -----------------------------------------------------------------------------
def fetch_bank_f10() -> pd.DataFrame:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    BASE = "https://datacenter.eastmoney.com/securities/api/data/get"
    session = requests.Session()
    retry = Retry(total=5, connect=5, read=5, backoff_factor=.8, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    headers = {
        "accept": "*/*",
        "origin": "https://emweb.securities.eastmoney.com",
        "referer": "https://emweb.securities.eastmoney.com/",
        "user-agent": "Mozilla/5.0 Chrome/130 Safari/537.36",
    }
    frames = []
    for i, code in enumerate(sorted(BANK_CODES), 1):
        ex = "SH" if code.startswith("6") else "SZ"
        params = {
            "type": "RPT_F10_FINANCE_MAINFINADATA",
            "sty": "APP_F10_MAINFINADATA",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{code}.{ex}")',
            "p": 1,
            "ps": 300,
            "sr": -1,
            "st": "REPORT_DATE",
            "source": "HSF10",
            "client": "PC",
        }
        try:
            r = session.get(BASE, params=params, headers=headers, timeout=30)
            r.raise_for_status()
            data = ((r.json().get("result") or {}).get("data") or [])
            if data:
                d = pd.DataFrame(data)
                d["code6"] = code
                frames.append(d)
        except Exception as e:
            log("BANK F10 FAIL", code, repr(e))
        if i % 10 == 0:
            log("BANK F10", i, "/", len(BANK_CODES))
        time.sleep(.08)
    if not frames:
        raise RuntimeError("No bank F10 data")
    f = pd.concat(frames, ignore_index=True, sort=False)
    for c in ["REPORT_DATE", "NOTICE_DATE", "UPDATE_DATE"]:
        if c in f.columns:
            f[c] = pd.to_datetime(f[c], errors="coerce")
    for c in ["BPS", "ROEJQ", "ZZCJLL", "BLDKBBL", "NONPERLOAN", "HXYJBCZL", "FIRST_ADEQUACY_RATIO", "NEWCAPITALADER", "NET_INTEREST_MARGIN", "LOAN_PROVISION_RATIO", "PARENTNETPROFIT"]:
        if c in f.columns:
            f[c] = pd.to_numeric(f[c], errors="coerce")
    f.to_csv(OUT / "bank_f10_v2.csv.gz", index=False, compression="gzip")
    return f


def bank_route_scores(x: pd.DataFrame, f10: pd.DataFrame, sig: pd.Timestamp) -> pd.DataFrame:
    y = sig.year
    bank_market = x[x["code6"].isin(BANK_CODES)].copy()
    rows = []
    for code, m in bank_market.groupby("code6"):
        hist = f10[
            f10["code6"].eq(code)
            & f10["REPORT_DATE"].dt.month.eq(12)
            & f10["REPORT_DATE"].dt.day.eq(31)
            & f10["REPORT_DATE"].dt.year.between(y - 5, y - 1)
            & f10["NOTICE_DATE"].notna()
            & f10["NOTICE_DATE"].le(sig)
        ].copy()
        if hist.empty:
            continue
        hist["fy"] = hist["REPORT_DATE"].dt.year
        hist = hist.sort_values(["fy", "NOTICE_DATE"]).drop_duplicates("fy", keep="first").sort_values("fy")
        latest = hist[hist["fy"].eq(y - 1)]
        if latest.empty or hist["fy"].nunique() < 3:
            continue
        last = latest.iloc[-1]
        def med(c):
            return float(pd.to_numeric(hist[c], errors="coerce").median()) if c in hist else np.nan
        def std(c):
            z = pd.to_numeric(hist[c], errors="coerce") if c in hist else pd.Series(dtype=float)
            return float(z.std(ddof=1)) if z.notna().sum() >= 2 else np.nan
        nim_trend = np.nan
        if "NET_INTEREST_MARGIN" in hist.columns:
            nh = pd.to_numeric(hist.tail(3)["NET_INTEREST_MARGIN"], errors="coerce").dropna().to_numpy(float)
            if len(nh) >= 2:
                nim_trend = float(np.polyfit(np.arange(len(nh)), nh, 1)[0])
        mr = m.iloc[0]
        bps = pd.to_numeric(last.get("BPS", np.nan), errors="coerce")
        pb = mr["raw_price_signal"] / bps if pd.notna(bps) and bps > 0 else mr.get("pb", np.nan)
        rows.append({
            **mr.to_dict(),
            "route": "BANK",
            "bank_roe": med("ROEJQ"),
            "bank_roe_std": std("ROEJQ"),
            "bank_roa": med("ZZCJLL"),
            "bank_npl": pd.to_numeric(last.get("BLDKBBL", np.nan), errors="coerce"),
            "bank_provision": pd.to_numeric(last.get("LOAN_PROVISION_RATIO", np.nan), errors="coerce"),
            "bank_cet1": pd.to_numeric(last.get("HXYJBCZL", np.nan), errors="coerce"),
            "bank_nim": pd.to_numeric(last.get("NET_INTEREST_MARGIN", np.nan), errors="coerce"),
            "bank_nim_trend": nim_trend,
            "pb": pb,
        })
    z = pd.DataFrame(rows)
    if z.empty:
        return z
    amt_cut = x["avg_amount_252"].quantile(1.0 - LIQ_KEEP)
    mv_cut = x["avg_mv_252"].quantile(1.0 - LIQ_KEEP)
    z = z[
        z["listed_years"].ge(MIN_LISTED_YEARS)
        & z["continuous_dividend_years"].ge(5)
        & z["dy_ttm"].ge(2.5)
        & z["avg_amount_252"].ge(amt_cut)
        & (z["avg_mv_252"].isna() | z["avg_mv_252"].ge(mv_cut))
        & z["pb"].gt(0)
        & (z["bank_npl"].isna() | z["bank_npl"].le(2.5))
        & (z["bank_cet1"].isna() | z["bank_cet1"].ge(7.0))
    ].copy()
    if z.empty:
        return z
    z["q_roe"] = pct_rank(z["bank_roe"], True)
    z["q_roe_stability"] = pct_rank(z["bank_roe_std"], False)
    z["q_roa"] = pct_rank(z["bank_roa"], True)
    z["q_npl"] = pct_rank(z["bank_npl"], False)
    z["q_provision"] = pct_rank(z["bank_provision"], True)
    z["q_cet1"] = pct_rank(z["bank_cet1"], True)
    z["q_nim"] = pct_rank(z["bank_nim"], True)
    z["q_nim_trend"] = pct_rank(z["bank_nim_trend"], True)
    z["QualityScore"] = z[["q_roe", "q_roe_stability", "q_roa", "q_npl", "q_provision", "q_cet1", "q_nim", "q_nim_trend"]].mean(axis=1, skipna=True)
    z["v_pb"] = pct_rank(z["pb"], False)
    z["v_dy"] = pct_rank(z["dy_ttm"], True)
    z["ValuationScore"] = z[["v_pb", "v_dy"]].mean(axis=1, skipna=True)
    z["DividendScore"] = np.nan
    z["LowVolScore"] = pct_rank(z["vol_252"], False)
    z["RouteScore"] = .65 * z["QualityScore"] + .35 * z["ValuationScore"]
    z["model_name"] = "BankQV"
    return z


# -----------------------------------------------------------------------------
# Non-bank industry-routed scoring.
# -----------------------------------------------------------------------------
def score_nonbanks(x: pd.DataFrame) -> pd.DataFrame:
    z = x[~x["code6"].isin(BANK_CODES)].copy()
    if z.empty:
        return z

    amt_cut = z["avg_amount_252"].quantile(1.0 - LIQ_KEEP)
    mv_cut = z["avg_mv_252"].quantile(1.0 - LIQ_KEEP)
    base = (
        z["listed_years"].ge(MIN_LISTED_YEARS)
        & z["three_year_dividend"].fillna(False)
        & z["dy_ttm"].ge(MIN_DY)
        & z["avg_amount_252"].ge(amt_cut)
        & z["avg_mv_252"].ge(mv_cut)
        & z["pe_ttm"].gt(0)
        & z["pb"].gt(0)
        & z["annual_count"].ge(3)
        & z["fin_year_latest"].eq(z["year"] - 1)
        & z["positive_profit_3y"].ge(3)
        & z["roe_median_5y"].ge(MIN_ROE)
        & ~z["isST"].fillna(False)
    )
    z = z[base].copy()
    if z.empty:
        return z

    # Universal veto. OTHER_FIN is exempt from leverage/CFO because statements are structurally different.
    normal = ~z["route"].eq("OTHER_FIN")
    z = z[~(normal & z["debt_assets_latest"].gt(.85))].copy()
    stable_like = z["route"].isin(["STABLE", "UTILITY", "TRANSPORT", "ASSET_STABLE"])
    z = z[~(stable_like & z["positive_cfo_3y"].lt(2))].copy()

    all_scored = []
    for route, g in z.groupby("route"):
        if route == "REAL_ESTATE_PENDING":
            continue
        g = g.copy()
        g["profit_cagr_w"] = winsor(g["profit_cagr"])
        g["revenue_cagr_w"] = winsor(g["revenue_cagr"])
        g["cfo_ni_w"] = winsor(g["cfo_ni_median_3y"])
        g["q_roe"] = pct_rank(g["roe_median_5y"], True)
        g["q_stability"] = pct_rank(g["roe_std_5y"], False)
        g["q_profit"] = pct_rank(g["profit_cagr_w"], True)
        g["q_revenue"] = pct_rank(g["revenue_cagr_w"], True)
        g["q_cash"] = pct_rank(g["cfo_ni_w"], True)
        g["q_debt"] = pct_rank(g["debt_assets_latest"], False)
        g["v_pe"] = pct_rank(g["pe_ttm"], False)
        g["v_pb"] = pct_rank(g["pb"], False)
        g["v_dy"] = pct_rank(g["dy_ttm"], True)
        g["d_years"] = pct_rank(g["continuous_dividend_years"], True)
        g["d_growth"] = pct_rank(winsor(g["dps_cagr_5y"]), True)
        g["d_stability"] = pct_rank(g["dps_max_cut_5y"], True)
        g["DividendScore"] = g[["d_years", "d_growth", "d_stability"]].mean(axis=1, skipna=True)
        g["LowVolScore"] = pct_rank(g["vol_252"], False)

        if route == "CYCLICAL":
            peak = pd.to_numeric(g["profit_peak_ratio"], errors="coerce").clip(.20, 5.0)
            g["norm_pe"] = g["pe_ttm"] * peak
            # Favour earnings close to normal, not a temporary peak or collapse.
            g["cycle_normality"] = -np.abs(np.log(peak))
            g["q_cycle_normality"] = pct_rank(g["cycle_normality"], True)
            g["v_norm_pe"] = pct_rank(g["norm_pe"], False)
            g["QualityScore"] = g[["q_stability", "q_cash", "q_debt", "q_cycle_normality"]].mean(axis=1, skipna=True)
            g["ValuationScore"] = g[["v_norm_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)
            g["RouteScore"] = .30*g["QualityScore"] + .30*g["ValuationScore"] + .20*g["DividendScore"] + .20*g["LowVolScore"]
            g["model_name"] = "CyclicalNormalized"
        elif route in ["UTILITY", "TRANSPORT"]:
            g["QualityScore"] = g[["q_roe", "q_stability", "q_cash", "q_debt"]].mean(axis=1, skipna=True)
            g["ValuationScore"] = g[["v_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)
            g["RouteScore"] = .40*g["QualityScore"] + .25*g["ValuationScore"] + .25*g["DividendScore"] + .10*g["LowVolScore"]
            g["model_name"] = "UtilityStable" if route == "UTILITY" else "TransportStable"
        elif route == "ASSET_STABLE":
            g["QualityScore"] = g[["q_roe", "q_stability", "q_cash", "q_debt"]].mean(axis=1, skipna=True)
            g["ValuationScore"] = g[["v_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)
            g["RouteScore"] = .45*g["QualityScore"] + .25*g["ValuationScore"] + .25*g["DividendScore"] + .05*g["LowVolScore"]
            g["model_name"] = "StableAsset"
        elif route == "OTHER_FIN":
            g["QualityScore"] = g[["q_roe", "q_stability", "q_profit"]].mean(axis=1, skipna=True)
            g["ValuationScore"] = g[["v_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)
            g["RouteScore"] = .40*g["QualityScore"] + .30*g["ValuationScore"] + .20*g["DividendScore"] + .10*g["LowVolScore"]
            g["model_name"] = "OtherFinancial"
        else:
            g["QualityScore"] = g[["q_roe", "q_stability", "q_profit", "q_revenue", "q_cash"]].mean(axis=1, skipna=True)
            g["ValuationScore"] = g[["v_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)
            g["RouteScore"] = .50*g["QualityScore"] + .25*g["ValuationScore"] + .20*g["DividendScore"] + .05*g["LowVolScore"]
            g["model_name"] = "StableQualityValue"
        # Shrink tiny-route percentile extremes toward neutral so a route with only
        # a handful of eligible names does not mechanically dominate the global Top10.
        shrink = min(1.0, math.sqrt(len(g) / 20.0))
        g["RouteScoreRaw"] = g["RouteScore"]
        g["RouteScore"] = 0.5 + (g["RouteScore"] - 0.5) * shrink
        all_scored.append(g)
    return pd.concat(all_scored, ignore_index=True) if all_scored else pd.DataFrame()


def select_routed(scored: pd.DataFrame, n: int) -> pd.DataFrame:
    if scored.empty:
        return scored
    caps = ROUTE_CAPS_10 if n == 10 else ROUTE_CAPS_20
    z = scored.sort_values(["RouteScore", "QualityScore", "dy_ttm"], ascending=False).drop_duplicates("code6", keep="first")
    chosen = []
    counts = {k: 0 for k in caps}
    for r in z.itertuples(index=False):
        route = str(r.route)
        cap = caps.get(route, n)
        if counts.get(route, 0) >= cap:
            continue
        chosen.append(r.code6)
        counts[route] = counts.get(route, 0) + 1
        if len(chosen) >= n:
            break
    return z[z["code6"].isin(chosen)].sort_values(["RouteScore", "QualityScore"], ascending=False).head(n)


def call_lowvol(my, fin):
    sig = inspect.signature(v1.lowvol_proxy_year)
    if len(sig.parameters) >= 2:
        return v1.lowvol_proxy_year(my, fin)
    return v1.lowvol_proxy_year(my)


def build_year_scored(market, payload, early_fin, val_map, meta, bank_f10, q, y):
    sig, _ = q.may_dates(y)
    my = market[market["year"].eq(y)].copy()
    if y <= EARLY_LAST_YEAR:
        fin = early_fin.get(y, pd.DataFrame()).copy()
    else:
        fin = v1.annual_financial_snapshot(payload, sig)
        fin = augment_hf_snapshot(payload, sig, fin)
    x = merge_valuation(my, fin, val_map, y)
    x = add_route(x, meta)
    banks = bank_route_scores(x, bank_f10, sig)
    nonbanks = score_nonbanks(x)
    scored = pd.concat([banks, nonbanks], ignore_index=True, sort=False) if not banks.empty or not nonbanks.empty else pd.DataFrame()
    return x, scored, fin


def main():
    paths, qextract = v1.download_inputs()
    qroot = v1.locate_qlib(qextract)
    q = v1.QlibStore.create(qroot)
    payload, _ = v1.load_financials(paths)
    meta = load_metadata(paths)
    div_groups = v1.load_dividend_groups(paths)
    market = v1.build_market_panel(q, div_groups)
    market = v1.add_dividend_history(market)

    # 2012-2017 backfill and bank-specialist history are intentionally fetched
    # before any V2 return is inspected.
    early_fin, val_map = fetch_early_baostock(market, q)
    bank_f10 = fetch_bank_f10()

    top10, top20, lowvol = {}, {}, {}
    selected_rows = []
    scored_rows = []
    route_rows = []

    for y in range(START_YEAR, END_SELECTION_YEAR + 1):
        x, scored, fin = build_year_scored(market, payload, early_fin, val_map, meta, bank_f10, q, y)
        s10 = select_routed(scored, 10)
        s20 = select_routed(scored, 20)
        raw_my = market[market["year"].eq(y)].copy()
        lv = call_lowvol(raw_my, fin)
        top10[y], top20[y], lowvol[y] = s10, s20, lv
        if not scored.empty:
            t = scored.copy(); t["selection_year"] = y; scored_rows.append(t)
            for route, g in scored.groupby("route"):
                route_rows.append({"year": y, "route": route, "eligible": len(g), "top_score": float(g["RouteScore"].max()), "median_score": float(g["RouteScore"].median())})
        if not s10.empty:
            t = s10.copy(); t["selection_year"] = y; selected_rows.append(t)
        log("V2 YEAR", y, "TOP10", [(r.code6, r.route, round(float(r.RouteScore), 3)) for r in s10.itertuples(index=False)])

    if selected_rows:
        pd.concat(selected_rows, ignore_index=True).to_csv(OUT / "top10_by_year.csv", index=False)
    if scored_rows:
        pd.concat(scored_rows, ignore_index=True).to_csv(OUT / "all_routed_scores.csv.gz", index=False, compression="gzip")
    pd.DataFrame(route_rows).to_csv(OUT / "route_coverage.csv", index=False)

    # Return calculation: same V1 engine/cost convention.
    annual_rows = []
    prev_codes = set()
    for y in range(START_YEAR, END_BACKTEST_YEAR + 1):
        s = top10.get(y, pd.DataFrame())
        ret = float(s["fwd_return"].mean()) if not s.empty else np.nan
        codes = set(s["code6"]) if not s.empty else set()
        turnover = 1.0 if not prev_codes else 1.0 - len(codes & prev_codes) / TOPN
        _, exe = q.may_dates(y)
        cost = v1.trading_cost_rate(exe, turnover, initial=(not prev_codes))
        net = (1 + ret) * (1 - cost) - 1 if np.isfinite(ret) else np.nan
        prev_codes = codes
        s20 = top20.get(y, pd.DataFrame())
        r20 = float(s20["fwd_return"].mean()) if not s20.empty else np.nan
        lv = lowvol.get(y, pd.DataFrame())
        lvr = float((lv["fwd_return"] * lv["weight"]).sum()) if not lv.empty and "weight" in lv.columns else np.nan
        annual_rows.append({"year": y, "RoutedTop10_gross": ret, "RoutedTop10_net": net, "turnover_oneway": turnover, "cost_rate": cost, "RoutedTop20_gross": r20, "LowVolProxy_gross": lvr})
    annual = pd.DataFrame(annual_rows)
    annual.to_csv(OUT / "annual_returns.csv", index=False)

    nav10 = v1.daily_path(q, top10, weighted=False)
    nav20 = v1.daily_path(q, top20, weighted=False)
    navlv = v1.daily_path(q, lowvol, weighted=True)
    navdf = pd.concat([nav10.rename("RoutedTop10"), nav20.rename("RoutedTop20"), navlv.rename("LowVolProxy")], axis=1, sort=False)
    navdf.index.name = "date"
    navdf.to_csv(OUT / "daily_nav_gross.csv")

    summary = pd.DataFrame([
        {"strategy": "RoutedTop10_gross", **v1.portfolio_metrics(annual, "RoutedTop10_gross", nav10)},
        {"strategy": "RoutedTop10_net", **v1.portfolio_metrics(annual, "RoutedTop10_net", None)},
        {"strategy": "RoutedTop20_gross", **v1.portfolio_metrics(annual, "RoutedTop20_gross", nav20)},
        {"strategy": "LowVolProxy_gross", **v1.portfolio_metrics(annual, "LowVolProxy_gross", navlv)},
    ])
    summary.to_csv(OUT / "summary.csv", index=False)

    period_rows = []
    for s in ["RoutedTop10_gross", "RoutedTop10_net", "RoutedTop20_gross", "LowVolProxy_gross"]:
        for a, b, label in [(2012, 2018, "early"), (2019, 2025, "recent"), (2012, 2025, "full")]:
            period_rows.append({"strategy": s, "period": label, **v1.annual_period_metrics(annual, s, a, b)})
    periods = pd.DataFrame(period_rows)
    periods.to_csv(OUT / "period_summary.csv", index=False)

    s2026 = top10.get(2026, pd.DataFrame())
    model_codes = set(s2026["code6"].astype(str)) if not s2026.empty else set()
    overlap = sorted(model_codes & set(OFFICIAL_2026))
    overlap_info = {
        "model_2026_codes": sorted(model_codes),
        "official_2026_codes": OFFICIAL_2026,
        "overlap_codes": overlap,
        "overlap_n": len(overlap),
        "overlap_rate": len(overlap) / 10.0,
        "representative_gate": len(overlap) >= 6,
        "note": "2026 model signal is early May while official frozen Top10 is September; this is a structural sanity check, not an optimization target.",
    }
    (REPORTS / "2026_overlap_sanity.json").write_text(json.dumps(overlap_info, ensure_ascii=False, indent=2), encoding="utf-8")

    coverage_years = int(annual["RoutedTop10_gross"].notna().sum())
    row = summary[summary["strategy"].eq("RoutedTop10_gross")].iloc[0].to_dict()
    cagr = row.get("cagr", np.nan)
    gates = {
        "full_14_year_coverage": coverage_years == 14,
        "2026_overlap_at_least_6": len(overlap) >= 6,
        "gross_cagr_above_12_1pct": bool(np.isfinite(cagr) and cagr > HARD_BENCHMARK_CAGR),
    }
    (REPORTS / "v2_gates.json").write_text(json.dumps(gates, ensure_ascii=False, indent=2), encoding="utf-8")

    definition = """# V2 Industry-Routed 模型冻结定义\n\n- 银行：BankQV = 65%银行质量 + 35%估值。\n- 公用事业/交通基础设施：40%质量 + 25%估值 + 25%分红 + 10%低波。\n- 周期：30%正常化质量 + 30%正常化估值 + 20%分红 + 20%低波；正常化PE惩罚峰值利润。\n- 稳定资产：45%质量 + 25%估值 + 25%分红 + 5%低波。\n- 普通稳定行业：50%质量 + 25%估值 + 20%分红 + 5%低波。\n- Top10 上限：银行3、周期1、其他金融1、公用事业3、交通3、稳定资产2、普通稳定6。\n- 2012–2017 使用 BaoStock 2007+ 年报 pubDate 与当日 PE/PB；2018+ 使用 V1 Tushare PIT 财务快照。\n- 行业标签仅作为宽路由元数据，不作为收益特征。\n"""
    (OUT / "MODEL_DEFINITION.md").write_text(definition, encoding="utf-8")

    md = "# A股红利核心股 PIT 动态Top10 V2.0 — Industry Routed\n\n"
    md += f"- 有效回测年份：{coverage_years}/14\n"
    md += f"- 2026与冻结Top10重合：{len(overlap)}/10\n"
    if np.isfinite(cagr):
        md += f"- RoutedTop10 gross CAGR：{cagr:.2%}；{'超过' if cagr > HARD_BENCHMARK_CAGR else '未超过'} 12.1%硬基准。\n"
    md += "\n## Gates\n\n```json\n" + json.dumps(gates, ensure_ascii=False, indent=2) + "\n```\n"
    md += "\n## Summary\n\n" + summary.to_markdown(index=False)
    md += "\n\n## Period stability\n\n" + periods.to_markdown(index=False)
    md += "\n\n## Annual returns\n\n" + annual.to_markdown(index=False)
    md += "\n\n## 2026 overlap\n\n```json\n" + json.dumps(overlap_info, ensure_ascii=False, indent=2) + "\n```\n"
    md += "\n" + definition
    (OUT / "README.md").write_text(md, encoding="utf-8")
    log(md[:25000])


if __name__ == "__main__":
    main()
