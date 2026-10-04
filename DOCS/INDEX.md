# 项目文档索引

本仓库用于承载 A 股研究脚本及其手动触发的 GitHub Actions 工作流，包括红利核心股 PIT 动态 Top10 V1.0 和工业富联 601138 盘中 5 分钟左侧卖点研究。

## 优先阅读

1. [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md)：当前项目事实、入口和约束。
2. [PROJECT_UPDATES.md](PROJECT_UPDATES.md)：重要变更、原因与验证记录。

## 专项文档

当前没有额外专项方案文档。

- [工业富联历史分钟数据交付](FOXCONN_KLINE_DELIVERY.md)：implemented，上市以来1m/5m/原生分时已覆盖，保留价格差异与质量筛选条件。

- [工业富联分钟真实性修复](FOXCONN_KLINE_REPAIR.md)：active，近期125日逐笔候选已交付，11日对账失败保留，早期全历史尚未认证。
