#!/usr/bin/env python3
"""
A股红利核心股 PIT 动态 Top10 回测 V1.0（Pilot）

目的：验证“Quality + Valuation + Dividend + Safety”这一已冻结方法论，
是否有能力在严格防前视下超过约 12% 的历史收益硬基准。

重要：本脚本不是对 2026 官方 Top10 的历史倒推。此前项目没有冻结一套
可复现的“全A年度精确权重公式”，因此本文件明确新增一个可复现的 V1.0
量化代理模型，并把 2026 与官方 Top10 的重合度作为 sanity check。
"""

from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np
import pandas as pd

# -------------------------------
# Parameters
# -------------------------------
START_YEAR = 2012
END_SELECTION_YEAR = 2026
END_BACKTEST_YEAR = 2025
LOOKBACK_YEARS = 5
TOPN = 10
TOPN20 = 20
BANK_CAP_TOP10 = 3
BANK_CAP_TOP20 = 6
MIN_LISTED_YEARS = 3.0
MIN_DY = 1.5  # %
MIN_MEDIAN_ROE = 5.0  # %
LIQUIDITY_KEEP_PCT = 0.80  # keep top 80% by 1y avg amount and market cap

QUALITY_WEIGHT = 0.50
VALUATION_WEIGHT = 0.30
DIVIDEND_WEIGHT = 0.20
HARD_BENCHMARK_CAGR = 0.121  # 512890 real-world historical CAGR reference, discussed separately

COMMISSION = 0.0001354
TRANSFER_FEE = 0.00001  # research approximation, each side
STAMP_PRE_20230828 = 0.001
STAMP_POST_20230828 = 0.0005

HF_REPO = "yifishbossman/financial-analyst-data-full"
QLIB_URL = os.environ.get(
    "QLIB_URL",
    "https://github.com/chenditc/investment_data/releases/download/2026-09-05/qlib_bin.tar.gz",
)
QLIB_SHA256 = os.environ.get(
    "QLIB_SHA256",
    "11866b2eaa627b758da43ce075667716598611546fddea981422e5c06a3956f1",
)

OFFICIAL_2026 = {
    "600036": "招商银行",
    "600690": "海尔智家",
    "000598": "兴蓉环境",
    "000333": "美的集团",
    "601128": "常熟银行",
    "001872": "招商港口",
    "002142": "宁波银行",
    "600461": "洪城环境",
    "600007": "中国国贸",
    "601298": "青岛港",
}

BANK_CODES = {
    "000001","002142","002807","002839","002936","002948","002958","002966",
    "600000","600015","600016","600036","600908","600919","600926","600928",
    "601009","601077","601128","601166","601169","601187","601229","601288",
    "601328","601398","601528","601577","601658","601665","601818","601825",
    "601838","601860","601916","601939","601963","601988","601997","601998",
    "603323","001227",
}

ROOT = Path(os.environ.get("OUT_DIR", "_dividend_pit_top10_v1"))
DATA = ROOT / "data"
OUT = ROOT / "out"
REPORTS = ROOT / "reports"
for p in (DATA, OUT, REPORTS):
    p.mkdir(parents=True, exist_ok=True)


def log(*a):
    print(*a, flush=True)


def pct_rank(s: pd.Series, higher: bool = True) -> pd.Series:
    s = pd.to_numeric(s, errors="coerce")
    r = s.rank(pct=True, method="average")
    return r if higher else 1.0 - r + (1.0 / max(s.notna().sum(), 1))


def winsor(s: pd.Series, lo=0.05, hi=0.95) -> pd.Series:
    x = pd.to_numeric(s, errors="coerce")
    if x.notna().sum() < 10:
        return x
    a, b = x.quantile([lo, hi])
    return x.clip(a, b)


def qcode_to_code6(qcode: str) -> str:
    return qcode[-6:]


def code6_to_qcode(code6: str) -> str:
    if code6.startswith("6"):
        return "SH" + code6
    if code6.startswith(("0", "3")):
        return "SZ" + code6
    if code6.startswith(("4", "8", "9")):
        return "BJ" + code6
    return "SZ" + code6


def ensure_deps():
    # Intended for GitHub Actions; harmless locally if packages already exist.
    pass


def download_inputs():
    from huggingface_hub import hf_hub_download

    log("Downloading compact financial inputs from Hugging Face...")
    needed = [
        "parquet/financial/balance_sheet.parquet",
        "parquet/financial/cash_flow.parquet",
        "parquet/financial/profit_sheet.parquet",
        "parquet/tushare_stock_basic.parquet",
        "parquet/xdxr/gbbq.parquet",
    ]
    hf_dir = DATA / "hf"
    hf_dir.mkdir(exist_ok=True)
    paths = {}
    for fn in needed:
        p = hf_hub_download(
            repo_id=HF_REPO,
            repo_type="dataset",
            filename=fn,
            local_dir=str(hf_dir),
        )
        paths[fn] = Path(p)
        log("HF", fn, Path(p).stat().st_size)

    tar = DATA / "qlib_bin.tar.gz"
    qlib_extract = DATA / "qlib"
    if not tar.exists():
        log("Downloading Qlib market data...")
        subprocess.run(
            ["curl", "-L", "--retry", "5", "--retry-delay", "2", "-o", str(tar), QLIB_URL],
            check=True,
        )
    if QLIB_SHA256:
        import hashlib
        h = hashlib.sha256(tar.read_bytes()).hexdigest()
        if h != QLIB_SHA256:
            raise RuntimeError(f"Qlib SHA256 mismatch: {h}")
    if not qlib_extract.exists() or not any(qlib_extract.iterdir()):
        qlib_extract.mkdir(parents=True, exist_ok=True)
        subprocess.run(["tar", "-xzf", str(tar), "-C", str(qlib_extract)], check=True)
    return paths, qlib_extract


def locate_qlib(extract: Path) -> Path:
    for p in [extract / "qlib_bin", extract / "cn_data", extract]:
        if (p / "calendars/day.txt").exists() and (p / "instruments/all.txt").exists() and (p / "features").exists():
            return p
    for m in extract.rglob("calendars/day.txt"):
        p = m.parent.parent
        if (p / "instruments/all.txt").exists() and (p / "features").exists():
            return p
    raise RuntimeError("Qlib root not found")


def normalize_code_col(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    candidates = ["ts_code", "TS_CODE", "code", "CODE", "symbol", "SECUCODE", "SECURITY_CODE"]
    c = next((x for x in candidates if x in out.columns), None)
    if not c:
        raise RuntimeError(f"No security-code column in {list(out.columns)[:30]}")
    s = out[c].astype("string").str.upper().str.extract(r"(\d{6})", expand=False)
    out["code6"] = s
    return out


def normalize_date_col(df: pd.DataFrame, target: str, aliases: List[str]) -> pd.DataFrame:
    c = next((x for x in aliases if x in df.columns), None)
    if c is None:
        df[target] = pd.NaT
        return df
    raw = df[c]
    # Tushare-style dates are often integers/strings YYYYMMDD. Plain pd.to_datetime(int)
    # would interpret them as nanoseconds since epoch, so normalize explicitly.
    text = raw.astype("string").str.replace(r"[^0-9]", "", regex=True).str.slice(0, 8)
    parsed8 = pd.to_datetime(text.where(text.str.len().eq(8)), format="%Y%m%d", errors="coerce")
    fallback = pd.to_datetime(raw, errors="coerce")
    df[target] = parsed8.fillna(fallback)
    return df


def pick_numeric(df: pd.DataFrame, aliases: List[str], target: str) -> pd.DataFrame:
    c = next((x for x in aliases if x in df.columns), None)
    if c is None:
        df[target] = np.nan
    else:
        df[target] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_financials(paths: Dict[str, Path]) -> Tuple[pd.DataFrame, pd.DataFrame]:
    profit = pd.read_parquet(paths["parquet/financial/profit_sheet.parquet"])
    bal = pd.read_parquet(paths["parquet/financial/balance_sheet.parquet"])
    cash = pd.read_parquet(paths["parquet/financial/cash_flow.parquet"])
    basic = pd.read_parquet(paths["parquet/tushare_stock_basic.parquet"])

    log("Schemas:")
    log("profit", list(profit.columns))
    log("balance", list(bal.columns))
    log("cash", list(cash.columns))

    for d in (profit, bal, cash, basic):
        d = d  # no-op for readability

    profit = normalize_code_col(profit)
    bal = normalize_code_col(bal)
    cash = normalize_code_col(cash)
    basic = normalize_code_col(basic)

    for df in (profit, bal, cash):
        normalize_date_col(df, "ann_date_n", ["ann_date", "ANN_DATE", "f_ann_date", "F_ANN_DATE", "NOTICE_DATE"])
        normalize_date_col(df, "end_date_n", ["end_date", "END_DATE", "REPORT_DATE", "REPORTDATE"])

    pick_numeric(profit, ["n_income_attr_p", "NET_PROFIT", "PARENT_NETPROFIT", "net_profit", "n_income"], "net_profit_n")
    pick_numeric(profit, ["revenue", "total_revenue", "total_operate_income", "TOTAL_OPERATE_INCOME", "operate_income"], "revenue_n")
    pick_numeric(bal, ["total_hldr_eqy_exc_min_int", "TOTAL_HLDR_EQY_EXC_MIN_INT", "total_equity", "TOTAL_EQUITY"], "equity_n")
    pick_numeric(bal, ["total_assets", "TOTAL_ASSETS"], "assets_n")
    pick_numeric(bal, ["total_liab", "TOTAL_LIAB", "total_liabilities"], "liab_n")
    pick_numeric(cash, ["n_cashflow_act", "NETCASH_OPERATE", "net_cashflow_operate", "net_operate_cash_flow"], "cfo_n")

    keep_p = ["code6", "ann_date_n", "end_date_n", "net_profit_n", "revenue_n"]
    keep_b = ["code6", "ann_date_n", "end_date_n", "equity_n", "assets_n", "liab_n"]
    keep_c = ["code6", "ann_date_n", "end_date_n", "cfo_n"]

    profit = profit[keep_p].dropna(subset=["code6", "end_date_n"])
    bal = bal[keep_b].dropna(subset=["code6", "end_date_n"])
    cash = cash[keep_c].dropna(subset=["code6", "end_date_n"])

    # Stock names are used only for reporting, never for eligibility or historical scoring.
    name_col = next((c for c in ["name", "NAME", "symbol", "fullname"] if c in basic.columns), None)
    if name_col:
        names = basic[["code6", name_col]].drop_duplicates("code6").rename(columns={name_col: "name"})
    else:
        names = pd.DataFrame({"code6": basic["code6"].drop_duplicates(), "name": pd.NA})

    # Save schema audit.
    schema = {
        "profit_columns": list(pd.read_parquet(paths["parquet/financial/profit_sheet.parquet"]).columns),
        "balance_columns": list(pd.read_parquet(paths["parquet/financial/balance_sheet.parquet"]).columns),
        "cash_columns": list(pd.read_parquet(paths["parquet/financial/cash_flow.parquet"]).columns),
    }
    (REPORTS / "financial_schema.json").write_text(json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8")

    # Merge is done per signal date after point-in-time filtering.
    payload = {"profit": profit, "bal": bal, "cash": cash}
    return payload, names



def load_dividend_groups(paths: Dict[str, Path]) -> Dict[Tuple[int, int], np.ndarray]:
    """Load PIT-observable cash-dividend events using the same gbbq convention as the bank model."""
    gbbq = pd.read_parquet(paths["parquet/xdxr/gbbq.parquet"])
    required = {"category", "datetime", "market", "code", "hongli_panqianliutong"}
    missing = required - set(gbbq.columns)
    if missing:
        raise RuntimeError(f"gbbq missing columns: {sorted(missing)}")
    cash = gbbq[pd.to_numeric(gbbq["category"], errors="coerce").eq(1)].copy()
    cash["datetime"] = pd.to_numeric(cash["datetime"], errors="coerce")
    cash["cash_per_share"] = pd.to_numeric(cash["hongli_panqianliutong"], errors="coerce") / 10.0
    out: Dict[Tuple[int, int], np.ndarray] = {}
    for (market, code), grp in cash.groupby(["market", "code"], sort=False):
        arr = grp[["datetime", "cash_per_share"]].dropna().sort_values("datetime").to_numpy()
        if len(arr):
            out[(int(market), int(code))] = arr
    log("Dividend event groups", len(out))
    return out


def dividend_metrics(div_groups: Dict[Tuple[int, int], np.ndarray], code6: str, signal: pd.Timestamp) -> dict:
    # gbbq market convention inherited from the already-validated bank workflow: SH=1, SZ=0.
    if code6.startswith("6"):
        market = 1
    elif code6.startswith(("0", "3")):
        market = 0
    else:
        return {
            "dps_ttm": 0.0,
            "continuous_dividend_years": 0,
            "dps_cagr_5y": np.nan,
            "dps_max_cut_5y": np.nan,
        }
    arr = div_groups.get((market, int(code6)))
    if arr is None:
        return {
            "dps_ttm": 0.0,
            "continuous_dividend_years": 0,
            "dps_cagr_5y": np.nan,
            "dps_max_cut_5y": np.nan,
        }
    dates = arr[:, 0].astype(int)
    dps = arr[:, 1].astype(float)
    sig_int = int(signal.strftime("%Y%m%d"))
    one_year = int((signal - pd.DateOffset(years=1)).strftime("%Y%m%d"))
    ttm = (dates <= sig_int) & (dates > one_year)
    dps_ttm = float(np.nansum(dps[ttm]))
    eligible = dates <= sig_int
    annual = {}
    for yy in np.unique(dates[eligible] // 10000):
        annual[int(yy)] = float(np.nansum(dps[eligible & ((dates // 10000) == yy)]))
    prev = signal.year - 1
    cont = 0
    while annual.get(prev, 0.0) > 0:
        cont += 1
        prev -= 1
    ys = [signal.year - i for i in range(5, 0, -1)]
    vals = [annual.get(yy, np.nan) for yy in ys]
    if np.isfinite(vals[0]) and vals[0] > 0 and np.isfinite(vals[-1]) and vals[-1] > 0:
        cagr = (vals[-1] / vals[0]) ** (1 / 4) - 1
    else:
        cagr = np.nan
    cuts = []
    for a, b in zip(vals[:-1], vals[1:]):
        if np.isfinite(a) and a > 0 and np.isfinite(b):
            cuts.append(b / a - 1)
    max_cut = float(min(cuts)) if cuts else np.nan
    return {
        "dps_ttm": dps_ttm,
        "continuous_dividend_years": cont,
        "dps_cagr_5y": cagr,
        "dps_max_cut_5y": max_cut,
    }

def annual_financial_snapshot(payload: dict, signal_date: pd.Timestamp) -> pd.DataFrame:
    target_year = signal_date.year - 1

    def prep(df: pd.DataFrame, fields: List[str]) -> pd.DataFrame:
        x = df[
            (df["ann_date_n"].notna())
            & (df["ann_date_n"] <= signal_date)
            & (df["end_date_n"].dt.month == 12)
            & (df["end_date_n"].dt.day == 31)
            & (df["end_date_n"].dt.year <= target_year)
        ].copy()
        x = x.sort_values(["code6", "end_date_n", "ann_date_n"]).drop_duplicates(["code6", "end_date_n"], keep="last")
        return x[["code6", "end_date_n"] + fields]

    p = prep(payload["profit"], ["net_profit_n", "revenue_n"])
    b = prep(payload["bal"], ["equity_n", "assets_n", "liab_n"])
    c = prep(payload["cash"], ["cfo_n"])

    x = p.merge(b, on=["code6", "end_date_n"], how="outer").merge(c, on=["code6", "end_date_n"], how="outer")
    x["fyear"] = x["end_date_n"].dt.year
    x = x.sort_values(["code6", "fyear"])

    # Keep last 5 annual periods per security, all known at signal date.
    x = x.groupby("code6", group_keys=False).tail(LOOKBACK_YEARS)
    x["roe_n"] = np.where(
        (x["equity_n"] > 0) & x["net_profit_n"].notna(),
        x["net_profit_n"] / x["equity_n"] * 100.0,
        np.nan,
    )
    x["debt_assets_n"] = np.where(
        x["assets_n"] > 0,
        x["liab_n"] / x["assets_n"],
        np.nan,
    )
    x["cfo_ni_n"] = np.where(
        x["net_profit_n"].abs() > 1e-9,
        x["cfo_n"] / x["net_profit_n"],
        np.nan,
    )

    rows = []
    for code6, g in x.groupby("code6"):
        g = g.sort_values("fyear")
        last3 = g.tail(3)
        roe = g["roe_n"].replace([np.inf, -np.inf], np.nan).dropna()
        npf = g["net_profit_n"].replace([np.inf, -np.inf], np.nan)
        rev = g["revenue_n"].replace([np.inf, -np.inf], np.nan)

        def cagr(vals: pd.Series) -> float:
            vals = vals.dropna()
            if len(vals) < 3 or vals.iloc[0] <= 0 or vals.iloc[-1] <= 0:
                return np.nan
            n = len(vals) - 1
            return (vals.iloc[-1] / vals.iloc[0]) ** (1.0 / n) - 1.0

        rows.append({
            "code6": code6,
            "fin_year_latest": int(g["fyear"].max()) if len(g) else np.nan,
            "annual_count": int(len(g)),
            "roe_median_5y": float(roe.median()) if len(roe) else np.nan,
            "roe_std_5y": float(roe.std(ddof=1)) if len(roe) >= 2 else np.nan,
            "profit_cagr": cagr(npf.tail(3)),
            "revenue_cagr": cagr(rev.tail(3)),
            "cfo_ni_median_3y": float(last3["cfo_ni_n"].median()) if last3["cfo_ni_n"].notna().any() else np.nan,
            "positive_profit_3y": int((last3["net_profit_n"] > 0).sum()),
            "positive_cfo_3y": int((last3["cfo_n"] > 0).sum()),
            "debt_assets_latest": float(g["debt_assets_n"].iloc[-1]) if pd.notna(g["debt_assets_n"].iloc[-1]) else np.nan,
        })
    # Preserve the merge contract even when an early signal date has no
    # disclosed annual statements yet.  Without explicit columns, an empty
    # `rows` list produces a DataFrame with no `code6` column and the first
    # yearly scoring merge fails with KeyError instead of yielding no picks.
    return pd.DataFrame(rows, columns=[
        "code6",
        "fin_year_latest",
        "annual_count",
        "roe_median_5y",
        "roe_std_5y",
        "profit_cagr",
        "revenue_cagr",
        "cfo_ni_median_3y",
        "positive_profit_3y",
        "positive_cfo_3y",
        "debt_assets_latest",
    ])


@dataclass
class QlibStore:
    root: Path
    calendar: pd.DatetimeIndex
    instruments: pd.DataFrame

    @classmethod
    def create(cls, root: Path):
        cal = pd.DatetimeIndex(pd.to_datetime(pd.read_csv(root / "calendars/day.txt", header=None)[0]))
        ins = pd.read_csv(root / "instruments/all.txt", sep="\t", header=None, names=["qcode", "start", "end"])
        ins["start"] = pd.to_datetime(ins["start"], errors="coerce")
        ins["end"] = pd.to_datetime(ins["end"], errors="coerce")
        return cls(root, cal, ins)

    def read_arr(self, qcode: str, field: str):
        fp = self.root / "features" / qcode.lower() / f"{field}.day.bin"
        if not fp.exists():
            return None, None
        arr = np.fromfile(fp, dtype="<f4")
        if len(arr) < 2:
            return None, None
        return int(arr[0]), arr[1:].astype(float)

    def value(self, start: Optional[int], arr: Optional[np.ndarray], idx: int):
        if arr is None or start is None:
            return np.nan
        j = idx - start
        if j < 0 or j >= len(arr):
            return np.nan
        return float(arr[j])

    def nearest_index(self, date: pd.Timestamp, direction="after") -> Optional[int]:
        if direction == "after":
            i = self.calendar.searchsorted(date, side="left")
            return int(i) if i < len(self.calendar) else None
        i = self.calendar.searchsorted(date, side="right") - 1
        return int(i) if i >= 0 else None

    def may_dates(self, year: int) -> Tuple[pd.Timestamp, pd.Timestamp]:
        m = self.calendar[(self.calendar.year == year) & (self.calendar.month == 5)]
        if len(m) < 2:
            raise RuntimeError(f"No two May trading days for {year}")
        return pd.Timestamp(m[0]), pd.Timestamp(m[1])


def build_market_panel(q: QlibStore, div_groups: Dict[Tuple[int, int], np.ndarray]) -> pd.DataFrame:
    years = range(START_YEAR - 2, END_SELECTION_YEAR + 1)
    idxs = {}
    for y in years:
        sig, exe = q.may_dates(y)
        idxs[y] = {
            "signal_date": sig,
            "exec_date": exe,
            "signal_idx": q.calendar.get_loc(sig),
            "exec_idx": q.calendar.get_loc(exe),
        }
    # Exit open for backtest years = next year's second May trading day.
    for y in range(START_YEAR - 2, END_BACKTEST_YEAR + 1):
        _, ex2 = q.may_dates(y + 1)
        idxs[y]["exit_date"] = ex2
        idxs[y]["exit_idx"] = q.calendar.get_loc(ex2)

    fields = ["open", "close", "factor", "amount", "pe_ttm", "pb", "dv_ttm", "total_mv"]
    rows = []
    allins = q.instruments[q.instruments["qcode"].astype(str).str.match(r"^(SH|SZ|BJ)\d{6}$", na=False)]
    log("Building annual market panel from", len(allins), "instruments")

    for n, r in enumerate(allins.itertuples(index=False), 1):
        qcode = r.qcode
        arrays = {f: q.read_arr(qcode, f) for f in fields}
        if arrays["close"][1] is None:
            continue
        code6 = qcode_to_code6(qcode)
        for y in years:
            meta = idxs[y]
            si = meta["signal_idx"]
            ei = meta["exec_idx"]
            start_close, close = arrays["close"]
            c = q.value(start_close, close, si)
            st_factor, factor_arr = arrays["factor"]
            factor = q.value(st_factor, factor_arr, si)
            if not np.isfinite(c) or not np.isfinite(factor) or factor == 0:
                continue
            raw_price = c / factor
            # Must already be listed by signal date and not ended before it.
            if pd.notna(r.start) and r.start > meta["signal_date"]:
                continue
            if pd.notna(r.end) and r.end < meta["signal_date"]:
                continue

            vals = {}
            for f in ["pe_ttm", "pb", "dv_ttm", "total_mv"]:
                st, ar = arrays[f]
                vals[f] = q.value(st, ar, si)

            # 252-day trailing stats known at signal date.
            st_amt, amt = arrays["amount"]
            j_amt = si - st_amt if amt is not None else -1
            if amt is not None and 0 <= j_amt < len(amt):
                block_amt = amt[max(0, j_amt - 251): j_amt + 1]
                avg_amount = float(np.nanmean(block_amt)) if np.isfinite(block_amt).any() else np.nan
            else:
                avg_amount = np.nan

            st_mv, mv = arrays["total_mv"]
            j_mv = si - st_mv if mv is not None else -1
            if mv is not None and 0 <= j_mv < len(mv):
                block_mv = mv[max(0, j_mv - 251): j_mv + 1]
                avg_mv = float(np.nanmean(block_mv)) if np.isfinite(block_mv).any() else np.nan
            else:
                avg_mv = np.nan

            j_close = si - start_close
            block_c = close[max(0, j_close - 251): j_close + 1]
            block_c = block_c[np.isfinite(block_c)]
            if len(block_c) >= 60:
                rets = pd.Series(block_c).pct_change().dropna()
                vol = float(rets.std(ddof=1) * math.sqrt(252)) if len(rets) >= 20 else np.nan
            else:
                vol = np.nan

            st_open, op = arrays["open"]
            entry_open = q.value(st_open, op, ei)
            exit_open = np.nan
            fwd = np.nan
            if "exit_idx" in meta:
                exit_open = q.value(st_open, op, meta["exit_idx"])
                if np.isfinite(entry_open) and np.isfinite(exit_open) and entry_open != 0:
                    fwd = exit_open / entry_open - 1.0

            listed_years = (meta["signal_date"] - r.start).days / 365.25 if pd.notna(r.start) else np.nan
            dm = dividend_metrics(div_groups, code6, meta["signal_date"])
            dy_actual_pct = (dm["dps_ttm"] / raw_price * 100.0) if raw_price > 0 else np.nan
            payout_proxy = (
                dy_actual_pct * vals["pe_ttm"] / 100.0
                if np.isfinite(dy_actual_pct) and np.isfinite(vals["pe_ttm"]) and vals["pe_ttm"] > 0
                else np.nan
            )
            rows.append({
                "year": y,
                "signal_date": meta["signal_date"],
                "exec_date": meta["exec_date"],
                "exit_date": meta.get("exit_date", pd.NaT),
                "qcode": qcode,
                "code6": code6,
                "listed_years": listed_years,
                "close_signal_adj": c,
                "raw_price_signal": raw_price,
                "pe_ttm": vals["pe_ttm"],
                "pb": vals["pb"],
                "dy_ttm": dy_actual_pct,
                "dy_ttm_qlib_audit": vals["dv_ttm"],
                "dps_ttm": dm["dps_ttm"],
                "continuous_dividend_years": dm["continuous_dividend_years"],
                "dps_cagr_5y": dm["dps_cagr_5y"],
                "dps_max_cut_5y": dm["dps_max_cut_5y"],
                "payout_proxy": payout_proxy,
                "avg_amount_252": avg_amount,
                "avg_mv_252": avg_mv,
                "vol_252": vol,
                "entry_open": entry_open,
                "exit_open": exit_open,
                "fwd_return": fwd,
                "is_bank": code6 in BANK_CODES,
            })
        if n % 500 == 0:
            log("market progress", n, "/", len(allins))

    panel = pd.DataFrame(rows)
    panel.to_csv(OUT / "annual_market_panel.csv.gz", index=False, compression="gzip")
    return panel


def add_dividend_history(market: pd.DataFrame) -> pd.DataFrame:
    """Add lagged actual TTM dividend yields for stability diagnostics only."""
    x = market.sort_values(["code6", "year"]).copy()
    for lag in [1, 2]:
        prev = x[["code6", "year", "dy_ttm"]].copy()
        prev["year"] += lag
        prev = prev.rename(columns={"dy_ttm": f"dy_lag{lag}"})
        x = x.merge(prev, on=["code6", "year"], how="left")
    x["three_year_dividend"] = x["continuous_dividend_years"].fillna(0).ge(3)
    x["dy_median_3y"] = x[["dy_ttm", "dy_lag1", "dy_lag2"]].median(axis=1, skipna=False)
    x["dy_min_3y"] = x[["dy_ttm", "dy_lag1", "dy_lag2"]].min(axis=1, skipna=False)
    return x

def select_with_bank_cap(df: pd.DataFrame, score_col: str, n: int, bank_cap: int) -> pd.DataFrame:
    z = df.sort_values(score_col, ascending=False).copy()
    chosen = []
    banks = 0
    for r in z.itertuples(index=False):
        if len(chosen) >= n:
            break
        if bool(r.is_bank):
            if banks >= bank_cap:
                continue
            banks += 1
        chosen.append(r.code6)
    return z[z["code6"].isin(chosen)].sort_values(score_col, ascending=False).head(n)


def score_year(market_y: pd.DataFrame, fin_y: pd.DataFrame, n: int, bank_cap: int) -> pd.DataFrame:
    x = market_y.merge(fin_y, on="code6", how="left")
    # Cross-sectional investability: keep top 80% by both liquidity and size.
    amt_cut = x["avg_amount_252"].quantile(1.0 - LIQUIDITY_KEEP_PCT)
    mv_cut = x["avg_mv_252"].quantile(1.0 - LIQUIDITY_KEEP_PCT)

    eligible = (
        (x["listed_years"] >= MIN_LISTED_YEARS)
        & x["three_year_dividend"].fillna(False)
        & (x["dy_ttm"] >= MIN_DY)
        & (x["avg_amount_252"] >= amt_cut)
        & (x["avg_mv_252"] >= mv_cut)
        & (x["pe_ttm"] > 0)
        & (x["pb"] > 0)
        & (x["annual_count"] >= 3)
        & (x["fin_year_latest"] == (x["year"] - 1))
        & (x["positive_profit_3y"] >= 3)
        & (x["roe_median_5y"] >= MIN_MEDIAN_ROE)
    )
    z = x[eligible].copy()

    # Safety veto for non-banks only. Banks are routed separately because leverage/CFO are structurally different.
    nonbank = ~z["is_bank"]
    veto = nonbank & (
        ((z["debt_assets_latest"].notna()) & (z["debt_assets_latest"] > 0.85))
        | ((z["positive_cfo_3y"].notna()) & (z["positive_cfo_3y"] < 2))
    )
    z = z[~veto].copy()

    # Winsorize noisy growth/cash-flow ratios before ranking.
    z["profit_cagr_w"] = winsor(z["profit_cagr"], 0.05, 0.95)
    z["revenue_cagr_w"] = winsor(z["revenue_cagr"], 0.05, 0.95)
    z["cfo_ni_w"] = winsor(z["cfo_ni_median_3y"], 0.05, 0.95)
    z["roe_stability"] = -z["roe_std_5y"]

    z["q_roe"] = pct_rank(z["roe_median_5y"], True)
    z["q_roe_stability"] = pct_rank(z["roe_stability"], True)
    z["q_profit_growth"] = pct_rank(z["profit_cagr_w"], True)
    z["q_revenue_growth"] = pct_rank(z["revenue_cagr_w"], True)
    z["q_cash"] = pct_rank(z["cfo_ni_w"], True)
    # Bank cash-flow statement is not comparable; neutralize this component rather than penalize banks.
    z.loc[z["is_bank"], "q_cash"] = np.nan
    z["QualityScore"] = z[["q_roe", "q_roe_stability", "q_profit_growth", "q_revenue_growth", "q_cash"]].mean(axis=1, skipna=True)

    z["v_pe"] = pct_rank(z["pe_ttm"], False)
    z["v_pb"] = pct_rank(z["pb"], False)
    z["v_dy"] = pct_rank(z["dy_ttm"], True)
    z["ValuationScore"] = z[["v_pe", "v_pb", "v_dy"]].mean(axis=1, skipna=True)

    z["d_years"] = pct_rank(z["continuous_dividend_years"], True)
    z["d_growth"] = pct_rank(winsor(z["dps_cagr_5y"], 0.05, 0.95), True)
    z["d_stability"] = pct_rank(z["dps_max_cut_5y"], True)
    z["DividendScore"] = z[["d_years", "d_growth", "d_stability"]].mean(axis=1, skipna=True)

    z["CoreScore"] = QUALITY_WEIGHT * z["QualityScore"] + VALUATION_WEIGHT * z["ValuationScore"] + DIVIDEND_WEIGHT * z["DividendScore"]
    z["QVScore"] = 0.65 * z["QualityScore"] + 0.35 * z["ValuationScore"]

    selected = select_with_bank_cap(z, "CoreScore", n=n, bank_cap=bank_cap)
    return selected


def lowvol_proxy_year(market_y: pd.DataFrame) -> pd.DataFrame:
    x = market_y.copy()
    amt_cut = x["avg_amount_252"].quantile(0.20)
    mv_cut = x["avg_mv_252"].quantile(0.20)
    z = x[
        (x["listed_years"] >= MIN_LISTED_YEARS)
        & (x["avg_amount_252"] >= amt_cut)
        & (x["avg_mv_252"] >= mv_cut)
        & x["three_year_dividend"].fillna(False)
        & (x["dy_ttm"] > 0)
        & (x["payout_proxy"] > 0)
    ].copy()
    if len(z) == 0:
        return z
    # Approximate H30269 payout-ratio abnormality filter.
    payout_hi = z["payout_proxy"].quantile(0.95)
    z = z[z["payout_proxy"] <= payout_hi]
    # Approximate 3y DPS-growth filter.
    z = z[z["dps_cagr_5y"].fillna(-1) > 0]
    z = z.sort_values("dy_ttm", ascending=False).head(75)
    z = z.sort_values("vol_252", ascending=True).head(50)
    w = z["dy_ttm"].clip(lower=0)
    if w.sum() <= 0:
        z["weight"] = 1.0 / len(z)
    else:
        z["weight"] = w / w.sum()
    # 10% single-name cap, iterative renormalization approximation.
    for _ in range(10):
        over = z["weight"] > 0.10
        if not over.any():
            break
        excess = (z.loc[over, "weight"] - 0.10).sum()
        z.loc[over, "weight"] = 0.10
        under = ~over
        if under.any() and z.loc[under, "weight"].sum() > 0:
            z.loc[under, "weight"] += excess * z.loc[under, "weight"] / z.loc[under, "weight"].sum()
    z["weight"] /= z["weight"].sum()
    return z


def portfolio_metrics(annual: pd.DataFrame, ret_col: str, daily_nav: Optional[pd.Series] = None) -> dict:
    rets = annual[ret_col].dropna().astype(float)
    if len(rets) == 0:
        return {}
    total = float(np.prod(1.0 + rets) - 1.0)
    cagr = float((1.0 + total) ** (1.0 / len(rets)) - 1.0)
    out = {
        "years": int(len(rets)),
        "total_return": total,
        "cagr": cagr,
        "positive_year_rate": float((rets > 0).mean()),
        "worst_year": float(rets.min()),
        "best_year": float(rets.max()),
        "annual_vol": float(rets.std(ddof=1)) if len(rets) >= 2 else np.nan,
    }
    if daily_nav is not None and len(daily_nav) > 10:
        nav = daily_nav.dropna().astype(float)
        dd = nav / nav.cummax() - 1.0
        d = nav.pct_change().dropna()
        vol = float(d.std(ddof=1) * math.sqrt(252)) if len(d) >= 20 else np.nan
        sharpe = float(d.mean() / d.std(ddof=1) * math.sqrt(252)) if len(d) >= 20 and d.std(ddof=1) > 0 else np.nan
        downside = d[d < 0]
        sortino = float(d.mean() / downside.std(ddof=1) * math.sqrt(252)) if len(downside) >= 10 and downside.std(ddof=1) > 0 else np.nan
        maxdd = float(dd.min())
        out.update({
            "daily_vol": vol,
            "sharpe": sharpe,
            "sortino": sortino,
            "max_drawdown": maxdd,
            "calmar": float(cagr / abs(maxdd)) if maxdd < 0 else np.nan,
        })
    return out


def annual_period_metrics(annual: pd.DataFrame, ret_col: str, start: int, end: int) -> dict:
    x = annual[annual["year"].between(start, end)][["year", ret_col]].dropna().copy()
    r = x[ret_col].astype(float).to_numpy()
    if len(r) == 0:
        return {"start": start, "end": end, "years": 0}
    total = float(np.prod(1.0 + r) - 1.0)
    cagr = float((1.0 + total) ** (1.0 / len(r)) - 1.0)
    return {
        "start": start,
        "end": end,
        "years": int(len(r)),
        "total_return": total,
        "cagr": cagr,
        "positive_year_rate": float(np.mean(r > 0)),
        "worst_year": float(np.min(r)),
        "best_year": float(np.max(r)),
    }

def daily_path(q: QlibStore, selections: Dict[int, pd.DataFrame], weighted: bool = False) -> pd.Series:
    nav0 = 1.0
    pieces = []
    for y in range(START_YEAR, END_BACKTEST_YEAR + 1):
        sel = selections.get(y)
        if sel is None or sel.empty:
            continue
        _, entry = q.may_dates(y)
        _, exitd = q.may_dates(y + 1)
        start_i = q.calendar.get_loc(entry)
        end_i = q.calendar.get_loc(exitd)
        dates = q.calendar[start_i:end_i + 1]
        cols = []
        weights = []
        for r in sel.itertuples(index=False):
            qcode = code6_to_qcode(r.code6)
            st_op, op = q.read_arr(qcode, "open")
            st_cl, cl = q.read_arr(qcode, "close")
            entry_open = q.value(st_op, op, start_i)
            exit_open = q.value(st_op, op, end_i)
            if not np.isfinite(entry_open) or entry_open == 0 or cl is None:
                continue
            vals = []
            for i in range(start_i, end_i + 1):
                v = q.value(st_cl, cl, i)
                vals.append(v / entry_open if np.isfinite(v) else np.nan)
            s = pd.Series(vals, index=dates).ffill()
            if np.isfinite(exit_open):
                s.iloc[-1] = exit_open / entry_open
            cols.append(s)
            weights.append(float(getattr(r, "weight", 1.0)) if weighted else 1.0)
        if not cols:
            continue
        mat = pd.concat(cols, axis=1)
        w = np.array(weights, dtype=float)
        w = w / w.sum()
        rel = mat.mul(w, axis=1).sum(axis=1, min_count=1)
        rel = rel / rel.iloc[0] if rel.iloc[0] != 0 else rel
        path = nav0 * rel
        if pieces:
            path = path.iloc[1:]
        pieces.append(path)
        nav0 = float(path.iloc[-1])
    return pd.concat(pieces) if pieces else pd.Series(dtype=float)


def trading_cost_rate(rebalance_date: pd.Timestamp, one_way_turnover: float, initial: bool = False) -> float:
    """Portfolio-level proportional transaction cost charged at the start of each annual period.

    Initial year: buy 100%. Later years: sell and buy only the replaced fraction.
    No artificial full liquidation is assumed at every year-end.
    """
    if initial:
        return COMMISSION + TRANSFER_FEE
    stamp = STAMP_POST_20230828 if rebalance_date >= pd.Timestamp("2023-08-28") else STAMP_PRE_20230828
    sell = one_way_turnover * (COMMISSION + TRANSFER_FEE + stamp)
    buy = one_way_turnover * (COMMISSION + TRANSFER_FEE)
    return sell + buy


def main():
    paths, qextract = download_inputs()
    qroot = locate_qlib(qextract)
    log("QLIB ROOT", qroot)
    q = QlibStore.create(qroot)
    payload, names = load_financials(paths)
    div_groups = load_dividend_groups(paths)
    market = build_market_panel(q, div_groups)
    market = add_dividend_history(market)

    core10 = {}
    core20 = {}
    lowvol = {}
    all_selected_rows = []
    all_lowvol_rows = []

    for y in range(START_YEAR, END_SELECTION_YEAR + 1):
        sig, _ = q.may_dates(y)
        fin = annual_financial_snapshot(payload, sig)
        my = market[market["year"] == y].copy()
        s10 = score_year(my, fin, TOPN, BANK_CAP_TOP10)
        s20 = score_year(my, fin, TOPN20, BANK_CAP_TOP20)
        lv = lowvol_proxy_year(my)
        core10[y] = s10
        core20[y] = s20
        lowvol[y] = lv
        if not s10.empty:
            tmp = s10.copy(); tmp["selection_year"] = y; all_selected_rows.append(tmp)
        if not lv.empty:
            tmp = lv.copy(); tmp["selection_year"] = y; all_lowvol_rows.append(tmp)
        log("YEAR", y, "Core10", list(s10["code6"]), "LowVol50", len(lv))

    selected_df = pd.concat(all_selected_rows, ignore_index=True) if all_selected_rows else pd.DataFrame()
    selected_df = selected_df.merge(names, on="code6", how="left")
    selected_df.to_csv(OUT / "top10_by_year.csv", index=False)
    if all_lowvol_rows:
        pd.concat(all_lowvol_rows, ignore_index=True).merge(names, on="code6", how="left").to_csv(OUT / "lowvol_proxy_by_year.csv", index=False)

    # Annual returns.
    rows = []
    prev_codes = set()
    for y in range(START_YEAR, END_BACKTEST_YEAR + 1):
        s = core10[y]
        ret = float(s["fwd_return"].mean()) if not s.empty else np.nan
        codes = set(s["code6"])
        turnover = 1.0 if y == START_YEAR else 1.0 - len(codes & prev_codes) / TOPN
        _, exe = q.may_dates(y)
        cost = trading_cost_rate(exe, turnover, initial=(y == START_YEAR))
        net = (1.0 + ret) * (1.0 - cost) - 1.0 if np.isfinite(ret) else np.nan
        prev_codes = codes

        s20 = core20[y]
        ret20 = float(s20["fwd_return"].mean()) if not s20.empty else np.nan
        lv = lowvol[y]
        lvret = float((lv["fwd_return"] * lv["weight"]).sum()) if not lv.empty else np.nan
        rows.append({"year": y, "CoreTop10_gross": ret, "CoreTop10_net": net, "turnover_oneway": turnover, "cost_rate": cost, "CoreTop20_gross": ret20, "LowVolProxy_gross": lvret})
    annual = pd.DataFrame(rows)
    annual.to_csv(OUT / "annual_returns.csv", index=False)

    # Daily NAV and risk.
    nav10 = daily_path(q, core10, weighted=False)
    nav20 = daily_path(q, core20, weighted=False)
    navlv = daily_path(q, lowvol, weighted=True)
    navdf = pd.concat([nav10.rename("CoreTop10"), nav20.rename("CoreTop20"), navlv.rename("LowVolProxy")], axis=1)
    navdf.index.name = "date"
    navdf.to_csv(OUT / "daily_nav_gross.csv")

    summary = []
    summary.append({"strategy": "CoreTop10_gross", **portfolio_metrics(annual, "CoreTop10_gross", nav10)})
    summary.append({"strategy": "CoreTop10_net", **portfolio_metrics(annual, "CoreTop10_net", None)})
    summary.append({"strategy": "CoreTop20_gross", **portfolio_metrics(annual, "CoreTop20_gross", nav20)})
    summary.append({"strategy": "LowVolProxy_gross", **portfolio_metrics(annual, "LowVolProxy_gross", navlv)})
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(OUT / "summary.csv", index=False)

    period_rows = []
    for strategy in ["CoreTop10_gross", "CoreTop10_net", "CoreTop20_gross", "LowVolProxy_gross"]:
        for start_y, end_y, label in [(2012, 2018, "early"), (2019, 2025, "recent"), (2012, 2025, "full")]:
            m = annual_period_metrics(annual, strategy, start_y, end_y)
            period_rows.append({"strategy": strategy, "period": label, **m})
    period_df = pd.DataFrame(period_rows)
    period_df.to_csv(OUT / "period_summary.csv", index=False)

    # 2026 sanity check vs frozen official Top10.
    s2026 = core10.get(2026, pd.DataFrame()).copy()
    s2026 = s2026.merge(names, on="code6", how="left") if not s2026.empty else s2026
    model_codes = set(s2026["code6"]) if not s2026.empty else set()
    overlap = sorted(model_codes & set(OFFICIAL_2026))
    sanity = {
        "official_2026_codes": OFFICIAL_2026,
        "model_2026_codes": sorted(model_codes),
        "overlap_codes": overlap,
        "overlap_n": len(overlap),
        "overlap_rate": len(overlap) / 10.0,
        "interpretation": (
            "Representative enough for provisional project-level inference" if len(overlap) >= 5
            else "Low overlap: treat this as methodology proxy only; do NOT claim it is the historical performance of the frozen 2026 official Top10 model"
        ),
        "timing_note": "V1 selects on early-May PIT data, while the frozen official 2026 Top10 was finalized in September; overlap is only a rough representativeness check.",
    }
    (REPORTS / "2026_overlap_sanity.json").write_text(json.dumps(sanity, ensure_ascii=False, indent=2), encoding="utf-8")

    model_def = f"""# PIT 动态 Top10 V1.0 模型定义\n\n## 定位\n这是可复现 Pilot，不是假装复刻此前未冻结的全A精确公式。\n\n## 时间\n- 信号：每年5月第一个交易日\n- 执行：每年5月第二个交易日开盘\n- 持有：至下一年5月第二个交易日开盘\n- 回测：{START_YEAR}–{END_BACKTEST_YEAR}\n- 2026仅用于当前成分 sanity check\n\n## PIT\n- 财务报表必须 `ann_date <= signal_date`\n- 只使用已披露完整年度\n- 市场估值/股息/流动性只取信号日前数据\n\n## Investability\n- 上市≥{MIN_LISTED_YEARS}年\n- 过去一年平均成交额、市值均位于全A前80%\n\n## Dividend Qualification\n- 使用 gbbq 实际现金分红事件，严格只统计信号日前已发生事件\n- 连续分红年数≥3\n- 当前TTM现金股息率≥{MIN_DY}%\n\n## Safety / Veto\n- PE、PB为正\n- 最近3个完整年度归母净利润均为正\n- 5Y中位ROE≥{MIN_MEDIAN_ROE}%\n- 非银行：资产负债率>85%或最近3年经营现金流仅0–1年为正则剔除\n\n## Quality 50%\n- 5Y中位ROE\n- ROE稳定性\n- 3Y净利润CAGR\n- 3Y营收CAGR\n- 3Y经营现金流/净利润中位数（银行中性化）\n\n## Valuation 30%\n- PE（越低越好）\n- PB（越低越好）\n- 当前TTM现金股息率（越高越好）\n\n## Dividend 20%\n- 连续分红年数\n- 5Y DPS CAGR\n- 5Y DPS最大下调幅度（越稳定越好）\n\n## Concentration guardrail\n- Top10银行最多{BANK_CAP_TOP10}只\n- Top20银行最多{BANK_CAP_TOP20}只\n\n## 成本\n- 佣金：万1.354（比例化；未模拟5元最低佣金）\n- 过户费：单边0.001%近似\n- 卖出印花税：2023-08-28前0.1%，之后0.05%\n- 初始建仓只收买入成本；以后仅对年度替换仓位计双边换手成本\n\n## 关键限制\n1. 该V1是“冻结方法论的量化代理”，不是此前2026榜单的历史复刻。\n2. 通过2026 Top10重合度检查代表性；重合<5/10时禁止把回测收益称为“官方Top10历史收益”。\n3. LowVolProxy近似H30269规则，但不是中证官方指数复刻。\n4. 2012–2018 / 2019–2025只用于稳定性分段，不宣称为真正训练/验证集，因为V1规则是在2026年后定义。\n5. 2026重合度比较存在时间点差异：V1是5月信号，官方Top10冻结于9月。\n"""
    (OUT / "MODEL_DEFINITION.md").write_text(model_def, encoding="utf-8")

    # Human-readable result.
    core_row = summary_df[summary_df["strategy"] == "CoreTop10_gross"].iloc[0].to_dict()
    net_row = summary_df[summary_df["strategy"] == "CoreTop10_net"].iloc[0].to_dict()
    lv_row = summary_df[summary_df["strategy"] == "LowVolProxy_gross"].iloc[0].to_dict()
    conclusion = []
    cagr = core_row.get("cagr", np.nan)
    if np.isfinite(cagr):
        if cagr > HARD_BENCHMARK_CAGR:
            conclusion.append(f"CoreTop10 V1 gross CAGR={cagr:.2%}，超过512890约12.1%历史CAGR硬基准。")
        else:
            conclusion.append(f"CoreTop10 V1 gross CAGR={cagr:.2%}，未超过512890约12.1%历史CAGR硬基准。")
    conclusion.append(f"2026与冻结官方Top10重合 {len(overlap)}/10。{sanity['interpretation']}")

    md = "# A股红利核心股 PIT 动态Top10 V1.0 回测结果\n\n" + "\n".join(f"- {x}" for x in conclusion) + "\n\n## Summary\n\n" + summary_df.to_markdown(index=False) + "\n\n## Period stability\n\n" + period_df.to_markdown(index=False) + "\n\n## Annual returns\n\n" + annual.to_markdown(index=False) + "\n\n## 2026 overlap\n\n" + json.dumps(sanity, ensure_ascii=False, indent=2) + "\n\n" + model_def
    (OUT / "README.md").write_text(md, encoding="utf-8")
    log(md[:20000])


if __name__ == "__main__":
    main()
