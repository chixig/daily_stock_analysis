---
license: apache-2.0
annotations_creators:
- no-annotation
source_datasets:
- original
task_categories:
- time-series-forecasting
tags:
- finance
- stock-market
- ohlcv
- minute-bars
- china
- tabular
- timeseries
- parquet
pretty_name: China A-Share Equities 1-Minute OHLCV
size_categories:
- 1B<n<10B
configs:
- config_name: bars_sample
  default: true
  data_files:
  - split: train
    path: viewer/bars_sample.parquet
- config_name: instrument_coverage
  data_files:
  - split: train
    path: viewer/instrument_coverage.parquet
- config_name: missing_intervals
  data_files:
  - split: train
    path: viewer/missing_intervals.parquet
- config_name: no_bar_day_classification
  data_files:
  - split: train
    path: viewer/no_bar_day_classification.parquet
- config_name: market_calendar
  data_files:
  - split: train
    path: viewer/market_calendar.parquet
- config_name: absent_instruments
  data_files:
  - split: train
    path: viewer/absent_instruments.parquet
---

# China A-Share Equities 1-Minute OHLCV

Minute-level OHLCV bars for exchange-listed Chinese A-share equities. The release uses a stable Parquet schema, one canonical file per instrument, and machine-readable coverage reports.

## Dataset summary

This snapshot contains **3,475,824,481 rows** for **5,795 instruments** across China A-share equities on the Shanghai, Shenzhen, and Beijing exchanges. It covers **2010-01-04 09:30:00** through **2026-08-07 10:21:00**. Prices are unadjusted. Volume is stored in shares, turnover in CNY, and timezone-naive timestamps are interpreted as **Asia/Singapore (UTC+8)**.

| Item | Value |
| --- | ---: |
| Schema version | 1 |
| Instruments with bars | 5,795 |
| Minute-bar rows | 3,475,824,481 |
| Canonical Parquet files | 5,795 |
| Normalized data size | 43.14 GB |
| First timestamp | 2010-01-04 09:30:00 |
| Last timestamp | 2026-08-07 10:21:00 |
| Snapshot build time | 2026-08-21T14:31:54+08:00 |
| Calendar/listing instrument-days before market-status audit | 14,572,676 |
| Observed instrument-trading days | 14,427,433 |
| Instrument-days without observed bars | 145,243 |
| Raw calendar/listing coverage before market-status audit | 99.0033% |
| Verified trading days missing minute bars | 62,161 |
| Confirmed suspension days | 69,928 |
| Zero-daily no-trade days | 148 |
| Unresolved no-bar days | 13,006 |
| Audited expected instrument-trading days | 14,502,600 |
| Audited missing instrument-trading days (verified + unresolved) | 75,167 |
| Audited instrument-trading-day coverage | 99.4817% |
| Instruments with verified missing minutes | 285 |
| Instruments with unresolved no-bar days | 393 |
| Instruments with no-bar days before market-status audit | 2,440 |
| Market-wide missing trading days inside the published span | 0 |

Scope: this repository covers A-share equities. Exchange-traded funds are excluded and published in a separate dataset with a compatible schema.

## Dataset Viewer and subsets

The canonical data uses one Parquet file per instrument. Asking the Hub to inspect all 5,795 remote files as one Viewer split can time out. The explicit subsets below keep the Viewer usable without changing or duplicating the canonical dataset.

| Subset | Contents | Rows |
| --- | --- | ---: |
| `bars_sample` (default) | First up to 64 chronological bars from every published instrument; deterministic and not synthetic | 370,880 |
| `instrument_coverage` | One row per published instrument with path, time range, record count, and trading-day coverage | 5,795 |
| `missing_intervals` | Consecutive eligible trading-day ranges with no observed bars | 10,221 |
| `no_bar_day_classification` | One row per in-scope instrument-day without bars, classified by daily trading and suspension evidence | 145,243 |
| `market_calendar` | Every calendar date labeled as trading day, weekend, or exchange closure, with market-wide bar availability | 7,889 |
| `absent_instruments` | Eligible universe members with no published canonical file | 66 |

The Viewer sample spans 5,795 instruments and is 7.13 MB. It exists only for browser inspection. The complete 3,475,824,481-row dataset remains under `data/stock_1m/`.

> `load_dataset("neigezhu/china-a-share-1min-ohlcv")` loads the default `bars_sample` subset. Use the file-level or full-snapshot methods below for the canonical bars.

### Load a Viewer subset

```python
from datasets import load_dataset

sample = load_dataset("neigezhu/china-a-share-1min-ohlcv", "bars_sample", split="train")
coverage = load_dataset("neigezhu/china-a-share-1min-ohlcv", "instrument_coverage", split="train")
```

### Load one canonical instrument

```python
from huggingface_hub import hf_hub_download
import pyarrow.parquet as pq

path = hf_hub_download(
    repo_id="neigezhu/china-a-share-1min-ohlcv",
    filename="data/stock_1m/SH/600519.parquet",
    repo_type="dataset",
)
bars = pq.read_table(path)
```

### Download and scan the complete snapshot

```python
from pathlib import Path
from huggingface_hub import snapshot_download
import pyarrow.dataset as ds

root = Path(snapshot_download(
    repo_id="neigezhu/china-a-share-1min-ohlcv",
    repo_type="dataset",
    allow_patterns=["data/stock_1m/*/*.parquet", "metadata/*"],
))
bars = ds.dataset(root / "data" / "stock_1m", format="parquet")
```

For reproducible research, pass a Hub commit SHA as `revision=` to `hf_hub_download` or `snapshot_download`.

## Repository layout

```text
data/stock_1m/{exchange}/{symbol}.parquet
viewer/bars_sample.parquet
viewer/instrument_coverage.parquet
viewer/missing_intervals.parquet
viewer/no_bar_day_classification.parquet
viewer/market_calendar.parquet
viewer/absent_instruments.parquet
metadata/coverage_by_instrument.csv
metadata/missing_intervals.csv
metadata/no_bar_day_classification.csv
metadata/market_calendar.csv
metadata/absent_instruments.csv
metadata/source_provenance.json
metadata/summary.json
LICENSE
README.md
```

Each canonical instrument file is sorted by `timestamp`. Its logical key is (`exchange`, `symbol`, `timestamp`). Symbols remain strings so leading zeroes are preserved.

## Bar schema and semantics

| Field | Parquet type | Unit / meaning |
| --- | --- | --- |
| `symbol` | string | Security identifier without exchange suffix |
| `exchange` | string | `SH`, `SZ`, or `BJ` |
| `timestamp` | timestamp[us] | Timezone-naive minute label interpreted as Asia/Singapore (UTC+8) |
| `open` | float64 | Unadjusted opening price, CNY per share |
| `high` | float64 | Unadjusted high price, CNY per share |
| `low` | float64 | Unadjusted low price, CNY per share |
| `close` | float64 | Unadjusted closing price, CNY per share |
| `volume` | int64 | Traded shares during the minute |
| `turnover` | float64 | Traded value during the minute, CNY |

- Frequency: 1 minute.
- Regular session labels: 09:30–11:30 and 13:00–15:00.
- Price adjustment: none; corporate-action adjustment factors are not included.
- Storage: Zstandard-compressed Parquet with statistics and bounded row groups.

## Coverage and quality reports

`metadata/coverage_by_instrument.csv` is the canonical inventory. It records each file path, observed range, row count, expected and observed trading days, and coverage status. `metadata/missing_intervals.csv` groups eligible trading-day ranges with no observed bars. `metadata/no_bar_day_classification.csv` classifies every in-scope no-bar instrument-day using daily-trading and suspension evidence. `metadata/market_calendar.csv` labels every date as `trading_day`, `weekend`, or `exchange_closed`, and records whether any published instrument has bars on that date. `metadata/absent_instruments.csv` lists eligible instruments without a published file. `metadata/summary.json` provides snapshot-level counts for automated checks.

Coverage is evaluated against an exchange trading calendar and each instrument's listing range. Weekends and exchange-declared closures, including statutory holiday closures, are excluded from expected trading days. Dates before listing and after known delisting are also excluded.

The value **145,243 instrument-days without observed bars** is an aggregate over instruments, not a count of distinct calendar dates. If 100 instruments have no bars on one open day, that contributes 100 no-bar instrument-days. Within the published span, **0 exchange trading days** have no bars for any instrument.


The no-bar audit separates absence of minute bars from absence of trading. Of **145,243 in-scope instrument-days without bars**, **62,161** have a positive-volume daily observation and are verified minute-data gaps; **69,928** have an explicit suspension event; **148** have a zero-volume and zero-turnover daily observation; and **13,006** lack decisive daily or suspension evidence and remain unresolved. Suspension and zero-trade days are excluded from the audited data-gap rate. Unresolved days remain conservatively counted as gaps.



## Construction and validation

This snapshot is assembled by **asynchronous multi-source cross-validation**: independent minute streams are aligned on instrument and timestamp, checked for session bounds and basic OHLCV sanity, and merged so overlapping minutes are corroborated. Records are then deduplicated and normalized to the public schema; coverage reports are regenerated from the published Parquet files.

## Limitations

- This is a historical snapshot, not a real-time feed.
- Coverage varies by instrument and is not gap-free; inspect `instrument_coverage` before research or backtesting.
- Prices are unadjusted and the release does not include corporate actions or adjustment factors.
- Minute OHLCV does not contain orders, individual trades, order-book state, participant identities, or latency information.
- Provider-level provenance is intentionally not exposed, so it cannot be independently audited from the repository alone.
- Floating-point prices and turnover should not be treated as exact decimal accounting values.

## Project perspective

We want open financial-market data to remain downloadable, auditable, and reusable. Stable schemas and explicit gap reports make replication easier and let research compete on methods rather than private access.

## Every person is a variable

**Every person is a variable.** The market is not exogenous weather: you cannot stand outside the equation, model it, and leave yourself out. Prices, trades, and rolls are produced by participants. A model of market behavior must include those participants—including the person building the model.

In 1993, **Metallgesellschaft (MG)** used front-month NYMEX energy futures, rolled repeatedly, to hedge long-term supply contracts. Its position reached roughly one-fifth of open interest, so other participants could anticipate its required monthly roll. MG was not merely modeling the market; its own position was changing the market. When the curve reversed, margin calls and the forced unwind brought it close to bankruptcy.

As quantitative participation grows, it changes price formation and can invalidate strategies fitted to a different participant mix. Institutions adapt, but that reinforces the point: when participants change, the market and its effective strategies change with them.

Therefore: **to model the market, first model yourself as part of it.** Open minute bars cannot identify every participant, but they preserve a public tape of how prices are formed when many participants act at once.

## Related dataset

For exchange-listed ETFs, use the separate [China Exchange-Traded Funds 1-Minute OHLCV](https://huggingface.co/datasets/neigezhu/china-etf-1min-ohlcv) dataset. It is already published; its universe and coverage metrics are independent of this A-share equity snapshot.

## Versioning, license, and citation

- Dataset schema version: `1`.
- License: [Apache License 2.0](LICENSE).
- Updates preserve the canonical path and field contract. Consumers that require an immutable snapshot should pin a Hub commit SHA.

```bibtex
@dataset{neigezhu_china_a_share_1m_ohlcv,
  author    = {neigezhu},
  title     = {China A-Share Equities 1-Minute OHLCV},
  year      = {2026},
  publisher = {Hugging Face},
  url       = {https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv}
}
```

---

## 中文说明

### 数据集概览

本快照包含沪、深、北交所中国 A 股，共 **5,795** 个证券、**3,475,824,481** 条 1 分钟 OHLCV，时间范围为 **2010-01-04 09:30:00** 至 **2026-08-07 10:21:00**。价格不复权，成交量单位为股，成交额单位为人民币。Parquet 的 `timestamp` 不携带时区，统一按 **Asia/Singapore（UTC+8）**解释。

范围说明：本仓库覆盖 A 股股票，不包含 ETF；ETF 使用兼容字段在独立数据集中发布。

### Dataset Viewer

主数据保持“每个证券一个 Parquet 文件”，共有 5,795 个文件。Hugging Face 若把这些远程文件作为一个 Viewer split 逐个读取元数据会超时，因此仓库显式配置了六个可用子集：

- `bars_sample`：默认子集；每个已发布证券取最早不超过 64 条记录，共 370,880 条。样本是确定性的真实记录，不是合成数据。
- `instrument_coverage`：每个已发布证券一行，包含文件路径、记录数、起止时间和交易日覆盖。
- `missing_intervals`：连续缺失交易日区间。
- `no_bar_day_classification`：逐证券日区分已核实分钟缺口、明确停牌、零成交和待确认日期。
- `market_calendar`：逐日标记交易日、周末或交易所休市日，并标记当天全市场是否至少有一条分钟数据。
- `absent_instruments`：应在证券范围内但没有主数据文件的证券。

Viewer 只用于浏览。完整的 3,475,824,481 条记录仍位于 `data/stock_1m/`。直接调用 `load_dataset("neigezhu/china-a-share-1min-ohlcv")` 会读取默认的 `bars_sample`，完整数据应使用上面的单证券下载或全快照下载方式。

### 数据约定

- 逻辑主键：`exchange + symbol + timestamp`。
- 单个证券文件按 `timestamp` 升序排列。
- 交易所代码：`SH`、`SZ`、`BJ`。
- 常规交易时段：09:30–11:30、13:00–15:00。
- 价格：人民币/股，不复权。
- 成交量：股。
- 成交额：人民币。
- 时间：无时区 Parquet 时间戳，按 Asia/Singapore（UTC+8）解释。

### 构建与质量

本快照通过**多数据源异步交叉核验**构建：多路分钟行情按证券与时间戳对齐，校验交易时段与 OHLCV 基本一致性后合并，并对重叠分钟做交叉确认。随后按证券和时间戳去重并规范化到公开字段，覆盖报告由最终发布的 Parquet 文件重新生成。

覆盖率按交易所交易日历和证券上市区间计算。周末、法定节假日休市和交易所公告休市日不进入应有交易日；上市前和已知退市后的日期也不计入。

当前共有 **14,572,676 个日历/上市区间内证券交易日**、**14,427,433 个已观察证券交易日**、**145,243 个无分钟记录证券日**。这个无记录数是“证券 × 交易日”的合计，不是不同自然日数量：同一个交易日有 100 只证券无记录会计 100。发布区间内，全市场所有证券同时没有数据的交易日为 **0 天**。


无分钟记录不等于数据缺失。逐证券日核验后，在发布区间内共有 **145,243 个无分钟记录证券日**：其中 **62,161 个**存在正成交量日线，确认为分钟数据缺口；**69,928 个**存在明确停牌记录；**148 个**日线成交量和成交额均为零；另有 **13,006 个**缺少决定性日线或停牌证据，继续列为待确认。停牌和零成交日不进入审计后的数据缺口率，待确认日期仍按保守口径计入缺口。

研究和回测前应同时检查 `instrument_coverage`、`no_bar_day_classification` 和 `market_calendar`，不能把停牌日直接当成采集缺口，也不能把数据集视为无缺口全历史。

### 局限

- 这是历史快照，不是实时行情。
- 不同证券的覆盖范围不同。
- 数据不复权，不包含公司行动和复权因子。
- 分钟 OHLCV 不包含逐笔成交、订单簿、参与者身份或延迟信息。
- 仓库不披露数据提供方名称，因此不能仅从公开文件独立审计提供方级别的来源。

### 项目视角

我们希望开放金融市场数据保持可下载、可审计、可复用。稳定字段与明确的缺口报告有助于复现，也让研究更多地竞争方法，而不是竞争私有数据权限。

### 每个人都是一个变量

我认为**每个人都是一个变量**。市场不是外生天气：你不能站在方程外面建模，却不把自己放进模型。价格、成交和移仓都由参与者产生，市场行为模型也必须包含建模的人自己。

1993 年，**德国金属公司（Metallgesellschaft，MG）**用近月 NYMEX 能源期货连续移仓，对冲长期供货合约。其仓位约占未平仓量两成，其他参与者可以预判它每月必须移仓。MG 不只是在建模市场，它的仓位本身也在改变市场；期限结构反转后，保证金追缴和被迫平仓使其濒临破产。

随着量化参与者增加，价格形成机制会改变，基于另一种参与者结构拟合的策略也可能失效。机构会调整，但这恰好说明：参与者变了，市场和有效策略也会随之改变。

所以：**算市场，先把自己算进去。** 开源分钟行情无法识别每个参与者，但能留下公共记录，呈现许多参与者同时行动时价格如何形成。

### 相关数据集

上市 ETF 数据见已发布的独立数据集 [China Exchange-Traded Funds 1-Minute OHLCV](https://huggingface.co/datasets/neigezhu/china-etf-1min-ohlcv)。其证券范围和覆盖指标独立于本 A 股股票快照。

### 版本与许可

- schema 版本：`1`。
- 许可：[Apache License 2.0](LICENSE)。
- 需要严格复现时，请在下载接口中固定 Hugging Face commit SHA。
