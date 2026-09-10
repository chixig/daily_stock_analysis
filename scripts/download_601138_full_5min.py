#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import time
from datetime import date
from pathlib import Path

import baostock as bs
import pandas as pd

CODE = "sh.601138"
SYMBOL = "601138"
DEFAULT_START = "2018-06-08"
DEFAULT_OUT = "data/601138_intraday/5min"

MINUTE_FIELDS = "date,time,code,open,high,low,close,volume,amount,adjustflag"
DAILY_FIELDS = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,pctChg"


def rs_to_df(rs) -> pd.DataFrame:
    rows = []
    while rs.error_code == "0" and rs.next():
        rows.append(rs.get_row_data())
    if rs.error_code != "0":
        raise RuntimeError(f"BaoStock error {rs.error_code}: {rs.error_msg}")
    return pd.DataFrame(rows, columns=rs.fields)


def fetch_5m(start_date: str, end_date: str, retries: int = 3) -> pd.DataFrame:
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            rs = bs.query_history_k_data_plus(
                CODE,
                MINUTE_FIELDS,
                start_date=start_date,
                end_date=end_date,
                frequency="5",
                adjustflag="3",
            )
            df = rs_to_df(rs)
            if df.empty:
                return df

            for c in ["open", "high", "low", "close", "volume", "amount"]:
                df[c] = pd.to_numeric(df[c], errors="coerce")

            df["datetime"] = pd.to_datetime(
                df["time"].astype(str).str.slice(0, 14),
                format="%Y%m%d%H%M%S",
                errors="coerce",
            )
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            return (
                df.dropna(subset=["date", "datetime", "open", "high", "low", "close"])
                  .drop_duplicates(subset=["date", "time", "code"], keep="last")
                  .sort_values(["date", "datetime"])
                  .reset_index(drop=True)
            )
        except Exception as e:
            last_error = e
            if attempt < retries:
                time.sleep(attempt * 2)
    raise RuntimeError(f"fetch_5m failed {start_date}~{end_date}: {last_error}")


def fetch_daily(start_date: str, end_date: str) -> pd.DataFrame:
    rs = bs.query_history_k_data_plus(
        CODE,
        DAILY_FIELDS,
        start_date=start_date,
        end_date=end_date,
        frequency="d",
        adjustflag="3",
    )
    df = rs_to_df(rs)
    if df.empty:
        return df

    for c in ["open", "high", "low", "close", "preclose", "volume", "amount", "pctChg"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)


def year_ranges(start_date: pd.Timestamp, end_date: pd.Timestamp):
    for year in range(start_date.year, end_date.year + 1):
        st = max(start_date, pd.Timestamp(f"{year}-01-01"))
        en = min(end_date, pd.Timestamp(f"{year}-12-31"))
        yield year, st.strftime("%Y-%m-%d"), en.strftime("%Y-%m-%d")


def build_qc(minute_df: pd.DataFrame, daily_df: pd.DataFrame) -> pd.DataFrame:
    if minute_df.empty:
        return pd.DataFrame()

    g = minute_df.groupby("date", as_index=False).agg(
        bars=("datetime", "count"),
        minute_open=("open", "first"),
        minute_high=("high", "max"),
        minute_low=("low", "min"),
        minute_close=("close", "last"),
        minute_volume=("volume", "sum"),
        minute_amount=("amount", "sum"),
    )

    d = daily_df[["date", "open", "high", "low", "close", "volume", "amount"]].copy()
    d = d.rename(columns={
        "open": "daily_open",
        "high": "daily_high",
        "low": "daily_low",
        "close": "daily_close",
        "volume": "daily_volume",
        "amount": "daily_amount",
    })

    qc = g.merge(d, on="date", how="left")
    qc["open_diff"] = qc["minute_open"] - qc["daily_open"]
    qc["close_diff"] = qc["minute_close"] - qc["daily_close"]
    qc["high_diff"] = qc["minute_high"] - qc["daily_high"]
    qc["low_diff"] = qc["minute_low"] - qc["daily_low"]

    qc["bars_ok"] = qc["bars"].between(46, 48)
    qc["open_ok_003"] = qc["open_diff"].abs() <= 0.03
    qc["close_ok_003"] = qc["close_diff"].abs() <= 0.03
    qc["hard_qc_ok"] = qc["bars_ok"] & qc["open_ok_003"] & qc["close_ok_003"]
    qc["extreme_warning"] = (
        (qc["high_diff"].abs() > 0.03) |
        (qc["low_diff"].abs() > 0.03)
    )
    return qc.sort_values("date").reset_index(drop=True)


def write_outputs(all_5m: pd.DataFrame, daily: pd.DataFrame, out_dir: Path,
                  requested_start: str, requested_end: str):
    out_dir.mkdir(parents=True, exist_ok=True)
    yearly_dir = out_dir / "yearly"
    yearly_dir.mkdir(parents=True, exist_ok=True)

    if all_5m.empty:
        coverage = {
            "symbol": SYMBOL,
            "frequency": "5min",
            "requested_start": requested_start,
            "requested_end": requested_end,
            "actual_start": None,
            "actual_end": None,
            "rows": 0,
            "trading_days": 0,
            "status": "NO_MINUTE_DATA_RETURNED",
        }
        (out_dir / "coverage.json").write_text(
            json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return

    all_5m = all_5m.sort_values(["date", "datetime"]).reset_index(drop=True)
    all_5m["year"] = all_5m["date"].dt.year

    for year, g in all_5m.groupby("year"):
        g.drop(columns=["year"]).to_csv(
            yearly_dir / f"{SYMBOL}_5min_{int(year)}.csv", index=False
        )

    all_save = all_5m.drop(columns=["year"]).copy()
    all_save.to_csv(out_dir / f"{SYMBOL}_5min_all.csv", index=False)
    daily.to_csv(out_dir / f"{SYMBOL}_daily_raw.csv", index=False)

    qc = build_qc(all_save, daily)
    qc.to_csv(out_dir / "qc_daily.csv", index=False)

    per_year = []
    for year, g in all_save.groupby(all_save["date"].dt.year):
        per_year.append({
            "year": int(year),
            "rows": int(len(g)),
            "trading_days": int(g["date"].nunique()),
        })

    coverage = {
        "symbol": SYMBOL,
        "code": CODE,
        "frequency": "5min",
        "adjustflag": "3_unadjusted",
        "requested_start": requested_start,
        "requested_end": requested_end,
        "actual_start": all_save["date"].min().strftime("%Y-%m-%d"),
        "actual_end": all_save["date"].max().strftime("%Y-%m-%d"),
        "rows": int(len(all_save)),
        "trading_days": int(all_save["date"].nunique()),
        "normal_48bar_days": int((qc["bars"] == 48).sum()) if not qc.empty else 0,
        "hard_qc_ok_days": int(qc["hard_qc_ok"].sum()) if not qc.empty else 0,
        "extreme_warning_days": int(qc["extreme_warning"].sum()) if not qc.empty else 0,
        "per_year": per_year,
        "notes": [
            "BaoStock does not provide 1-minute bars; this dataset is 5-minute.",
            "High/Low differences versus daily bars are warnings only and are not deleted.",
            "Actual coverage may be shorter than requested coverage because minute-history availability is vendor-limited."
        ],
    }
    (out_dir / "coverage.json").write_text(
        json.dumps(coverage, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print(json.dumps(coverage, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=DEFAULT_START)
    ap.add_argument("--end", default=date.today().isoformat())
    ap.add_argument("--out", default=DEFAULT_OUT)
    args = ap.parse_args()

    start_ts = pd.Timestamp(args.start)
    end_ts = pd.Timestamp(args.end)
    if end_ts < start_ts:
        raise ValueError("end must be >= start")

    login = bs.login()
    if login.error_code != "0":
        raise RuntimeError(f"BaoStock login failed {login.error_code}: {login.error_msg}")

    try:
        pieces = []
        ranges = list(year_ranges(start_ts, end_ts))
        for i, (year, st, en) in enumerate(ranges, 1):
            print(f"[{i}/{len(ranges)}] Fetch {year}: {st} ~ {en}")
            df = fetch_5m(st, en)
            print(f"  rows={len(df)}, days={df['date'].nunique() if not df.empty else 0}")
            if not df.empty:
                pieces.append(df)
            time.sleep(0.3)

        if pieces:
            all_5m = (
                pd.concat(pieces, ignore_index=True)
                  .drop_duplicates(subset=["date", "time", "code"], keep="last")
                  .sort_values(["date", "datetime"])
                  .reset_index(drop=True)
            )
        else:
            all_5m = pd.DataFrame()

        daily = fetch_daily(args.start, args.end)
        write_outputs(all_5m, daily, Path(args.out), args.start, args.end)
    finally:
        bs.logout()


if __name__ == "__main__":
    main()
