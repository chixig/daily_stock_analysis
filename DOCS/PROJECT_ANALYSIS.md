# 项目当前分析

## 定位

仓库承载一个严格防前视的 A 股红利核心股 PIT 动态 Top10 V1.0 Pilot。它验证 `Quality + Valuation + Dividend + Safety` 的可复现量化代理，不等同于把 2026 年冻结官方 Top10 倒推到历史。

## 当前入口

- 工业富联最新[来源追溯和逐分钟核验](FOXCONN_PROVENANCE_R3.md)：332异常日源neigezhu、上游未知；591分钟为TDX多版本及HF的651对。当前逐笔候选与至少一个旧版本相同49分钟、全不同541分钟，另1分钟无候选OHLC。公开早年档案目录可读、下载403；尚未增加认证覆盖。数据0020d076，流程37282949860。

- 回测脚本：`scripts/research/dividend_pit_top10_v1.py`
- GitHub Actions：`.github/workflows/chatgpt-dividend-pit-top10-v1.yml`
- 触发方式：GitHub Actions 页面手动运行 `ChatGPT Dividend PIT Top10 V1`

## 核心约束

- 回测年份为 2012–2025，2026 仅做成分重合度 sanity check。
- 每年 5 月第一个交易日产生信号，第二个交易日开盘执行。
- 财务数据必须满足披露日期不晚于信号日；历史现金分红来自 gbbq 事件。
- Top10 等权，银行最多 3 只；同时输出 Top20 与近似 LowVolProxy 对照。
- 输出结果位于 `_dividend_pit_top10_v1/out/` 和 `_dividend_pit_top10_v1/reports/`，作为 Actions artifact 上传。
- 约 12.1% 的 512890 历史实盘 CAGR 是比较基准，不是本仓库计算出的结果。
- 当前 Qlib 发布包只包含 OHLCV、复权因子和成交额；PE、PB 和平均市值由信号日前可见的完整年度 EPS、权益、估算股本和过去一年平均原始价格派生，属于可复现代理口径。
- Qlib 的指数序列会在建面板时过滤，且选股结果按 `code6` 去重，避免指数代码与股票代码碰撞。

## 工业富联 601138 盘中研究

- 研究脚本：`scripts/chatgpt_601138_intraday_research.py`
- GitHub Actions：`.github/workflows/chatgpt-601138-intraday-research.yml`
- 触发方式：GitHub Actions 页面手动运行 `ChatGPT 601138 Intraday Research`，可选 `end_date`。
- 日线母策略：RA-D1-V；分钟执行数据来自 BaoStock 不复权 5 分钟 K 线。
- 执行候选：开盘卖、Open 上方固定限价卖、冲高后回落确认卖，并比较 1.2%/1.5%/1.8% 回补和 4% 灾难止损敏感性。
- 防前视约束：分钟数据只用于信号后的执行；实际卖出后的下一根 5 分钟 bar 才允许触发 TP/Stop；同 bar 双触发按止损先发生；分钟 OHLC 与 BaoStock 未复权日线不一致的日期剔除。
- 输出目录：`research/601138_intraday/`，包括信号、分钟 QC、逐笔交易、汇总和 `REPORT.md`；成功运行后由 workflow 尝试 commit 回 `main`，同时上传 Actions artifact。

## 当前状态

红利 PIT Top10 工作流已完成一次成功真实数据回测，最近成功运行 `34450501954`。工业富联 601138 研究桥已完成真实 BaoStock 回测，成功运行 `34472518379`，并将 `research/601138_intraday/` 写回 `main`；当前结果用于参数稳定性研究，不宣布单点参数定版。

## 工业富联全历史分钟数据批次

2026-10-05用户明确授权GitHub计算、数据整理及本批提交。research/foxconn-kline-20261005独立分支已交付2018-06-08—2026-09-30，共2019交易日；1m及原生分时各484560条，5m为96912条。raw/canonical/audit/delivery四层见[交付入口](FOXCONN_KLINE_DELIVERY.md)。

事实：逐行源一致性、全网格、独立5m聚合、CSV/Parquet回读和离线图表测试通过。最终数据提交9a51ba137149b3e40b6160f3ed8113302a307e15，最终数据/图表流程37226125093成功。仍有332日分钟极值与两家日线不符、18日旧收盘定义待区分、591根OHLC版本冲突；strict_eligible为1659日。全量覆盖不等于零误差行情。旧研究数据及原main自动化保留。


## 工业富联分钟真实性修复当前状态

[修复入口](FOXCONN_KLINE_REPAIR.md)active，最新[公开源扩展](FOXCONN_PUBLIC_SOURCE_SEARCH_R2.md)。125日逐笔候选1m30000格、5m6000根；旧版114日量价额通过。新交易阶段分类及10日收盘归属推定候选使124日通过，7/15仍少91600股/相对盘口280条成交；时间归属未获源方确认，保留原秒标签和旧版。新取得2022原生分钟146日34894条，142日价格/股数通过、133日再通过金额1元条件；来源上游及分钟标签未认证。suncong全240条严重OHLC错误及362日总体失败，不采用；ANTICH为BaoStock派生。原332早期异常及591根真值冲突仍未解决，不能称全历史已干净。原全历史分时及旧研究保留，所有原件、计算与哈希在GitHub；用户授权最终本地副本。
