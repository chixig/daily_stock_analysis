# 项目更新记录

## 2026-09-10：初始化导入（本地验证完成）

- 背景：将 `dividend_pit_top10_v1_bundle_v2` 中说明指定的两份文件导入 `chixig/daily_stock_analysis`。
- 方案：只提交标准仓库路径下的回测脚本和 Actions 工作流；不提交下载包根目录的可见副本，也不提交运行产生的数据和结果。
- 原因：下载包明确将根目录副本标记为查看用途，标准路径才是仓库入口。
- 验证：导入前已确认目标远程仓库为空提交仓库；脚本可编译，依赖可导入，纯函数 smoke 测试通过，YAML 可解析，`git diff --check` 通过；源文件与下载包副本 SHA-256 一致。
- 当时待办：推送到 `main` 后手动触发 GitHub Actions，真实数据回测结果以 Actions artifact 为准。

## 2026-09-10：修复空财务快照字段契约

- 背景：首次 Actions 运行已完成数据下载和市场面板构建，但在 2012 年评分时因空财务快照缺少 `code6` 列而失败。
- 修复：`annual_financial_snapshot()` 在无可用披露数据时显式返回完整字段集合，保持与后续 `merge(on="code6")` 的契约一致。
- 验证：空财务快照回归 smoke 测试通过；失败运行编号为 `34447521319`，未产生可用回测结果。

## 2026-09-10：适配实际 Qlib 数据字段并消除指数代码碰撞

- 背景：第二次 Actions 运行已完成数据下载和逐年评分，但实际发布的 Qlib 包只提供 OHLCV、复权因子和成交额，没有 `pe_ttm`、`pb`、`total_mv` 等估值字段；运行因此没有有效入选结果，并在空结果输出阶段失败，运行编号为 `34447991956`。
- 根因：原实现假设 Qlib 包含估值字段；同时 `instruments/all.txt` 还包含 `SH000905`、`SZ399300` 等指数序列，把它们映射成六位代码后会与股票代码碰撞并导致重复选股。
- 修复：使用信号日前可见的最新完整年度 `basic_eps`、归母权益和净利润/每股收益估算股本，结合 Qlib OHLCV 推导 PE、PB 和过去一年平均市值代理；过滤指数序列，仅保留股票代码，并在最终选股处按 `code6` 去重。
- 口径：上述估值和市值是可复现代理，不声称等同于 Qlib 官方估值字段；模型定义会在结果中明确披露这一限制。
- 验证：实际下载的 Hugging Face 财务 parquet 与 Qlib 数据本地回归通过；2018–2026 每年均可生成 10 个不同代码的 CoreTop10，LowVolProxy 每年 50 个标的；脚本编译和空快照/估值推导/去重 smoke 测试通过。
- 当时待办：重新运行 GitHub Actions，并以成功运行的 artifact 检查最终回测结果。

## 2026-09-10：完成真实数据回测

- 运行：GitHub Actions `34450501954`，对应提交 `23d403ccc83308fb88c04679559967c33aa09d43`，状态为 success。
- 产物：artifact `dividend-pit-top10-v1-34450501954`，包含 summary、年度收益、逐年 Top10/LowVolProxy、模型定义和 2026 重合度报告。
- 结果事实：CoreTop10 gross 在 8 个有有效组合的年份上总收益 73.41%、CAGR 7.12%、正收益年份占比 75%；CoreTop10 net 总收益 72.09%、CAGR 7.02%。2012–2017 因 PIT 财务/筛选条件不足没有 CoreTop10 有效组合，不能把 2012–2025 直接解读为 14 年连续有效样本。
- 结果事实：LowVolProxy 在 10 个有效年份上总收益 217.87%、CAGR 12.26%、正收益年份占比 90%。它是近似代理，不是中证官方指数复刻。
- 结果事实：2026 模型 Top10 与冻结官方 Top10 重合 3/10；报告明确要求仅将本项目视为方法论代理，不得把收益表述为官方 2026 Top10 的历史收益。
- 验证：artifact 下载、CSV/JSON 结构检查、逐年代码唯一性检查均通过；CoreTop10 2018–2026 每年 10 个不同代码，LowVolProxy 2016–2026 每年 50 个不同代码。

## 2026-09-10：导入工业富联 601138 盘中研究桥

- 背景：根据 `industrial_fulian_601138_intraday_research_bridge` 说明，将工业富联 `601138` 的 RA-D1-V × 5 分钟左侧卖点研究接入同一仓库。
- 导入范围：`scripts/chatgpt_601138_intraday_research.py` 和 `.github/workflows/chatgpt-601138-intraday-research.yml`；未提交下载包根目录说明副本或本地研究产物。
- 研究口径：日线前复权只负责重建开盘时已知的 RA-D1-V 信号；BaoStock 不复权 5 分钟 K 线只负责信号后的执行顺序；实际卖出后的下一根 bar 才开始 TP/Stop 判断；分钟 OHLC 对账失败日期剔除。
- 输出与发布：workflow 生成 `research/601138_intraday/` 下的 signals、minute QC、trades、summary 和 `REPORT.md`，成功后尝试 commit 回 `main`，并上传 30 天 artifact。
- 本地验证：脚本编译通过、workflow YAML 解析通过、70 个策略规格生成、限价成交/回落确认/下一根 bar 回补/同 bar 止损优先/日线 OHLC 对账/费用计算 smoke 测试通过。
- 当时待办：手动触发 `ChatGPT 601138 Intraday Research`，检查真实 BaoStock 数据覆盖、QC 通过率、候选信号数和参数稳定性；不以单点最高回测值直接定版。

## 2026-09-10：完成工业富联 601138 真实数据回测

- 运行：GitHub Actions `34472518379`，状态为 success；workflow 的数据研究、报告展示、artifact 上传和自动 commit 全部通过。
- 回写：研究结果已提交到 `main`，提交为 `e6bc6671851b034e98c35dfcbd7c2f39ebfa4c50`，提交消息为 `research: add 601138 intraday 5m backtest`。
- 产物事实：共 61 个 RA-D1-V 候选信号；分钟 QC 通过 51 个，10 个因分钟 OHLC 与 BaoStock 未复权日线不一致而剔除；生成 2,674 笔策略交易，full / 2024+ / 2025+ 各输出 70 个参数组合。
- 结果事实：现代窗口中 `limit rise=0.5%, TP=1.8%` 的 15 笔成交、PF 1.34、平均净收益/候选信号 0.28%；加入 4% 灾难止损、`TP=1.5%` 的相邻方案为 15 笔成交、PF 1.54、平均净收益/候选信号 0.27%。但在 2025+ 窗口，带止损方案的平均净收益/候选信号仅 0.07%、PF 1.06；full 窗口该指标为 -0.05%、PF 1.04，未形成稳健平台，不能据此宣布定版。
- 结果事实：`pullback` 方案在 2024+ 的部分参数组合 PF 较高，但成交样本只有 8–13 笔，且 full 窗口仍为负或接近零；这符合说明中的纪律，不把单点最高值当作稳健结论。
- QC 异常日期：`2023-09-20`、`2024-09-18`、`2025-04-14`、`2025-04-16`、`2025-12-04`、`2025-12-05`、`2026-01-28`、`2026-07-23`、`2026-07-24`、`2026-08-05`。
- 交付：artifact 为 `industrial-fulian-601138-intraday-research`，保留 30 天；报告和 CSV 结果已同时写回仓库。

## 2026-09-13 工业富联反T研究恢复
新增独立分支审计与有限研究入口，保留现有采集流程。计算和底稿全部在GitHub；双向亏损区域登记反向候选。真实数据验收待执行。

## Foxconn T0 batch validation (2026-09-13)
Runs 34707899992, 34708396165 and final 34708662088 succeeded. Final code: 166ab401abce18213c7d025671074240dde1b19d; results: ac5b6e3af988b609a40f6cf16737b4dcf2c8871b.
Data: 2007 daily dates, 2006 snapshot dates; missing snapshot 2019-08-16. V3 candidate N31 reproduced; frozen-stage variant N23. Both remain observation candidates.
Completed: fixed 88-region study, robustness, indicative execution prices, finite-cash scenarios and 149 scope-tagged negative-region mirror records. No live strategy, full dividend-tax account model or prospective automation certified.
Results: research/foxconn_t0_20260913/REPORT.md, REVIEW.md, manifest.json. All data processing stayed on GitHub; local deliverable is conclusions only.

## Foxconn batch02 (2026-09-13)
User approved continued reverse T research. Six fixed mechanisms across four stages; all computation and evidence on GitHub. Prior results remain unchanged. New outputs research/foxconn_t0_20260913_b02/. Actual validation pending Actions.
