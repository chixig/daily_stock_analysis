#!/usr/bin/env python3
"""
A股红利核心股 PIT 动态 Top10 V2.1.1 — pandas.NA routing hotfix

This is a minimal hotfix layered on top of V2.1.

It DOES NOT change:
- V2 model weights
- industry-routing keyword definitions
- qualification thresholds
- route caps
- BankQV
- return/cost logic
- BaoStock checkpoint schema

It ONLY makes route_from_metadata() robust to pandas.NA / NaN metadata.
The V2.1 resumable BaoStock cache is reused unchanged.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
V21_PATH = HERE / "dividend_pit_top10_v2_1.py"

spec = importlib.util.spec_from_file_location("pit_v21", V21_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot import {V21_PATH}")

v21 = importlib.util.module_from_spec(spec)
sys.modules["pit_v21"] = v21
spec.loader.exec_module(v21)

v2 = v21.v2


def _safe_text(value) -> str:
    """
    Convert pandas/NumPy missing scalar metadata to an empty string
    without ever asking pandas.NA for a boolean value.
    """
    if value is None:
        return ""
    try:
        missing = pd.isna(value)
        # Metadata cells here are expected to be scalars.  Be defensive in case
        # an array-like object ever slips through.
        if isinstance(missing, bool):
            if missing:
                return ""
        elif hasattr(missing, "item") and bool(missing.item()):
            return ""
    except Exception:
        pass
    return str(value)


def route_from_metadata_safe(row) -> str:
    code = _safe_text(row.get("code6", ""))
    if code in v2.BANK_CODES:
        return "BANK"

    industry = _safe_text(row.get("industry", ""))
    name = _safe_text(row.get("name", ""))
    text = industry + " " + name

    # EXACT SAME routing keywords/order as V2.
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


def _self_test():
    # Exact failure mode from the V2.1 traceback.
    r = pd.Series({"code6": "600000", "industry": pd.NA, "name": pd.NA})
    assert route_from_metadata_safe(r) == "BANK"

    r = pd.Series({"code6": "600001", "industry": pd.NA, "name": pd.NA})
    assert route_from_metadata_safe(r) == "STABLE"

    r = pd.Series({"code6": "600002", "industry": "水务", "name": pd.NA})
    assert route_from_metadata_safe(r) == "UTILITY"

    r = pd.Series({"code6": "600003", "industry": pd.NA, "name": "某港口"})
    assert route_from_metadata_safe(r) == "TRANSPORT"

    print("V2.1.1 route metadata self-test: PASS", flush=True)


def main():
    _self_test()

    # Patch only the pandas.NA-unsafe metadata conversion.
    v2.route_from_metadata = route_from_metadata_safe

    # V2.1 main then patches ONLY the BaoStock retrieval layer and calls V2 main.
    # Therefore both fixes are active while all investment-model logic remains frozen.
    print(
        "V2.1.1 active: V2 model frozen; V2.1 resumable data layer + pandas.NA route hotfix.",
        flush=True,
    )
    v21.main()


if __name__ == "__main__":
    main()
