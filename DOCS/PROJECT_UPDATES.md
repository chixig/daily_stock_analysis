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

## 2026-09-13 Batch02 completion

Batch02 historical research completed on 2026-09-13. Final Actions run 34746090459 succeeded; code efe13df45ec425cea3570f762be0583288b7f0af; results 611d9ebfde3eb910a263cb4aad1e8dcab08ddc1f. Six mechanisms across four frozen stages produced 24 cells: 2 empty, 19 negative means, 3 weak positive means. No strategy promotion. Fourteen materially negative cells were independently costed as positive-T mirrors.
Old frozen-stage volume candidate remains N23; top three winning cash flows equal 97.3% of net cash gain. After path inspection, two fixed exits were explored in-sample without threshold search, under touch/gap-aware and next-bar execution assumptions. Baseline cash 8706.204; stop2 touch 3507.609; stop2_tp1 touch -2048.378. Both execution assumptions failed to improve aggregate cash for all three examined candidates. This does not falsify every stop rule. Four negative-mean exit variants also have independently costed mirrors; the frozen touch mirror loses 1152.402, preserving the both-directions-negative counterexample.
Validation includes parent input hashes, deterministic cash-flow checks, previous-day signal invariance to same-day OHLC/volume, and exit cardinality/finite outcomes. An intermediate timestamp field-access failure was fixed and rerun. All market computation/evidence remains on GitHub. Local outputs contain conclusions only. No main merge, live trading, positive-T optimization or prospective automation. Remaining scope includes point-in-time event data and executable intraday reversal hypotheses; the overall reverse-T research is not final.
Evidence: research/foxconn_t0_20260913_b02/REPORT.md, manifest.json and results/.

## 2026-09-13 Batch03 authorized
Fixed 38 factor definitions, up to 410 rule cells including six predetermined interactions per scope. Comparison with unchanged PT direction matrix and log-return attribution. Evidence remains GitHub only; no forward unseen-sample claim.

## 2026-09-13 Batch03 scope closed

Final run 34748296586 succeeded. Code 2ba44af48d1a77e8ef969baf99ca7847cfe4bd1d; result 9c13b3e507e00b05222f8e332ebc38cae301f17b. All 38 factors obtained; FRED timed out, identical Nasdaq/SOX indices obtained from Yahoo with NY/Shanghai alignment. Current vendor vintage, not historical publication-vintage certification.
410 registered cells, 392 nonempty, 239 with N>=30. Twenty N>=30 cells had positive means; none survived deletion of the best five returns and none was positive in all three calendar years. No rule passed the basic hurdle. 322 negative-mean cells, 229 at or below -0.5%, preserve independently costed mirrors with overlap and scope labels.
Frozen PT direction matrix, primary N72: mean 1.616%, cash 45428.671, cash PF4.342. Original PT 91-trade ledger not claimed identical. Matched N71: opening cash 45399.025 versus delayed proxy 30399.983; D1 delayed negative. Old RT volume N23 and R deceleration N15 remain historical evidence, not execution rules.
For 166 causal D days, mean overnight log return -0.25756% and intraday +0.25657%; near cancellation. D describes prior weakness, not guaranteed next-day decline. Hindsight actual peak-trough intervals include both overnight and intraday declines, often before D classification. Corporate-action reference changes separately recorded. Hindsight peak/trough labels never used as entry factors.
Decision under the user's stopping condition: do not adopt mechanical open-sell/close-buy RT; close repeated historical factor tuning in this scope. This does not establish that all intraday or overnight RT mechanisms are impossible. PT remains an execution-unvalidated research baseline. No overnight strategy, prospective automation or live trading started.
Validation: parent hashes, frozen-stage consistency, deterministic cash flows, three historical feature-mutation cutoffs, exact log decomposition, and matched execution dates. Common cash scenario is an ex-post feasibility audit; insufficient funds are reported, never used to delete trades based on future closing needs. Main branch unchanged. All data/computation/evidence stay GitHub; local conclusion and project-context updates only.

## 2026-09-13 Scope clarification
Status implemented. Of eight previously identified hindsight decline intervals, four produce positive net RT cash and mean returns; four are negative. All contain profitable days. Fixed1000 shares and inherited costs. Opportunities exist; previously tested causal rules remain unverified and not adopted. No new stage formula or live strategy.
2026-06-03 to07-30: N40, +9063.723 net cash. 2023-04-18 to05-12: N15, +3471.609. 2024-07-09 to2025-04-08: N180, -4670.225 despite45.274% stock decline. Eight selected hindsight intervals are not a future win-rate sample.
Run34750591927 succeeded; code f19008fac161fba0705644bc3af0047edf511d7d; result99a05378ea3facf65598df2a1d598651b9ddfe8f. Parent hashes, interval counts and daily cash reproduction passed. All market computation and trades remain GitHub. Evidence: research/foxconn_t0_20260913_hindsight_check/REPORT.md and manifest.json.


## Foxconn B04 authorized bounded reopening
User approved historical swing segmentation, causal detection and post-detection RT economics. Original four-stage and PT rules remain frozen. Contract DOCS/FOXCONN_T0_B04.md fixed before results; all computation and evidence on GitHub, no main merge. Status active, actual validation pending.


## 2026-09-13 B04 verified outcome

Status implemented. Pre-run specification commit c524fde6dcc4e41b7bb6f9e2e8f1c542493f0fc6 remains immutable. Final code 41f58dade65e07cde2bfeab1fa14c5d81b49cd70, result cf48fb77993d7eb6cf84f8c9ace2248e4ee496c4; Actions34765727424 succeeded. Data2018-06-08..2026-09-11, daily2007, primary654.
At 8/12/20 percent reversal scales, full available complete down legs were46/22/10, RT-net-positive43/20/9; primary18/12/4, positive18/11/3. Hindsight opportunities are real; these labels are future-dependent and not entry signals. R is the reference rule's residual, not an adopted sideways-trading regime; censored edges remain separate.
All10 causal RT variants had negative primary mean and cash, each calendar-year mean also negative. DD2 captures17 of18 primary profitable8-percent down legs, versus frozenD9; inside those legs cash25226.953, all other signal dates -82582.751, total-57355.798. Full-date8-percent attribution: DD2 down dates+26006.760, up dates-68574.963. Faster coverage does not pay for rebound-period losses. No stable cross-scale early/middle/late profit pattern; no phase-timing rule added.
Ten primary negative RT variants independently costed as PT candidates, six at or below-0.5 percent. Across windows/directions178 mirror records,53 large flags, overlapping. DD2_I10 PTmean0.291,cash17323.457 but delete5cash-4000.926; BR10_I10 PTmean0.286,cash17589.103 but delete5cash-3735.280; both descriptive month intervals crosszero. No mirror promoted. Frozen PT remains72,mean1.616,cash45428.671, matched delayed71cash30399.983; previous D1 execution counterevidence retained.
Annual retrospective selection2024/25/26 choseNONE under training-only gates. This is already-inspected history, not new OOS. Original four-stage formula unchanged; current tested mechanical RT rules not adopted. This is not a proof no RT opportunities or no possible causal method exists. No live trading, overnight strategy, main merge or PT optimization.
Validation: parent hashes, frozen stage/PT reproduction, synthetic pivots and next-day signals, prefix/current-future invariance at300/800/1600, decomposition and full-path reconciliation. Initial run34765496340 succeeded; reporting expansion preserved all original numerical file hashes. A summary column-count defect2007 versus10 was corrected with a shape assertion, final run passed, all other output hashes unchanged. Only this research workflow is certified; unrelated existing bank-model workflow failures on branch pushes were not modified.
Evidence: [fixed report](https://github.com/chixig/daily_stock_analysis/blob/cf48fb77993d7eb6cf84f8c9ace2248e4ee496c4/research/foxconn_t0_20260913_b04/REPORT.md), [manifest](https://github.com/chixig/daily_stock_analysis/blob/cf48fb77993d7eb6cf84f8c9ace2248e4ee496c4/research/foxconn_t0_20260913_b04/manifest.json). Local Chinese conclusions only; study English docs do not change bilingual product interfaces.


## B05 authorized 2026-09-15
Conditional open-close decline probability and net economics, fixed monthly causal logistic/ridge forecasts. Specification FOXCONN_T0_B05.md. Original stages/PT frozen; data through2026-09-11 stays GitHub. Results pending.


## 2026-09-15 B05 completed conditional probability study

User authorized continued search for close below open. Data fixed through2026-09-11, primary654 days; no new unseen-data claim. Pre-run spec313f25001277a2e5f01dc6cfe99d7973bbfcdc04; final code8e779e6d510fe6b5727fb2f36ce10c9e8ea78522; results7b62b4bf5467aa354a703242a64c33ace2dc2af3; final run34875628984 succeeded.
Fourteen fixed descriptive conditions and four monthly chronological logistic/ridge models completed. Baseline primary P(C<O)48.165%. PreviousCLV>=.8: N141,p58.156%,RTmean-0.244%; previousvolume/MA20>=1.5: N67,p59.701%,RTmean0.351%.
Their fixed conjunction: N30,p70%,netwin66.667%,RTmean1.355%,cash13849.687,PFcash3.181,delete5mean0.535%,delete5cash2551.567,delayed30mean1.180%,cash10952.848,double-slipmean1.255%. Year2024/25/26 N13/10/7,down76.923/70/57.143%,netmean1.782/1.082/0.949%. Primary descriptive month meanCI[0.470,2.526], probabilityCI[54.283,86.211], not corrected for all historical trials.
Counterevidence: 2020 onwardN62,p58.065%,mean0.261%,cash10783.083,delete5mean-0.194%,delete5cash-515.038,meanCI[-0.475,1.051], liftCI[-2.301,21.584]. Recent candidate, not long-run validated strategy. Primary overlaps old UR-volume on10dates;20 outside old rule have65% declines and mean1.005%, but delete5negative. No overlapping-profit summation, no post-result phase exclusion; original four-stage formula frozen.
Models mildly improve aggregate Brier but upper probabilities overstate realized hit rates; all8 fixed probability-plus-positive-predicted-return trade masks lose. These models not adopted. Prior-lowCLV plus currentgap<=-1%: N40,p25%,RTmean-1.331%; independent PTmirror mean0.951%,cash17061.311,after-auction timing. Across windows/directions129 negative mirrors,87 large flags; no PT optimization.
Decision: preserve highCLV+highVolume as a fixed observation/research candidate. Continue with validation of this precise condition when requested, not broad threshold tuning or automatic trading. Previous no-adoption decisions still apply to prior tested rules; B05 adds a candidate and does not certify execution or future70% probability.
Validation: input hashes, future-feature and prefix invariance900/1600, entire forecast refit with future targets mutated unchanged through2025-01-02, prior-month train cutoff, all654 forecasts finite, synthetic logistic/cost checks, IRLS converged<=5iterations, frozen PT72/cash45428.671 reproduced. Initial run failed on duplicate summary n key, fixed without parameter change; reporting extension preserves all original numerical-file hashes. Only study workflow certified; unrelated bank-model workflow not modified.
Evidence: research/foxconn_t0_20260915_b05/REPORT.md and manifest.json at fixed result commit. All market computation/evidence on GitHub, local Chinese conclusions only; no main merge, live trading, overnight strategy or new automatic monitor.


## B06 authorized
2026-09-15 user requested continued fixed-candidate validation and supplied five external AI rules for reference. Exact external period/costs unknown; no claim of reproduction. Six fixed masks, execution and failure/overlap audit, all computation on GitHub. Results pending.


## 2026-09-15 B06 verified outcome

Implemented six fixed masks on data through2026-09-11, primary2024-01-02 onward654 dates. External screenshot dates/fees/fills unknown: common-window retest, not exact reproduction or proof the source is wrong. No date-window search or threshold tuning.
BASE prior CLV>=0.8 and volume/MA20>=1.5: primary30, down70%, netwin66.667%, netmean1.355%, cash13849.687. Same30 delayed09:35/09:45/10:00 netmean1.180/1.145/0.911%, doubledslip1.081/1.045/0.812%. Delete5mean0.535%, independent delete5cash2551.567; delete best monthcash8578.702. Counterevidence: 2020-2023N32,netmean-0.764%,grossmean-0.489%; full2020N62 netmean0.261%, delete5negative and month interval crosseszero. Remains fixed observation candidate, not execution-certified.
EXT_R1..R5 primaryN62/77/69/96/60; netmean-0.093/-0.328/-0.337/-0.430/-0.221%. All delay-time netmeans negative. Four cash totals positive despite equal-weight percentage mean negative; fixed shares place greater cash exposure on high-price dates. All2024/25 negative, all2026 positive; no year switch adopted. All delete5 and delete-largest-month cash negative. External-only dates outside BASE all have negative mean; no union/intersection adopted.
Useful method: separately evaluate incremental dates from threshold relaxation; R2 minus R1N15 RTmean-1.299%, independently costed PTmean0.927%,cash5809.190. R4 minus R3N27 PTmean0.293%,cash4128.477; R2 minus R5N17 PTmean0.326%,cash1884.101. Diagnostic candidates only, overlapping, not PT optimization. Registry194 cross-window/direction/partition records,70 large-loss flags. Both-directions-negative counterexamples retained.
Next research hypothesis concerns pre-known conditions distinguishing continuation from reversal after a strong/high-volume day; no new environment factors implemented. BASE thresholds and original stages/PT frozen; no live trading, automatic monitoring, overnight study or main merge. PT72/cash45428.671 reproduced, previous D1 delay counterevidence retained.
Spec commitb686e61b383d13b5206c0b7d975abfea0dcc7df1 retained unchanged. Code35b5f5a05358fa36202a2f7040d1bba2f75837e1; results6f62c7f85a5918fa0cab54e84f8074a1619377fa; final Actions34924821913 succeeded. First run34924675336 also succeeded. Follow-up only completed diagnostic mirrors and explicit slip_bps presentation (3-decimal rendering had displayed both slip assumptions as0.001). Original rule, ledger, overlap, annual and relaxation CSV hashes unchanged.
Validation: five parent hashes, original cashflow/stage/PT and BASE dates/cash, literal predicates on2007rows, future mutation/prefix at900/1600, minute09:35 reproduction, pairwise cash reconciliation. All6 primary rules have complete common execution dates; total primary minute coverage651/654. Bar-open proxies and same-vendor checks are not actual-fill or independent-source certification. Only this study workflow certified; unrelated bank-model workflow remains failing.
Evidence: [fixed report](https://github.com/chixig/daily_stock_analysis/blob/6f62c7f85a5918fa0cab54e84f8074a1619377fa/research/foxconn_t0_20260915_b06/REPORT.md), [manifest](https://github.com/chixig/daily_stock_analysis/blob/6f62c7f85a5918fa0cab54e84f8074a1619377fa/research/foxconn_t0_20260915_b06/manifest.json). All market processing and detailed evidence stay GitHub. Local Chinese conclusion SHA256a6606a1c4f7b2cfb18e12a992f4b4f90b5b728cb737d60e946637fc9d6b92835.
