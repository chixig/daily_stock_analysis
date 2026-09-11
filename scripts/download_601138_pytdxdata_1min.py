#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
工业富联 601138｜免费通达信 1分钟历史数据库（pytdxdata MAC通道版）

为什么改用 pytdxdata:
- v0.3.1 起：MIN_1 强制走 MAC K线通道，修复标准通道 1分钟历史深度/分页问题
- v0.3.0 起：历史分时 get_minute(date=YYYYMMDD) 走 MAC 通道，支持完整240点
- 无账号、无 Secret、无付费

模式：
  probe          只探测历史深度（第一次运行）
  kline_full     回填真正 1分钟 OHLCV K线
  snapshot_full  回填历史分时 price+vol 240点
  both_full      两者都回填
  incremental    更新近期 1分钟K线

输出：
data/601138_intraday/pytdxdata_1min/
├── probe_report.json
├── coverage.json
├── daily_trade_calendar.csv
├── kline_yearly/
│   └── 601138_1m_kline_YYYY.csv
├── snapshot_yearly/
│   └── 601138_1m_snapshot_YYYY.csv
├── qc_kline_daily.csv
└── qc_snapshot_daily.csv
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from pytdxdata import TdxData
from pytdxdata.models import KlinePeriod, Market


CODE = "601138"
MARKET = Market.SH
LISTED = pd.Timestamp("2018-06-08")
DEFAULT_OUT = Path("data/601138_intraday/pytdxdata_1min")

# 约8年 * 242交易日 * 240根 ~= 46万根；留足余量
MAX_1M_BARS = 600_000
KLINE_CHUNK = 20_000


def log(msg: str):
    print(msg, flush=True)


def dump_json(path: Path, obj: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(obj, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def objdict(x):
    if is_dataclass(x):
        return asdict(x)
    if hasattr(x, "__dict__"):
        return vars(x)
    if isinstance(x, dict):
        return x
    raise TypeError(type(x))


def bar_datetime(bar) -> pd.Timestamp:
    # pytdxdata SecurityBar 文档声明 year/month/day/hour/minute + datetime 属性
    dt = getattr(bar, "datetime", None)
    if dt is not None:
        return pd.Timestamp(dt)
    d = objdict(bar)
    return pd.Timestamp(
        year=int(d["year"]),
        month=int(d["month"]),
        day=int(d["day"]),
        hour=int(d.get("hour", 0)),
        minute=int(d.get("minute", 0)),
    )


def normalize_kline(bars) -> pd.DataFrame:
    rows = []
    for b in bars or []:
        d = objdict(b)
        dt = bar_datetime(b)
        rows.append({
            "symbol": CODE,
            "datetime": dt,
            "date": dt.normalize(),
            "open": float(d.get("open")),
            "high": float(d.get("high")),
            "low": float(d.get("low")),
            "close": float(d.get("close")),
            "volume": float(d.get("vol", d.get("volume", 0)) or 0),
            "amount": float(d.get("amount", 0) or 0),
            "source": "pytdxdata_mac_min1",
        })
    if not rows:
        return pd.DataFrame()
    x = pd.DataFrame(rows)
    return (
        x.drop_duplicates("datetime", keep="last")
         .sort_values("datetime")
         .reset_index(drop=True)
    )


def minute_times(n: int):
    morning = pd.date_range("09:30", "11:29", freq="1min").strftime("%H:%M").tolist()
    afternoon = pd.date_range("13:00", "14:59", freq="1min").strftime("%H:%M").tolist()
    return (morning + afternoon)[:n]


def normalize_snapshot(items, day: pd.Timestamp) -> pd.DataFrame:
    if not items:
        return pd.DataFrame()
    times = minute_times(len(items))
    rows = []
    for i, m in enumerate(items):
        d = objdict(m)
        hhmm = times[i] if i < len(times) else None
        if hhmm is None:
            continue
        dt = pd.Timestamp(f"{day.strftime('%Y-%m-%d')} {hhmm}")
        rows.append({
            "symbol": CODE,
            "datetime": dt,
            "date": day.normalize(),
            "price": float(d.get("price", 0) or 0),
            "volume": float(d.get("vol", d.get("volume", 0)) or 0),
            "source": "pytdxdata_mac_snapshot",
        })
    return pd.DataFrame(rows)


async def fetch_trade_calendar(td: TdxData, start: pd.Timestamp, end: pd.Timestamp):
    # 日线仅约2000根，直接一次取足
    bars = await td.get_kline(MARKET, CODE, KlinePeriod.DAY, count=3500)
    if not bars:
        return pd.DatetimeIndex([])
    dates = sorted({bar_datetime(b).normalize() for b in bars})
    dates = [d for d in dates if start <= d <= end]
    return pd.DatetimeIndex(dates)


async def probe(td: TdxData, start: pd.Timestamp, end: pd.Timestamp, out: Path):
    report = {
        "symbol": CODE,
        "requested_start": start.strftime("%Y-%m-%d"),
        "requested_end": end.strftime("%Y-%m-%d"),
        "package": "pytdxdata>=0.3.2",
        "kline_offset_probes": [],
        "snapshot_date_probes": [],
    }

    # 1) 真正1分钟OHLCV：按 start 偏移探测深度
    offsets = [0, 50_000, 100_000, 200_000, 300_000, 400_000, 450_000, 480_000, 500_000, 550_000]
    oldest_seen = None

    for off in offsets:
        try:
            bars = await td.get_kline(
                MARKET, CODE, KlinePeriod.MIN_1,
                start=off, count=200
            )
            df = normalize_kline(bars)
            if df.empty:
                rec = {"start_offset": off, "rows": 0}
            else:
                rec = {
                    "start_offset": off,
                    "rows": int(len(df)),
                    "first": str(df["datetime"].min()),
                    "last": str(df["datetime"].max()),
                }
                cur_oldest = df["datetime"].min()
                oldest_seen = cur_oldest if oldest_seen is None else min(oldest_seen, cur_oldest)
            report["kline_offset_probes"].append(rec)
            log(f"KLINE PROBE start={off}: {rec}")
        except Exception as e:
            rec = {"start_offset": off, "rows": 0, "error": repr(e)}
            report["kline_offset_probes"].append(rec)
            log(f"KLINE PROBE ERROR start={off}: {e}")

    if oldest_seen is not None:
        report["kline_oldest_seen"] = str(oldest_seen)
        report["kline_reaches_target_start"] = bool(oldest_seen.normalize() <= start)
    else:
        report["kline_oldest_seen"] = None
        report["kline_reaches_target_start"] = False

    # 2) 历史分时：直接测试关键历史日期（只测试真实交易日）
    calendar = await fetch_trade_calendar(td, start, end)
    pd.DataFrame({"date": calendar}).to_csv(out / "daily_trade_calendar.csv", index=False)

    preferred = [
        pd.Timestamp("2018-06-08"),
        pd.Timestamp("2019-01-02"),
        pd.Timestamp("2020-01-02"),
        pd.Timestamp("2021-01-04"),
        pd.Timestamp("2022-01-04"),
        pd.Timestamp("2023-01-03"),
        pd.Timestamp("2024-01-02"),
        pd.Timestamp("2025-01-02"),
        pd.Timestamp("2026-01-05"),
    ]
    cset = set(calendar)
    probe_dates = []
    for p in preferred:
        if p in cset and p <= end:
            probe_dates.append(p)
        elif len(calendar):
            # 找 >= p 的第一个真实交易日
            later = calendar[calendar >= p]
            if len(later):
                d = later[0]
                if d <= end:
                    probe_dates.append(d)

    # 去重
    probe_dates = sorted(set(probe_dates))

    for d in probe_dates:
        try:
            items = await td.get_minute(MARKET, CODE, date=int(d.strftime("%Y%m%d")))
            rec = {
                "date": d.strftime("%Y-%m-%d"),
                "rows": int(len(items or [])),
            }
            if items:
                first = objdict(items[0])
                last = objdict(items[-1])
                rec["first_price"] = first.get("price")
                rec["last_price"] = last.get("price")
            report["snapshot_date_probes"].append(rec)
            log(f"SNAPSHOT PROBE {d.date()}: {rec}")
        except Exception as e:
            rec = {"date": d.strftime("%Y-%m-%d"), "rows": 0, "error": repr(e)}
            report["snapshot_date_probes"].append(rec)
            log(f"SNAPSHOT PROBE ERROR {d.date()}: {e}")

    report["snapshot_reaches_2018"] = any(
        r.get("date", "").startswith("2018") and r.get("rows", 0) >= 230
        for r in report["snapshot_date_probes"]
    )

    dump_json(out / "probe_report.json", report)
    return report


async def download_kline_full(td, start, end):
    pieces = []
    for off in range(0, MAX_1M_BARS, KLINE_CHUNK):
        log(f"[MIN1] start={off:,}, count={KLINE_CHUNK:,}")
        bars = await td.get_kline(
            MARKET, CODE, KlinePeriod.MIN_1,
            start=off, count=KLINE_CHUNK
        )
        df = normalize_kline(bars)
        log(f"  -> rows={len(df):,}")
        if df.empty:
            break

        pieces.append(df)
        oldest = df["datetime"].min()
        log(f"  -> {oldest} ~ {df['datetime'].max()}")

        if oldest.normalize() <= start:
            break

        # 如果源头返回数显著不足，通常已到历史边界
        if len(df) < min(800, KLINE_CHUNK):
            break

    if not pieces:
        return pd.DataFrame()

    x = (
        pd.concat(pieces, ignore_index=True)
        .drop_duplicates("datetime", keep="last")
        .sort_values("datetime")
    )
    x = x[(x["date"] >= start) & (x["date"] <= end)].reset_index(drop=True)
    return x


async def download_snapshots_full(td, calendar):
    rows = []
    total = len(calendar)

    for i, d in enumerate(calendar, 1):
        try:
            items = await td.get_minute(MARKET, CODE, date=int(d.strftime("%Y%m%d")))
            df = normalize_snapshot(items, d)
            if not df.empty:
                rows.append(df)
            if i == 1 or i % 50 == 0 or i == total:
                log(f"[SNAPSHOT {i}/{total}] {d.date()} rows={len(df)}")
        except Exception as e:
            log(f"[SNAPSHOT {i}/{total}] ERROR {d.date()}: {e}")
        await asyncio.sleep(0.01)

    if not rows:
        return pd.DataFrame()
    return (
        pd.concat(rows, ignore_index=True)
        .drop_duplicates("datetime", keep="last")
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def save_yearly(df, folder: Path, prefix: str):
    folder.mkdir(parents=True, exist_ok=True)
    if df.empty:
        return
    x = df.copy()
    x["datetime"] = pd.to_datetime(x["datetime"])
    for year, g in x.groupby(x["datetime"].dt.year):
        g.sort_values("datetime").to_csv(
            folder / f"{prefix}_{int(year)}.csv",
            index=False
        )


def load_yearly(folder: Path, pattern: str):
    files = sorted(folder.glob(pattern))
    parts = []
    for f in files:
        try:
            d = pd.read_csv(f)
            d["datetime"] = pd.to_datetime(d["datetime"], errors="coerce")
            d["date"] = pd.to_datetime(d["date"], errors="coerce")
            parts.append(d)
        except Exception as e:
            log(f"WARNING read {f}: {e}")
    if not parts:
        return pd.DataFrame()
    return (
        pd.concat(parts, ignore_index=True)
        .dropna(subset=["datetime"])
        .drop_duplicates("datetime", keep="last")
        .sort_values("datetime")
        .reset_index(drop=True)
    )


def qc_kline(df):
    if df.empty:
        return pd.DataFrame()
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"]).dt.normalize()
    q = x.groupby("date", as_index=False).agg(
        bars=("datetime", "count"),
        first=("datetime", "min"),
        last=("datetime", "max"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        amount=("amount", "sum"),
    )
    q["bars_240"] = q["bars"] == 240
    return q


def qc_snapshot(df):
    if df.empty:
        return pd.DataFrame()
    x = df.copy()
    x["date"] = pd.to_datetime(x["date"]).dt.normalize()
    q = x.groupby("date", as_index=False).agg(
        bars=("datetime", "count"),
        first=("datetime", "min"),
        last=("datetime", "max"),
        first_price=("price", "first"),
        high_price=("price", "max"),
        low_price=("price", "min"),
        last_price=("price", "last"),
        volume=("volume", "sum"),
    )
    q["bars_240"] = q["bars"] == 240
    return q


def coverage(kdf, sdf, start, end):
    out = {
        "symbol": CODE,
        "requested_start": start.strftime("%Y-%m-%d"),
        "requested_end": end.strftime("%Y-%m-%d"),
        "kline": {},
        "snapshot": {},
    }

    if not kdf.empty:
        out["kline"] = {
            "rows": int(len(kdf)),
            "trading_days": int(pd.to_datetime(kdf["date"]).nunique()),
            "actual_start": str(pd.to_datetime(kdf["datetime"]).min()),
            "actual_end": str(pd.to_datetime(kdf["datetime"]).max()),
        }
    if not sdf.empty:
        out["snapshot"] = {
            "rows": int(len(sdf)),
            "trading_days": int(pd.to_datetime(sdf["date"]).nunique()),
            "actual_start": str(pd.to_datetime(sdf["datetime"]).min()),
            "actual_end": str(pd.to_datetime(sdf["datetime"]).max()),
        }
    return out


async def main_async(args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    start = max(pd.Timestamp(args.start).normalize(), LISTED)
    end = pd.Timestamp(args.end).normalize()

    async with TdxData() as td:
        if args.mode == "probe":
            rep = await probe(td, start, end, out)
            log(json.dumps(rep, ensure_ascii=False, indent=2, default=str))
            return

        calendar = await fetch_trade_calendar(td, start, end)
        pd.DataFrame({"date": calendar}).to_csv(out / "daily_trade_calendar.csv", index=False)

        kfolder = out / "kline_yearly"
        sfolder = out / "snapshot_yearly"

        existing_k = load_yearly(kfolder, f"{CODE}_1m_kline_*.csv")
        existing_s = load_yearly(sfolder, f"{CODE}_1m_snapshot_*.csv")

        kdf = existing_k
        sdf = existing_s

        if args.mode in ("kline_full", "both_full"):
            kdf = await download_kline_full(td, start, end)
            save_yearly(kdf, kfolder, f"{CODE}_1m_kline")

        if args.mode in ("snapshot_full", "both_full"):
            sdf = await download_snapshots_full(td, calendar)
            save_yearly(sdf, sfolder, f"{CODE}_1m_snapshot")

        if args.mode == "incremental":
            # 对已有K线库回补最近20个交易日，足够处理休市/延迟
            recent = calendar[-20:] if len(calendar) else calendar
            if len(recent):
                inc_start = recent[0]
                # 20交易日 * 240 ≈ 4800，取6000根留余量
                bars = await td.get_kline(
                    MARKET, CODE, KlinePeriod.MIN_1,
                    start=0, count=6000
                )
                inc = normalize_kline(bars)
                inc = inc[(inc["date"] >= inc_start) & (inc["date"] <= end)]
                if not inc.empty:
                    if not existing_k.empty:
                        kdf = (
                            pd.concat([existing_k, inc], ignore_index=True)
                            .drop_duplicates("datetime", keep="last")
                            .sort_values("datetime")
                            .reset_index(drop=True)
                        )
                    else:
                        kdf = inc
                    save_yearly(kdf, kfolder, f"{CODE}_1m_kline")

        qk = qc_kline(kdf)
        qs = qc_snapshot(sdf)
        if not qk.empty:
            qk.to_csv(out / "qc_kline_daily.csv", index=False)
        if not qs.empty:
            qs.to_csv(out / "qc_snapshot_daily.csv", index=False)

        cov = coverage(kdf, sdf, start, end)
        dump_json(out / "coverage.json", cov)
        log(json.dumps(cov, ensure_ascii=False, indent=2))


def main():
    p = argparse.ArgumentParser()
    p.add_argument(
        "--mode",
        choices=["probe", "kline_full", "snapshot_full", "both_full", "incremental"],
        default="probe",
    )
    p.add_argument("--start", default="2018-06-08")
    p.add_argument("--end", default=date.today().isoformat())
    p.add_argument("--out", default=str(DEFAULT_OUT))
    args = p.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
