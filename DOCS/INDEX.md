# 项目文档索引

本仓库用于承载 A 股研究脚本及其手动触发的 GitHub Actions 工作流，包括红利核心股 PIT 动态 Top10 V1.0 和工业富联 601138 盘中 5 分钟左侧卖点研究。

## 优先阅读

1. [PROJECT_ANALYSIS.md](PROJECT_ANALYSIS.md)：当前项目事实、入口和约束。
2. [PROJECT_UPDATES.md](PROJECT_UPDATES.md)：重要变更、原因与验证记录。

## 专项文档

[Foxconn T0 research](FOXCONN_T0_RESEARCH.md): implemented historical batch; prospective specification remains proposed.

- [工业富联反T复核与有限研究](FOXCONN_T0_RESEARCH.md)：active；GitHub独立研究分支执行。

- [Foxconn T0 B02](FOXCONN_T0_B02.md): implemented historical coverage, failure audit and fixed-exit exploration; no strategy promotion.

- [Foxconn batch03](FOXCONN_T0_B03.md): implemented; mechanical open-to-close reverse T not adopted after fixed factor audit, PT comparison and return attribution.

- [Hindsight decline check](FOXCONN_T0_HINDSIGHT_CHECK.md): implemented; profitable intervals exist, causal identification remains unverified.

- [Foxconn B04](FOXCONN_T0_B04.md): implemented; hindsight opportunities confirmed, all10 causal RT variants negative. Fixed evidence: research/foxconn_t0_20260913_b04/REPORT.md. Pre-run contract retained unchanged.

- [B05 conditional decline probability](FOXCONN_T0_B05.md): implemented; prior highCLV+highvolume observation candidate, long-history counterevidence retained. Results research/foxconn_t0_20260915_b05/REPORT.md; pre-run spec retained.

- [B06 execution and external hypotheses](FOXCONN_T0_B06.md): implemented; BASE execution sensitivity and external rules verified; candidate retained with historical counterevidence, external rules not adopted. Evidence research/foxconn_t0_20260915_b06/REPORT.md; pre-run contract unchanged.

- [B07 expanded-history environment study](FOXCONN_T0_B07.md): implemented; expanded history,8 environment splits and annualNONE results; historical counterevidence retained.

- [B08 overnight study](FOXCONN_OVERNIGHT_B08.md): implemented finite first round;14 computable rules negative,ON2_F7 unavailable; no strategy promotion. Fixed results b4691c823383eca5de71ca120c3df2e3918df6a3; execution uncertified.
