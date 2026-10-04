# 工业富联上市以来分钟数据：初版候选入口

真实性修复状态active，请先看[最新逐笔补证与限制](FOXCONN_KLINE_REPAIR.md)。本页初版保留作历史候选，有完整OHLC字段不代表真实每分钟极值已认证。

**状态：全历史覆盖已补齐；结构清洗与来源核验通过；部分行情价格差异仍保留。**

范围：601138.SH，2018-06-08—2026-09-30，共2,019个交易日。不复权，北京时间UTC+8。

| 交付 | 数量 | 入口 |
|---|---:|---|
| 1分钟OHLCV | 484,560根，每日240根 | [Parquet](../research/foxconn_kline_20261005/canonical/601138_1min.parquet) · [CSV.gz](../research/foxconn_kline_20261005/canonical/601138_1min.csv.gz) |
| 5分钟OHLCV | 96,912根，每日48根 | [Parquet](../research/foxconn_kline_20261005/canonical/601138_5min.parquet) · [CSV.gz](../research/foxconn_kline_20261005/canonical/601138_5min.csv.gz) |
| 每日原生分时 | 484,560点，每日240点 | [Parquet](../research/foxconn_kline_20261005/canonical/601138_intraday.parquet) · [CSV.gz](../research/foxconn_kline_20261005/canonical/601138_intraday.csv.gz) |
| 数据＋三份离线图表 | ZIP内含三个普通CSV | [下载目录](../research/foxconn_kline_20261005/delivery/) |

[使用与口径说明](../research/foxconn_kline_20261005/delivery/数据说明.md) · [逐日质量](../research/foxconn_kline_20261005/canonical/daily_quality.csv) · [分时质量](../research/foxconn_kline_20261005/canonical/snapshot_daily_quality.csv) · [覆盖统计](../research/foxconn_kline_20261005/canonical/coverage.json) · [独立验证](../research/foxconn_kline_20261005/audit/independent_verification.json) · [图表验证](../research/foxconn_kline_20261005/audit/chart_verification.json)。

## 使用边界

缺日0、缺格点0、重复时间戳0、非法OHLC 0。5m由五个完整1m区间聚合；分时为重新采集的原生price/vol/avg_price，没有推造OHLC。

332日分钟高低价与BaoStock及TDX日线参考不符，18日末分钟价与2018-08-20以前的旧收盘定义需区分；591根1m有其他版本价格冲突。按本轮日线价格/量额容差和版本冲突筛选，strict_eligible=true为1,659日。全量数据不因存在问题而删除，也不称为交易所逐笔认证。

raw/保存固定来源；canonical/是本批统一数据入口；audit/保存差异与验证；delivery/是面向使用者的最终导出。旧main数据及B13历史快照保留用于复核，不覆盖旧研究。

## 来源

HF固定ba589a11534825044fe5a6b84838f50ba8d8d188的601138单股OHLC；B13固定fc832bce87c5963349bd9df9766fbf60089c385d；main固定e428977626fa6575dc8f4a5b0693c11e93f9a4c2；原BaoStock5m附件11243418261；本批pytdxdata 0.6.1新取得的1m、日线和全部分时。具体哈希见SHA256.json及交付包清单。

用户2026-10-05明确授权本对话自主执行GitHub计算、整理和提交。采集、清洗、统计和图表构建均在GitHub Actions执行；本地仅回存结论及最终用户交付副本。

最终数据提交：[9a51ba1](https://github.com/chixig/daily_stock_analysis/tree/9a51ba137149b3e40b6160f3ed8113302a307e15/research/foxconn_kline_20261005)。最终运行：[37226125093](https://github.com/chixig/daily_stock_analysis/actions/runs/37226125093)。
