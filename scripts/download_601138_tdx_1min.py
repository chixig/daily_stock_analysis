#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工业富联 601138｜通达信免费 1 分钟历史数据探测 / 回填器

使用 easy-tdx（无需账号、无需 Secret、无需付费）。

模式：
  probe         只探测历史深度（推荐第一次先跑）
  kline_full    分页抓取真正 1 分钟 OHLCV K线
  snapshot_full 按交易日抓取历史分时 240 点（price + vol）
  both_full     两种都抓
  incremental   对已经存在的数据做近期增量更新

为什么分两种数据：
1) get_security_bars(..., KlineCategory.MIN_1, start, count)
   -> 真正的 1m OHLCV；最多 800 根/次，可通过 start 向历史分页。
2) get_history_minute_time_data(..., YYYYMMDD)
   -> 历史分时图，每分钟 price + vol，共约 240 点；不是 OHLC。

输出：
  data/601138_intraday/tdx_1min/
    probe_report.json
    coverage.json
    daily_trade_calendar.csv
    kline_yearly/601138_1m_kline_YYYY.csv
    snapshot_yearly/601138_1m_snapshot_YYYY.csv
    qc_kline_daily.csv
    qc_snapshot_daily.csv

注意：
- 这是对“通达信公开行情服务器实际保留深度”的实测，不预设一定能到 2018。
- 第一次应先 mode=probe；看到 probe_report.json 再决定跑哪种 full。
"""

from __future__ import annotations

import argparse
import json
import math
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from easy_tdx import TdxClient, Market, KlineCategory


CODE = "601138"
MARKET = Market.SH
LISTED = pd.Timestamp("2018-06-08")
DEFAULT_OUT = Path("data/601138_intraday/tdx_1min")
PAGE = 800


def log(msg: str) -> None:
    print(msg, flush=True)


def json_dump(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def normalize_kline(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    x = df.copy()
    if "datetime" not in x.columns:
        raise RuntimeError(f"MIN_1 Kline response missing datetime: {list(x.columns)}")
    x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
    x = x.dropna(subset=["datetime"]).copy()
    x["date"] = x["datetime"].dt.normalize()
    for c in ["open", "high", "low", "close", "vol", "amount"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x["symbol"] = CODE
    x["source"] = "TDX_MIN1_KLINE"
    cols = ["symbol", "datetime", "date", "open", "high", "low", "close", "vol", "amount", "source"]
    cols = [c for c in cols if c in x.columns]
    return (
        x[cols]
        .drop_duplicates("datetime", keep="last")
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def normalize_snapshot(df: pd.DataFrame, yyyymmdd: int) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    x = df.copy()
    if "datetime" not in x.columns:
        # easy-tdx 正常会自动补 datetime；这里只做防御
        d = pd.Timestamp(str(yyyymmdd))
        mins = []
        for i in range(len(x)):
            if i < 120:
                mins.append(d + pd.Timedelta(hours=9, minutes=30+i))
            else:
                mins.append(d + pd.Timedelta(hours=13, minutes=i-120))
        x.insert(0, "datetime", mins)
    x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
    x = x.dropna(subset=["datetime"]).copy()
    x["date"] = x["datetime"].dt.normalize()
    for c in ["price", "vol"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")
    x["symbol"] = CODE
    x["source"] = "TDX_HISTORY_MINUTE_SNAPSHOT"
    cols = ["symbol", "datetime", "date", "price", "vol", "source"]
    cols = [c for c in cols if c in x.columns]
    return (
        x[cols]
        .drop_duplicates("datetime", keep="last")
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def fetch_daily_calendar(client: TdxClient, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    """用通达信日K自身构造工业富联实际交易日，避免逐自然日猜测。"""
    pieces = []
    offset = 0
    seen = set()
    for _ in range(20):  # 20*800 远超上市以来日线数量
        df = client.get_security_bars(MARKET, CODE, KlineCategory.DAY, offset, PAGE)
        if df is None or df.empty:
            break
        if "date" not in df.columns:
            raise RuntimeError(f"Daily bars missing date: {list(df.columns)}")
        df = df.copy()
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        df = df.dropna(subset=["date"])
        sig = (str(df["date"].min()), str(df["date"].max()), len(df))
        if sig in seen:
            break
        seen.add(sig)
        pieces.append(df)
        if df["date"].min() <= start:
            break
        offset += PAGE
        time.sleep(0.03)

    if not pieces:
        raise RuntimeError("Could not fetch daily trade calendar from TDX")
    x = pd.concat(pieces, ignore_index=True)
    x = x.drop_duplicates("date", keep="last").sort_values("date")
    x = x[(x["date"] >= start) & (x["date"] <= end)].reset_index(drop=True)
    return x


def fetch_min1_page(client: TdxClient, offset: int, count: int = PAGE) -> pd.DataFrame:
    return normalize_kline(
        client.get_security_bars(MARKET, CODE, KlineCategory.MIN_1, int(offset), int(count))
    )


def probe_kline_depth(client: TdxClient, target_start: pd.Timestamp) -> dict:
    """指数跳页 + 二分，快速找到 MIN_1 服务器可返回的最大历史 offset。"""
    records = []

    def call(page_no: int) -> tuple[bool, Optional[pd.DataFrame]]:
        offset = page_no * PAGE
        try:
            df = fetch_min1_page(client, offset, 20)
            rec = {
                "page_no": page_no,
                "offset": offset,
                "rows": int(len(df)),
                "min_datetime": None if df.empty else df["datetime"].min().isoformat(),
                "max_datetime": None if df.empty else df["datetime"].max().isoformat(),
            }
            records.append(rec)
            return (not df.empty), df
        except Exception as e:
            records.append({"page_no": page_no, "offset": offset, "rows": 0, "error": str(e)})
            return False, None

    # page 0 必须能取到近期数据
    ok0, df0 = call(0)
    if not ok0:
        return {"ok": False, "reason": "MIN_1 current page returned empty", "samples": records}

    if df0 is not None and df0["datetime"].min().normalize() <= target_start:
        return {
            "ok": True,
            "oldest_available": df0["datetime"].min().isoformat(),
            "reaches_target_start": True,
            "samples": records,
        }

    # 指数寻找 first empty page
    last_nonempty = 0
    first_empty = None
    p = 1
    while p <= 2048:  # 2048*800 > 160万根，足够
        ok, df = call(p)
        if ok:
            last_nonempty = p
            if df is not None and df["datetime"].min().normalize() <= target_start:
                return {
                    "ok": True,
                    "oldest_available": df["datetime"].min().isoformat(),
                    "reaches_target_start": True,
                    "max_tested_page": p,
                    "samples": records,
                }
            p *= 2
        else:
            first_empty = p
            break

    if first_empty is None:
        first_empty = p

    # 二分最大 non-empty page
    lo, hi = last_nonempty, first_empty
    while hi - lo > 1:
        mid = (lo + hi) // 2
        ok, _ = call(mid)
        if ok:
            lo = mid
        else:
            hi = mid

    # 最大 non-empty page 用完整800根再确认最早时间
    oldest_df = fetch_min1_page(client, lo * PAGE, PAGE)
    oldest = None if oldest_df.empty else oldest_df["datetime"].min()
    return {
        "ok": True,
        "max_nonempty_page": int(lo),
        "max_nonempty_offset": int(lo * PAGE),
        "oldest_available": None if oldest is None else oldest.isoformat(),
        "reaches_target_start": bool(oldest is not None and oldest.normalize() <= target_start),
        "samples": records,
    }


def nearest_trade_date(trade_dates: list[pd.Timestamp], target: pd.Timestamp) -> Optional[pd.Timestamp]:
    candidates = [d for d in trade_dates if d >= target]
    return candidates[0] if candidates else None


def probe_snapshot_depth(client: TdxClient, daily: pd.DataFrame) -> dict:
    dates = list(pd.to_datetime(daily["date"]).dt.normalize())
    targets = [
        pd.Timestamp("2018-06-08"),
        pd.Timestamp("2019-01-02"),
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2021-01-04"),
        pd.Timestamp("2022-01-04"),
        pd.Timestamp("2023-01-03"),
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2025-01-02"),
        dates[-1] if dates else pd.Timestamp.today().normalize(),
    ]
    out = []
    for t in targets:
        d = nearest_trade_date(dates, t)
        if d is None:
            continue
        dint = int(d.strftime("%Y%m%d"))
        try:
            df = normalize_snapshot(client.get_history_minute_time_data(MARKET, CODE, dint), dint)
            out.append({
                "date": d.strftime("%Y-%m-%d"),
                "rows": int(len(df)),
                "first_price": None if df.empty or "price" not in df else float(df.iloc[0]["price"]),
                "last_price": None if df.empty or "price" not in df else float(df.iloc[-1]["price"]),
                "looks_complete_240": bool(len(df) == 240),
            })
        except Exception as e:
            out.append({"date": d.strftime("%Y-%m-%d"), "rows": 0, "error": str(e)})
        time.sleep(0.03)

    first = next((r for r in out if r["date"] == dates[0].strftime("%Y-%m-%d")), None) if dates else None
    # 上市首日可能交易时长/停牌等特殊，因此 reaches_2018 允许 >=200 条作为“有历史数据”的证据
    first_2018 = next((r for r in out if r["date"].startswith("2018-")), None)
    return {
        "probes": out,
        "reaches_2018": bool(first_2018 and first_2018.get("rows", 0) >= 200),
        "first_trade_date": None if not dates else dates[0].strftime("%Y-%m-%d"),
    }


def load_yearly(folder: Path, pattern: str) -> pd.DataFrame:
    if not folder.exists():
        return pd.DataFrame()
    parts = []
    for p in sorted(folder.glob(pattern)):
        try:
            x = pd.read_csv(p)
            if "datetime" in x.columns:
                x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
            if "date" in x.columns:
                x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.normalize()
            parts.append(x)
        except Exception as e:
            log(f"WARNING read {p}: {e}")
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    if "datetime" in x.columns:
        x = x.dropna(subset=["datetime"]).drop_duplicates("datetime", keep="last").sort_values("datetime")
    return x.reset_index(drop=True)


def save_yearly(df: pd.DataFrame, folder: Path, prefix: str) -> None:
    if df.empty:
        return
    folder.mkdir(parents=True, exist_ok=True)
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"], errors="coerce")
    x = x.dropna(subset=["datetime"])
    for year, g in x.groupby(x["datetime"].dt.year):
        g.sort_values("datetime").to_csv(folder / f"{prefix}_{int(year)}.csv", index=False)


def fetch_kline_full(client: TdxClient, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
    parts = []
    offset = 0
    seen = set()
    while offset <= 1_600_000:
        df = fetch_min1_page(client, offset, PAGE)
        if df.empty:
            log(f"MIN_1 empty at offset={offset}; stop")
            break
        sig = (df["datetime"].min().isoformat(), df["datetime"].max().isoformat(), len(df))
        if sig in seen:
            log(f"MIN_1 repeated page at offset={offset}; stop")
            break
        seen.add(sig)
        parts.append(df)
        oldest = df["datetime"].min().normalize()
        newest = df["datetime"].max().normalize()
        log(f"MIN_1 offset={offset:>7} rows={len(df):>3} {oldest.date()} -> {newest.date()}")
        if oldest <= start:
            break
        offset += PAGE
        time.sleep(0.03)

    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    x = x.drop_duplicates("datetime", keep="last").sort_values("datetime")
    x = x[(x["datetime"].dt.normalize() >= start) & (x["datetime"].dt.normalize() <= end)]
    return x.reset_index(drop=True)


def fetch_snapshot_full(client: TdxClient, trade_dates: list[pd.Timestamp], existing: pd.DataFrame) -> pd.DataFrame:
    existing_dates = set()
    if not existing.empty and "date" in existing.columns:
        existing_dates = set(pd.to_datetime(existing["date"], errors="coerce").dropna().dt.normalize())

    parts = [existing] if not existing.empty else []
    total = len(trade_dates)
    for i, d in enumerate(trade_dates, 1):
        if d in existing_dates:
            continue
        dint = int(d.strftime("%Y%m%d"))
        last_err = None
        df = pd.DataFrame()
        for attempt in range(3):
            try:
                df = normalize_snapshot(client.get_history_minute_time_data(MARKET, CODE, dint), dint)
                last_err = None
                break
            except Exception as e:
                last_err = e
                time.sleep(0.4 * (attempt + 1))
        if last_err is not None:
            log(f"[{i}/{total}] {d.date()} ERROR {last_err}")
            continue
        log(f"[{i}/{total}] {d.date()} snapshot rows={len(df)}")
        if not df.empty:
            parts.append(df)
        time.sleep(0.02)

    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True)
    x = x.drop_duplicates("datetime", keep="last").sort_values("datetime")
    return x.reset_index(drop=True)


def qc_kline(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"])
    x["date"] = x["datetime"].dt.normalize()
    q = x.groupby("date", as_index=False).agg(
        bars=("datetime", "count"),
        first_time=("datetime", "min"),
        last_time=("datetime", "max"),
        day_open=("open", "first"),
        day_high=("high", "max"),
        day_low=("low", "min"),
        day_close=("close", "last"),
        volume=("vol", "sum"),
        amount=("amount", "sum"),
    )
    q["bars_240"] = q["bars"] == 240
    return q


def qc_snapshot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"])
    x["date"] = x["datetime"].dt.normalize()
    q = x.groupby("date", as_index=False).agg(
        bars=("datetime", "count"),
        first_time=("datetime", "min"),
        last_time=("datetime", "max"),
        first_price=("price", "first"),
        max_price=("price", "max"),
        min_price=("price", "min"),
        last_price=("price", "last"),
        volume=("vol", "sum"),
    )
    q["bars_240"] = q["bars"] == 240
    return q


def dataset_coverage(df: pd.DataFrame, expected_trade_days: int) -> dict:
    if df.empty:
        return {"rows": 0, "trading_days": 0, "actual_start": None, "actual_end": None, "expected_trade_days": expected_trade_days}
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"])
    days = int(x["datetime"].dt.normalize().nunique())
    return {
        "rows": int(len(x)),
        "trading_days": days,
        "expected_trade_days": int(expected_trade_days),
        "day_coverage_ratio": round(days / expected_trade_days, 6) if expected_trade_days else None,
        "actual_start": x["datetime"].min().isoformat(),
        "actual_end": x["datetime"].max().isoformat(),
    }


def incremental_kline(client: TdxClient, existing: pd.DataFrame, end: pd.Timestamp) -> pd.DataFrame:
    # 拉最近 10 页（最多 8000 分钟，约 33 个交易日）后合并，足够日常修复缺口
    parts = [existing] if not existing.empty else []
    for off in range(0, 8000, PAGE):
        df = fetch_min1_page(client, off, PAGE)
        if df.empty:
            break
        parts.append(df)
        if not existing.empty:
            old_max = pd.to_datetime(existing["datetime"]).max()
            if df["datetime"].min() <= old_max:
                break
    if not parts:
        return pd.DataFrame()
    x = pd.concat(parts, ignore_index=True).drop_duplicates("datetime", keep="last").sort_values("datetime")
    return x.reset_index(drop=True)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["probe", "kline_full", "snapshot_full", "both_full", "incremental"], default="probe")
    ap.add_argument("--start", default="2018-06-08")
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--out", default=str(DEFAULT_OUT))
    args = ap.parse_args()

    start = max(pd.Timestamp(args.start).normalize(), LISTED)
    end = pd.Timestamp(args.end).normalize()
    if end < start:
        raise SystemExit("end < start")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    kfolder = out / "kline_yearly"
    sfolder = out / "snapshot_yearly"

    log("Selecting best free TDX quote server...")
    with TdxClient.from_best_host(ping_timeout=3.0, heartbeat_interval=15.0) as client:
        log("Connected.")
        daily = fetch_daily_calendar(client, start, end)
        daily.to_csv(out / "daily_trade_calendar.csv", index=False)
        trade_dates = list(pd.to_datetime(daily["date"]).dt.normalize())
        log(f"Trade days: {len(trade_dates)}, {trade_dates[0].date()} -> {trade_dates[-1].date()}")

        # 所有模式都先留一份轻量探测报告，便于以后审计服务器历史深度变化
        kprobe = probe_kline_depth(client, start)
        sprobe = probe_snapshot_depth(client, daily)
        probe = {
            "run_time_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
            "symbol": CODE,
            "requested_start": start.strftime("%Y-%m-%d"),
            "requested_end": end.strftime("%Y-%m-%d"),
            "daily_trade_days": len(trade_dates),
            "min1_kline_probe": kprobe,
            "history_snapshot_probe": sprobe,
            "interpretation": {
                "kline": "True 1-minute OHLCV. Best dataset if reaches 2018.",
                "snapshot": "Historical minute chart price+volume, ~240 points/day; useful if kline depth is shorter, but it is not OHLC.",
            },
        }
        json_dump(out / "probe_report.json", probe)
        log(json.dumps(probe, ensure_ascii=False, indent=2))

        if args.mode == "probe":
            log("Probe finished. No bulk download performed.")
            return

        existing_k = load_yearly(kfolder, f"{CODE}_1m_kline_*.csv")
        existing_s = load_yearly(sfolder, f"{CODE}_1m_snapshot_*.csv")

        kline = existing_k
        snapshot = existing_s

        if args.mode in ("kline_full", "both_full"):
            log("=== FULL TRUE 1M KLINE DOWNLOAD ===")
            kline = fetch_kline_full(client, start, end)
            if kline.empty:
                log("WARNING: no MIN_1 Kline data returned.")
            else:
                save_yearly(kline, kfolder, f"{CODE}_1m_kline")

        if args.mode in ("snapshot_full", "both_full"):
            log("=== FULL HISTORICAL MINUTE SNAPSHOT DOWNLOAD ===")
            snapshot = fetch_snapshot_full(client, trade_dates, existing_s)
            if snapshot.empty:
                log("WARNING: no historical minute snapshot data returned.")
            else:
                save_yearly(snapshot, sfolder, f"{CODE}_1m_snapshot")

        if args.mode == "incremental":
            if not existing_k.empty:
                log("Incremental: updating existing true 1m Kline dataset.")
                kline = incremental_kline(client, existing_k, end)
                save_yearly(kline, kfolder, f"{CODE}_1m_kline")
            if not existing_s.empty:
                log("Incremental: refreshing recent 10 trade days of snapshot dataset.")
                recent = trade_dates[-10:]
                # 移除近期日期，让 fetch_snapshot_full 重新抓取并覆盖
                cutoff = recent[0] if recent else end
                old = existing_s[pd.to_datetime(existing_s["date"]).dt.normalize() < cutoff].copy()
                snapshot = fetch_snapshot_full(client, recent, old)
                save_yearly(snapshot, sfolder, f"{CODE}_1m_snapshot")
            if existing_k.empty and existing_s.empty:
                log("No full dataset exists yet. Incremental mode only wrote probe results.")

    # 连接结束后统一 QC / coverage
    kline = load_yearly(kfolder, f"{CODE}_1m_kline_*.csv")
    snapshot = load_yearly(sfolder, f"{CODE}_1m_snapshot_*.csv")
    qk = qc_kline(kline)
    qs = qc_snapshot(snapshot)
    if not qk.empty:
        qk.to_csv(out / "qc_kline_daily.csv", index=False)
    if not qs.empty:
        qs.to_csv(out / "qc_snapshot_daily.csv", index=False)

    coverage = {
        "symbol": CODE,
        "requested_start": start.strftime("%Y-%m-%d"),
        "requested_end": end.strftime("%Y-%m-%d"),
        "expected_trade_days": len(trade_dates),
        "true_1m_kline_ohlcv": dataset_coverage(kline, len(trade_dates)),
        "historical_minute_snapshot_price_vol": dataset_coverage(snapshot, len(trade_dates)),
        "probe_summary": {
            "kline_reaches_target_start": bool(kprobe.get("reaches_target_start", False)),
            "kline_oldest_available": kprobe.get("oldest_available"),
            "snapshot_reaches_2018": bool(sprobe.get("reaches_2018", False)),
        },
    }
    json_dump(out / "coverage.json", coverage)
    log("=== COVERAGE ===")
    log(json.dumps(coverage, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
