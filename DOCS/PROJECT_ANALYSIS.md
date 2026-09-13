# 项目当前分析

## 定位

仓库承载一个严格防前视的 A 股红利核心股 PIT 动态 Top10 V1.0 Pilot。它验证 `Quality + Valuation + Dividend + Safety` 的可复现量化代理，不等同于把 2026 年冻结官方 Top10 倒推到历史。

## 当前入口

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

## 工业富联反T独立复核批次
2026-09-13用户授权在GitHub执行全阶段反T审计。入口 scripts/research/foxconn_t0_audit.py；规格 FOXCONN_T0_RESEARCH.md。底稿保留GitHub，旧RA-D1-V不代表完整反T。真实数据验收待工作流运行。

## Foxconn T0 batch validation (2026-09-13)
Runs 34707899992, 34708396165 and final 34708662088 succeeded. Final code: 166ab401abce18213c7d025671074240dde1b19d; results: ac5b6e3af988b609a40f6cf16737b4dcf2c8871b.
Data: 2007 daily dates, 2006 snapshot dates; missing snapshot 2019-08-16. V3 candidate N31 reproduced; frozen-stage variant N23. Both remain observation candidates.
Completed: fixed 88-region study, robustness, indicative execution prices, finite-cash scenarios and 149 scope-tagged negative-region mirror records. No live strategy, full dividend-tax account model or prospective automation certified.
Results: research/foxconn_t0_20260913/REPORT.md, REVIEW.md, manifest.json. All data processing stayed on GitHub; local deliverable is conclusions only.

## Foxconn batch02 (2026-09-13)
User approved continued reverse T research. Six fixed mechanisms across four stages; all computation and evidence on GitHub. Prior results remain unchanged. New outputs research/foxconn_t0_20260913_b02/. Actual validation pending Actions.
