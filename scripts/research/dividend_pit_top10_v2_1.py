#!/usr/bin/env python3
"""
A股红利核心股 PIT 动态 Top10 V2.1 — Resumable BaoStock Data Layer

This file intentionally DOES NOT change any V2 model weights, thresholds,
industry-routing rules, portfolio caps, or return logic.

V2.1 changes only the 2012-2017 BaoStock data-engineering layer:
1) socket error => logout/login/retry with exponential backoff;
2) proactive reconnect after a bounded number of successful requests;
3) durable checkpoints for code-year fundamentals and signal-date valuations;
4) reruns skip completed work;
5) circuit breaker stops a broken session instead of looping for hours;
6) explicit QA gates reject incomplete network retrieval before backtest;
7) V2's original main() is reused after monkey-patching only
   fetch_early_baostock().
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
V2_PATH = HERE / "dividend_pit_top10_v2.py"

spec = importlib.util.spec_from_file_location("pit_v2", V2_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import {V2_PATH}")
v2 = importlib.util.module_from_spec(spec)
sys.modules["pit_v2"] = v2
spec.loader.exec_module(v2)

ROOT = Path(os.environ.get("OUT_DIR", "_dividend_pit_top10_v2_1"))
OUT = ROOT / "out"
REPORTS = ROOT / "reports"
CACHE = Path(os.environ.get("PIT_CACHE_DIR", str(ROOT / "cache" / "baostock_early_v2_1")))
for p in [OUT, REPORTS, CACHE]:
    p.mkdir(parents=True, exist_ok=True)

ANNUAL_CACHE = CACHE / "annual_rows.csv.gz"
PAIR_STATUS_CACHE = CACHE / "pair_status.json"
VALUATION_CACHE = CACHE / "valuation_map.json"
VALUATION_STATUS_CACHE = CACHE / "valuation_status.json"
CACHE_META = CACHE / "cache_meta.json"

MAX_RETRIES = int(os.environ.get("BS_MAX_RETRIES", "5"))
PROACTIVE_RECONNECT_EVERY = int(os.environ.get("BS_RECONNECT_EVERY", "120"))
CHECKPOINT_EVERY_PAIRS = int(os.environ.get("BS_CHECKPOINT_EVERY_PAIRS", "25"))
CHECKPOINT_EVERY_VALS = int(os.environ.get("BS_CHECKPOINT_EVERY_VALS", "100"))
CIRCUIT_BREAKER_FULL_FAILURES = int(os.environ.get("BS_CIRCUIT_BREAKER", "3"))
MAX_UNRESOLVED_RATE = float(os.environ.get("BS_MAX_UNRESOLVED_RATE", "0.03"))
BACKOFF = [2, 4, 8, 16, 30]


def log(*args):
    print(*args, flush=True)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Corrupt checkpoint {path}: {exc}") from exc


def _atomic_write_text(path: Path, text: str):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def _save_json(path: Path, obj):
    _atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True))


def _load_annual_rows() -> Dict[str, dict]:
    if not ANNUAL_CACHE.exists():
        return {}
    df = pd.read_csv(
        ANNUAL_CACHE,
        dtype={"code6": "string"},
        parse_dates=["pubDate", "statDate"],
    )
    out = {}
    for r in df.to_dict("records"):
        code = str(r["code6"]).zfill(6)
        fy = int(r["financial_year"])
        out[f"{code}|{fy}"] = r
    return out


def _save_annual_rows(rows: Dict[str, dict]):
    cols = [
        "code6", "financial_year", "pubDate", "statDate", "roe_pct",
        "net_profit", "revenue", "eps", "total_share", "debt_assets", "cfo_ni",
    ]
    if rows:
        df = pd.DataFrame(list(rows.values()))
        for c in cols:
            if c not in df.columns:
                df[c] = np.nan
        df = df[cols].sort_values(["code6", "financial_year"])
    else:
        df = pd.DataFrame(columns=cols)
    tmp = ANNUAL_CACHE.with_suffix(".csv.gz.tmp")
    df.to_csv(tmp, index=False, compression="gzip")
    tmp.replace(ANNUAL_CACHE)


def _valuation_key(year: int, code: str) -> str:
    return f"{int(year)}|{str(code).zfill(6)}"


def _pair_key(code: str, fy: int) -> str:
    return f"{str(code).zfill(6)}|{int(fy)}"


def _checkpoint(annual_rows, pair_status, val_map_json, val_status, meta_extra=None):
    _save_annual_rows(annual_rows)
    _save_json(PAIR_STATUS_CACHE, pair_status)
    _save_json(VALUATION_CACHE, val_map_json)
    _save_json(VALUATION_STATUS_CACHE, val_status)
    meta = {
        "version": "2.1",
        "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
        "annual_rows": len(annual_rows),
        "pair_status": len(pair_status),
        "valuation_rows": len(val_map_json),
        "valuation_status": len(val_status),
    }
    if meta_extra:
        meta.update(meta_extra)
    _save_json(CACHE_META, meta)


def fetch_early_baostock_v21(
    market: pd.DataFrame, q
) -> Tuple[Dict[int, pd.DataFrame], Dict[Tuple[int, str], dict]]:
    import baostock as bs

    plan = v2.early_candidate_plan(market)
    pair_need = set()
    signal_need = []
    for y, codes in plan.items():
        sig, _ = q.may_dates(y)
        for code in codes:
            code = str(code).zfill(6)
            signal_need.append((int(y), code, sig))
            for fy in range(y - 5, y):
                pair_need.add((code, int(fy)))

    pair_need = sorted(pair_need)
    signal_need = sorted(signal_need, key=lambda x: (x[0], x[1]))
    log(
        "V2.1 BaoStock plan:",
        f"pairs={len(pair_need):,}",
        f"valuations={len(signal_need):,}",
        f"cache={CACHE}",
    )

    annual_rows = _load_annual_rows()
    pair_status = _load_json(PAIR_STATUS_CACHE, {})
    val_map_json = _load_json(VALUATION_CACHE, {})
    val_status = _load_json(VALUATION_STATUS_CACHE, {})

    # Keep only statuses that are meaningful to the current plan.
    needed_pair_keys = {_pair_key(c, y) for c, y in pair_need}
    needed_val_keys = {_valuation_key(y, c) for y, c, _ in signal_need}
    pair_status = {k: v for k, v in pair_status.items() if k in needed_pair_keys}
    val_status = {k: v for k, v in val_status.items() if k in needed_val_keys}
    val_map_json = {k: v for k, v in val_map_json.items() if k in needed_val_keys}

    state = {
        "requests_since_login": 0,
        "full_failure_streak": 0,
        "total_reconnects": 0,
        "retry_events": 0,
    }

    def login_or_raise(reason: str):
        try:
            bs.logout()
        except Exception:
            pass
        delay = 1 if reason == "initial" else 2
        if delay:
            time.sleep(delay)
        lg = bs.login()
        if lg.error_code != "0":
            raise RuntimeError(
                f"BaoStock login failed after {reason}: "
                f"{lg.error_code} {lg.error_msg}"
            )
        state["requests_since_login"] = 0
        if reason != "initial":
            state["total_reconnects"] += 1
        log("BaoStock login OK", f"reason={reason}", f"reconnects={state['total_reconnects']}")

    def maybe_proactive_reconnect():
        if state["requests_since_login"] >= PROACTIVE_RECONNECT_EVERY:
            login_or_raise("proactive")

    def query_with_reconnect(label: str, fn):
        last = None
        for attempt in range(1, MAX_RETRIES + 1):
            maybe_proactive_reconnect()
            try:
                out = fn()
                state["requests_since_login"] += 1
                state["full_failure_streak"] = 0
                return out
            except Exception as exc:
                last = exc
                state["retry_events"] += 1
                wait = BACKOFF[min(attempt - 1, len(BACKOFF) - 1)]
                log(
                    f"BaoStock retry {attempt}/{MAX_RETRIES}",
                    label,
                    type(exc).__name__,
                    str(exc)[:180],
                    f"backoff={wait}s",
                )
                try:
                    login_or_raise(f"error:{label}")
                except Exception as login_exc:
                    log("BaoStock relogin failed", label, repr(login_exc)[:220])
                time.sleep(wait)
        state["full_failure_streak"] += 1
        if state["full_failure_streak"] >= CIRCUIT_BREAKER_FULL_FAILURES:
            raise RuntimeError(
                "BaoStock circuit breaker opened after "
                f"{state['full_failure_streak']} consecutive fully failed requests; "
                f"last={label}: {last!r}"
            )
        raise RuntimeError(last)

    login_or_raise("initial")

    unresolved_pairs = []
    completed_pairs_this_run = 0

    for idx, (code, fy) in enumerate(pair_need, 1):
        key = _pair_key(code, fy)
        if pair_status.get(key, {}).get("complete") is True:
            continue

        parts = {}
        pair_errors = []
        for kind in ["profit", "balance", "cash"]:
            label = f"{kind}:{code}:{fy}"

            def _call(kind=kind, code=code, fy=fy):
                if kind == "profit":
                    return v2.bs_collect(
                        bs.query_profit_data(
                            code=v2.bs_code(code), year=int(fy), quarter=4
                        )
                    )
                if kind == "balance":
                    return v2.bs_collect(
                        bs.query_balance_data(
                            code=v2.bs_code(code), year=int(fy), quarter=4
                        )
                    )
                return v2.bs_collect(
                    bs.query_cash_flow_data(
                        code=v2.bs_code(code), year=int(fy), quarter=4
                    )
                )

            try:
                d = query_with_reconnect(label, _call)
            except Exception as exc:
                pair_errors.append({"kind": kind, "error": repr(exc)})
                d = pd.DataFrame()

            if not d.empty:
                d["pubDate"] = pd.to_datetime(d["pubDate"], errors="coerce")
                d["statDate"] = pd.to_datetime(d["statDate"], errors="coerce")
                d = d[
                    d["statDate"].dt.month.eq(12)
                    & d["statDate"].dt.day.eq(31)
                ]
                if not d.empty:
                    d = d.sort_values("pubDate").iloc[0]
            parts[kind] = d

        if pair_errors:
            pair_status[key] = {
                "complete": False,
                "errors": pair_errors,
                "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
            }
            unresolved_pairs.append((code, fy))
        else:
            pair_status[key] = {
                "complete": True,
                "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
            }
            p = parts["profit"]
            if isinstance(p, pd.Series):
                b = (
                    parts["balance"]
                    if isinstance(parts["balance"], pd.Series)
                    else pd.Series(dtype=object)
                )
                c = (
                    parts["cash"]
                    if isinstance(parts["cash"], pd.Series)
                    else pd.Series(dtype=object)
                )
                roe = v2.normalize_ratio(p.get("roeAvg", np.nan))
                roe_pct = roe * 100 if np.isfinite(roe) and abs(roe) <= 2 else roe
                liab = v2.normalize_ratio(b.get("liabilityToAsset", np.nan))
                if np.isfinite(liab) and liab > 2:
                    liab /= 100.0
                cfo_np = v2.normalize_ratio(c.get("CFOToNP", np.nan))
                annual_rows[key] = {
                    "code6": code,
                    "financial_year": int(fy),
                    "pubDate": p.get("pubDate", pd.NaT),
                    "statDate": p.get("statDate", pd.NaT),
                    "roe_pct": roe_pct,
                    "net_profit": pd.to_numeric(
                        p.get("netProfit", np.nan), errors="coerce"
                    ),
                    "revenue": pd.to_numeric(
                        p.get("MBRevenue", p.get("operatingRevenue", np.nan)),
                        errors="coerce",
                    ),
                    "eps": pd.to_numeric(p.get("epsTTM", np.nan), errors="coerce"),
                    "total_share": pd.to_numeric(
                        p.get("totalShare", np.nan), errors="coerce"
                    ),
                    "debt_assets": liab,
                    "cfo_ni": cfo_np,
                }

        completed_pairs_this_run += 1
        if completed_pairs_this_run % CHECKPOINT_EVERY_PAIRS == 0:
            _checkpoint(
                annual_rows,
                pair_status,
                val_map_json,
                val_status,
                {
                    "phase": "annual",
                    "pair_index": idx,
                    "pair_total": len(pair_need),
                    **state,
                },
            )
            log(
                "Checkpoint annual",
                f"processed_this_run={completed_pairs_this_run:,}",
                f"overall_status={len(pair_status):,}/{len(pair_need):,}",
            )

    # Retry unresolved pair keys from previous/current passes once more as a whole
    # is intentionally NOT done here: each query already has MAX_RETRIES plus reconnect.
    unresolved_pair_keys = [
        k for k in needed_pair_keys
        if not pair_status.get(k, {}).get("complete")
    ]
    pair_unresolved_rate = len(unresolved_pair_keys) / max(1, len(needed_pair_keys))

    completed_vals_this_run = 0
    for idx, (year, code, sig) in enumerate(signal_need, 1):
        key = _valuation_key(year, code)
        if val_status.get(key, {}).get("complete") is True:
            continue
        ds = sig.strftime("%Y-%m-%d")
        label = f"valuation:{year}:{code}:{ds}"

        def _call_val(code=code, ds=ds):
            return v2.bs_collect(
                bs.query_history_k_data_plus(
                    v2.bs_code(code),
                    "date,code,peTTM,pbMRQ,isST",
                    start_date=ds,
                    end_date=ds,
                    frequency="d",
                    adjustflag="3",
                )
            )

        try:
            d = query_with_reconnect(label, _call_val)
            val_status[key] = {
                "complete": True,
                "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
            }
            if not d.empty:
                r = d.iloc[-1]
                val_map_json[key] = {
                    "pe_ttm_bs": (
                        None
                        if pd.isna(pd.to_numeric(r.get("peTTM", np.nan), errors="coerce"))
                        else float(pd.to_numeric(r.get("peTTM"), errors="coerce"))
                    ),
                    "pb_bs": (
                        None
                        if pd.isna(pd.to_numeric(r.get("pbMRQ", np.nan), errors="coerce"))
                        else float(pd.to_numeric(r.get("pbMRQ"), errors="coerce"))
                    ),
                    "isST_bs": str(r.get("isST", "0")) == "1",
                }
        except Exception as exc:
            val_status[key] = {
                "complete": False,
                "error": repr(exc),
                "updated_at_utc": pd.Timestamp.utcnow().isoformat(),
            }

        completed_vals_this_run += 1
        if completed_vals_this_run % CHECKPOINT_EVERY_VALS == 0:
            _checkpoint(
                annual_rows,
                pair_status,
                val_map_json,
                val_status,
                {
                    "phase": "valuation",
                    "valuation_index": idx,
                    "valuation_total": len(signal_need),
                    **state,
                },
            )
            log(
                "Checkpoint valuation",
                f"processed_this_run={completed_vals_this_run:,}",
                f"overall_status={len(val_status):,}/{len(signal_need):,}",
            )

    try:
        bs.logout()
    except Exception:
        pass

    _checkpoint(
        annual_rows,
        pair_status,
        val_map_json,
        val_status,
        {
            "phase": "complete",
            "pair_total": len(pair_need),
            "valuation_total": len(signal_need),
            **state,
        },
    )

    unresolved_val_keys = [
        k for k in needed_val_keys
        if not val_status.get(k, {}).get("complete")
    ]
    val_unresolved_rate = len(unresolved_val_keys) / max(1, len(needed_val_keys))

    qa = {
        "version": "2.1",
        "pair_total": len(needed_pair_keys),
        "pair_complete": len(needed_pair_keys) - len(unresolved_pair_keys),
        "pair_unresolved": len(unresolved_pair_keys),
        "pair_unresolved_rate": pair_unresolved_rate,
        "valuation_total": len(needed_val_keys),
        "valuation_complete": len(needed_val_keys) - len(unresolved_val_keys),
        "valuation_unresolved": len(unresolved_val_keys),
        "valuation_unresolved_rate": val_unresolved_rate,
        "annual_rows": len(annual_rows),
        "valuation_rows": len(val_map_json),
        **state,
    }
    _save_json(REPORTS / "baostock_v2_1_data_qa.json", qa)
    _save_json(
        REPORTS / "baostock_early_failures.json",
        {
            "unresolved_pairs": unresolved_pair_keys[:500],
            "unresolved_valuations": unresolved_val_keys[:500],
            "qa": qa,
        },
    )
    log("BaoStock V2.1 QA", json.dumps(qa, ensure_ascii=False))

    # Hard data-quality gate. No backtest is allowed on a badly incomplete download.
    if pair_unresolved_rate > MAX_UNRESOLVED_RATE:
        raise RuntimeError(
            f"BaoStock annual unresolved rate {pair_unresolved_rate:.2%} "
            f"> {MAX_UNRESOLVED_RATE:.2%}"
        )
    if val_unresolved_rate > MAX_UNRESOLVED_RATE:
        raise RuntimeError(
            f"BaoStock valuation unresolved rate {val_unresolved_rate:.2%} "
            f"> {MAX_UNRESOLVED_RATE:.2%}"
        )

    # Materialize the exact V2-compatible outputs.
    if annual_rows:
        ann = pd.DataFrame(list(annual_rows.values()))
        ann["code6"] = ann["code6"].astype("string").str.zfill(6)
        ann["financial_year"] = pd.to_numeric(
            ann["financial_year"], errors="coerce"
        ).astype("Int64")
        ann["pubDate"] = pd.to_datetime(ann["pubDate"], errors="coerce")
        ann["statDate"] = pd.to_datetime(ann["statDate"], errors="coerce")
    else:
        ann = pd.DataFrame(
            columns=[
                "code6", "financial_year", "pubDate", "statDate", "roe_pct",
                "net_profit", "revenue", "eps", "total_share", "debt_assets",
                "cfo_ni",
            ]
        )
    ann.to_csv(
        OUT / "baostock_early_annual.csv.gz",
        index=False,
        compression="gzip",
    )

    val_map = {}
    for key, d in val_map_json.items():
        y, code = key.split("|", 1)
        val_map[(int(y), code)] = {
            "pe_ttm_bs": np.nan if d.get("pe_ttm_bs") is None else d.get("pe_ttm_bs"),
            "pb_bs": np.nan if d.get("pb_bs") is None else d.get("pb_bs"),
            "isST_bs": bool(d.get("isST_bs", False)),
        }

    fin_by_year = {}
    fin_cols = [
        "code6", "fin_year_latest", "annual_count", "roe_median_5y",
        "roe_std_5y", "profit_cagr", "revenue_cagr", "cfo_ni_median_3y",
        "positive_profit_3y", "positive_cfo_3y", "debt_assets_latest",
        "eps_latest", "shares_estimate_latest", "equity_per_share_latest",
        "profit_median_5y", "profit_latest", "profit_peak_ratio",
    ]
    coverage_by_year = {}

    for y in range(v2.START_YEAR, v2.EARLY_LAST_YEAR + 1):
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
            g = (
                g.sort_values("financial_year")
                .drop_duplicates("financial_year", keep="first")
            )
            latest = g[g["financial_year"].eq(y - 1)]
            if latest.empty:
                continue
            last = latest.iloc[-1]
            last3 = g.tail(3)
            profits = pd.to_numeric(g["net_profit"], errors="coerce")
            revenues = pd.to_numeric(g["revenue"], errors="coerce")
            roe = pd.to_numeric(g["roe_pct"], errors="coerce")
            median_profit = (
                float(profits.median()) if profits.notna().any() else np.nan
            )
            latest_profit = (
                float(last["net_profit"])
                if pd.notna(last["net_profit"])
                else np.nan
            )
            peak = (
                latest_profit / median_profit
                if np.isfinite(latest_profit)
                and np.isfinite(median_profit)
                and median_profit > 0
                else np.nan
            )
            shares = (
                float(last["total_share"])
                if pd.notna(last["total_share"])
                else np.nan
            )
            rows.append(
                {
                    "code6": code,
                    "fin_year_latest": int(last["financial_year"]),
                    "annual_count": int(g["financial_year"].nunique()),
                    "roe_median_5y": (
                        float(roe.median()) if roe.notna().any() else np.nan
                    ),
                    "roe_std_5y": (
                        float(roe.std(ddof=1))
                        if roe.notna().sum() >= 2
                        else np.nan
                    ),
                    "profit_cagr": v2.cagr3(profits.tail(3)),
                    "revenue_cagr": v2.cagr3(revenues.tail(3)),
                    "cfo_ni_median_3y": float(
                        pd.to_numeric(last3["cfo_ni"], errors="coerce").median()
                    ),
                    "positive_profit_3y": int(
                        (pd.to_numeric(last3["net_profit"], errors="coerce") > 0).sum()
                    ),
                    "positive_cfo_3y": int(
                        (pd.to_numeric(last3["cfo_ni"], errors="coerce") > 0).sum()
                    ),
                    "debt_assets_latest": (
                        float(last["debt_assets"])
                        if pd.notna(last["debt_assets"])
                        else np.nan
                    ),
                    "eps_latest": (
                        float(last["eps"]) if pd.notna(last["eps"]) else np.nan
                    ),
                    "shares_estimate_latest": shares,
                    "equity_per_share_latest": np.nan,
                    "profit_median_5y": median_profit,
                    "profit_latest": latest_profit,
                    "profit_peak_ratio": peak,
                }
            )

        fin_by_year[y] = pd.DataFrame(rows, columns=fin_cols)
        coverage_by_year[str(y)] = {
            "candidate_count": len(codes),
            "pit_financial_rows": len(fin_by_year[y]),
            "pit_financial_coverage": (
                len(fin_by_year[y]) / len(codes) if codes else 0.0
            ),
        }

    _save_json(REPORTS / "baostock_v2_1_pit_coverage_by_year.json", coverage_by_year)
    log("PIT coverage by year", json.dumps(coverage_by_year, ensure_ascii=False))

    return fin_by_year, val_map


def main():
    # Monkey-patch ONLY the failing data retrieval layer.
    v2.fetch_early_baostock = fetch_early_baostock_v21
    log("V2.1 active: model logic frozen; only BaoStock data layer replaced.")
    v2.main()


if __name__ == "__main__":
    main()
