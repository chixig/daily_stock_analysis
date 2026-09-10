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

## 当前状态

仓库原先为空提交仓库。本次导入和空财务快照字段修复已完成本地校验；真实全 A 数据回测需在 GitHub Actions 中下载外部数据后执行。
