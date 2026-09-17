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
User approved continued reverse T research. Six fixed mechanisms across four stages; all computation and evidence on GitHub. Prior results remain unchanged. New outputs research/foxconn_t0_20260913_b02/. Validation completed; see outcome below.

## Batch02 validated outcome

Batch02 historical research completed on 2026-09-13. Final Actions run 34746090459 succeeded; code efe13df45ec425cea3570f762be0583288b7f0af; results 611d9ebfde3eb910a263cb4aad1e8dcab08ddc1f. Six mechanisms across four frozen stages produced 24 cells: 2 empty, 19 negative means, 3 weak positive means. No strategy promotion. Fourteen materially negative cells were independently costed as positive-T mirrors.
Old frozen-stage volume candidate remains N23; top three winning cash flows equal 97.3% of net cash gain. After path inspection, two fixed exits were explored in-sample without threshold search, under touch/gap-aware and next-bar execution assumptions. Baseline cash 8706.204; stop2 touch 3507.609; stop2_tp1 touch -2048.378. Both execution assumptions failed to improve aggregate cash for all three examined candidates. This does not falsify every stop rule. Four negative-mean exit variants also have independently costed mirrors; the frozen touch mirror loses 1152.402, preserving the both-directions-negative counterexample.
Validation includes parent input hashes, deterministic cash-flow checks, previous-day signal invariance to same-day OHLC/volume, and exit cardinality/finite outcomes. An intermediate timestamp field-access failure was fixed and rerun. All market computation/evidence remains on GitHub. Local outputs contain conclusions only. No main merge, live trading, positive-T optimization or prospective automation. Remaining scope includes point-in-time event data and executable intraday reversal hypotheses; the overall reverse-T research is not final.
Evidence: research/foxconn_t0_20260913_b02/REPORT.md, manifest.json and results/.

## Foxconn batch03
User requested a final bounded factor round before deciding whether to discontinue the literal open-sell close-buy approach. Validation completed; see verified outcome below. Specification FOXCONN_T0_B03.md; no actual trading.

## Batch03 verified current decision

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


## 2026-09-15 B06 verified outcome

Implemented six fixed masks on data through2026-09-11, primary2024-01-02 onward654 dates. External screenshot dates/fees/fills unknown: common-window retest, not exact reproduction or proof the source is wrong. No date-window search or threshold tuning.
BASE prior CLV>=0.8 and volume/MA20>=1.5: primary30, down70%, netwin66.667%, netmean1.355%, cash13849.687. Same30 delayed09:35/09:45/10:00 netmean1.180/1.145/0.911%, doubledslip1.081/1.045/0.812%. Delete5mean0.535%, independent delete5cash2551.567; delete best monthcash8578.702. Counterevidence: 2020-2023N32,netmean-0.764%,grossmean-0.489%; full2020N62 netmean0.261%, delete5negative and month interval crosseszero. Remains fixed observation candidate, not execution-certified.
EXT_R1..R5 primaryN62/77/69/96/60; netmean-0.093/-0.328/-0.337/-0.430/-0.221%. All delay-time netmeans negative. Four cash totals positive despite equal-weight percentage mean negative; fixed shares place greater cash exposure on high-price dates. All2024/25 negative, all2026 positive; no year switch adopted. All delete5 and delete-largest-month cash negative. External-only dates outside BASE all have negative mean; no union/intersection adopted.
Useful method: separately evaluate incremental dates from threshold relaxation; R2 minus R1N15 RTmean-1.299%, independently costed PTmean0.927%,cash5809.190. R4 minus R3N27 PTmean0.293%,cash4128.477; R2 minus R5N17 PTmean0.326%,cash1884.101. Diagnostic candidates only, overlapping, not PT optimization. Registry194 cross-window/direction/partition records,70 large-loss flags. Both-directions-negative counterexamples retained.
Next research hypothesis concerns pre-known conditions distinguishing continuation from reversal after a strong/high-volume day; no new environment factors implemented. BASE thresholds and original stages/PT frozen; no live trading, automatic monitoring, overnight study or main merge. PT72/cash45428.671 reproduced, previous D1 delay counterevidence retained.
Spec commitb686e61b383d13b5206c0b7d975abfea0dcc7df1 retained unchanged. Code35b5f5a05358fa36202a2f7040d1bba2f75837e1; results6f62c7f85a5918fa0cab54e84f8074a1619377fa; final Actions34924821913 succeeded. First run34924675336 also succeeded. Follow-up only completed diagnostic mirrors and explicit slip_bps presentation (3-decimal rendering had displayed both slip assumptions as0.001). Original rule, ledger, overlap, annual and relaxation CSV hashes unchanged.
Validation: five parent hashes, original cashflow/stage/PT and BASE dates/cash, literal predicates on2007rows, future mutation/prefix at900/1600, minute09:35 reproduction, pairwise cash reconciliation. All6 primary rules have complete common execution dates; total primary minute coverage651/654. Bar-open proxies and same-vendor checks are not actual-fill or independent-source certification. Only this study workflow certified; unrelated bank-model workflow remains failing.
Evidence: [fixed report](https://github.com/chixig/daily_stock_analysis/blob/6f62c7f85a5918fa0cab54e84f8074a1619377fa/research/foxconn_t0_20260915_b06/REPORT.md), [manifest](https://github.com/chixig/daily_stock_analysis/blob/6f62c7f85a5918fa0cab54e84f8074a1619377fa/research/foxconn_t0_20260915_b06/manifest.json). All market processing and detailed evidence stay GitHub. Local Chinese conclusion SHA256a6606a1c4f7b2cfb18e12a992f4b4f90b5b728cb737d60e946637fc9d6b92835.


## B07 expanded-history study completed 2026-09-15

User requested expansion before2024. Main evaluation now2020 onward1624 dates, old2020-2023 970 and recent2024 onward654 mandatory side-by-side; all available2018-06-08..2026-09-11 2007 daily rows also reported. New environment common availability begins2019-07-22 (1735dates), no warmup imputation; all80 original BASE signals include18 early signals without matched minute data. No new unseen-data claim.
Fixed BASE primary2020N62 mean0.261%, delete5mean-0.194%, cash10783.083 and delete5cash-515.038. Unrestricted full historyN80 mean0.073%, doubledslip-0.027%; 2019 and each2020-2023 year mean negative. RecentN30 mean1.355% remains historically true but not long-run certification.
Four prior-known environment families (SSE20trend, stock-minus-SSE20return,20dayvol relative252median,20dayclose*volume proxy relative252median), high/low splits only, no combinations. All8 splits negative in2020-2023; all2020 deletion-of5-winners mean and cash negative, month intervals crosszero. ACT_high recentN9 down88.889%,mean3.230%, versus oldN14 mean-0.946%; shows danger of recent-window selection. No environment adopted.
Annual expanding selection2022-2026 from2020 training, pre-fixed sample/profit/delete5/two-positive-years gates, allNONE. Zero trades not profitability or proof all possible selectors fail. Gates unchanged after results. BASE retained only as recent historical observation, not deployable validated rule.
Registry239 overlapping scope/direction records,152 large flags. Old BASE+VOL_highN20 RTmean-1.080%, independently costed PTmean0.517%,cash1345.729; candidate only, no calendar-year direction switch. Frozen PT expanded baselineN148 mean0.930%,oldN76mean0.280%,recentN72mean1.616%; no new long-window PT stress certification, prior D1 delay counterevidence preserved.
Pre-run spec7bbe95413e19b3ceb1b69ce8adfdee02b4780c0d, code957860b9d76a951f92a5a8921702014568522c03, results4ca9fe8092262031d52c27ef321784fe990c8a88, Actions34926660120 succeeded. Parent hashes, cash/stage/BASE/PT reproduction, current-future mutation/prefix900/1600, complementary splits/cash, annual training cutoff checks passed. No post-result parameter changes; unrelated bank-model workflow failures not fixed.
Next requires new timestamp-reliable information (industry/auction data) and limited preregistered hypotheses if authorized; no additional acquisition launched. SSE not industry; ACT proxy not actual turnover. Original phases/PT unchanged, no live/overnight/monitor/main merge. Study-only English docs; bilingual product interfaces untouched.
Evidence: [report](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260915_b07/REPORT.md), [manifest](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260915_b07/manifest.json). All market processing/evidence GitHub; local Chinese conclusion SHA256612d6daac99fc711c0718b57de290ea328db0d616ab4f8ba49eec95cf1d89a3a.

## B08 overnight active
User paused intraday RT and authorized close-to-next-open research2026-09-16. Frozen PT unchanged. Spec DOCS/FOXCONN_OVERNIGHT_B08.md; isolated branch,results pending.

## B08 completed 2026-09-16
Close-to-next-open study on data through2026-09-11:2007daily rows,2006complete labels. Main2020N1623 netmean-0.329135%,old970-0.347777%,recent653-0.301444%; zero slip still-0.229419%,non-dividend1615-0.330261%. Commission/minimum and date-varying taxes are research assumptions;20% dividend tax scenario. Raw overnight price mean-0.095324%,tax-adjusted dividend gross mean-0.086811%. No unconditional adoption.
14 computable bounded rules all main netmean negative; ON2_F7 unavailable without intraday index,ON2_F8 aliases ON1_F8. Annual retrospective selectors2022-2026 allNONE. Recent prior-volumeF6N75mean0.014836% but cash-4220.913,delete5-0.348662%,double slip-0.085129%; not promoted. No added combinations or live monitoring; intradayRT paused,PT frozen unchanged.
All2006 cashflows independently scalar-reconciled; all2007 daily open/close matched another same-vendor download within rounding; nine dividend dates and reference-price differences matched vendor dividend table. Input hashes/calendar/causal mutation/prefix checks passed. Execution still uncertified: OHLC proxies,missing intraday index,dividend announcement/payment primary verification and actual queues/partial fills outstanding. Equal-capital dynamic account not implemented; fixed1000 finite-cash scenario reported separately. No candidate passed to unlock combined strategies.
Initial dtype failure corrected without changing rules; later independent audit and descriptive gross-column correction did not change main result/coverage/ledger/neighbor/annual/account hashes versus first successful run. Final codeb2ef11994ad9f742dac445fdcb0221c9852d3655,resultb4691c823383eca5de71ca120c3df2e3918df6a3,Actions35061910249success. Frozen pre-run spec retained. Unrelated pre-existing bank workflow remains failing.
Evidence: research/foxconn_overnight_20260916_b08/REPORT.md and manifest.json. Local Chinese conclusion SHA2568137b86c635cd8623b334cb7a65ecf4b57d25a81816ae437b2d608053654932e. All market data and ledgers remain GitHub. No main merge. Study-only docs; product interfaces and bilingual product docs unaffected.

## B09 active
User continued overnight research2026-09-16. Eight new intraday-path hypotheses,not daily-state grid expansion. Main close-buy/nextopen-sell unchanged; results pending.

## B09 completed 2026-09-16
User continued close-buy/nextopen-sell research. Eight predeclared intraday path hypotheses used completed bars at14:50:tailup/down,afternoon recovery/reversal,break above/below pre14:00 range,tailup/down with same-time-volume ratio>=1.5. No adaptive threshold changes, no fresh data/OOS claim.
All8 main2020/old2020-2023/recent2024 netmeans negative. BreakoutN97mean-0.4816%,breakdownN181mean-0.5156%. Fixed early-entry diagnostic at bar-open after14:50 remains negative for all8; small last10minute drift does not overcome negative overnight/costs. Annual retrospective selections2022-2026 allNONE. No strategy promotion or extra combinations.
Reverse ledger independent costs only:breakdown recentN77mean0.3086%,earlyN104-0.1710%,fullN1810.0330%,delete5-0.1651%;registry only,not primary switch. IntradayRT paused,PT frozen unchanged. No monitoring/live trading/main merge.
Input hashes/B08 cash reproduction,future-minute and daily-final-price mutation,prefix,coverage partition,path-log identity passed.1624minute dates,1624valid path prices,1604with20day tail volume baseline;final date has no nextopen label. First run35068415957success;code7b0d63e74785868eb0ad3307f0296be17d5ba253;results1290406e8da73b3d10a5e85882d188a1a88ff332. Frozen spec retained. Limits:previously explored history,OHLC execution proxy,dividend announcement/settlement not primary-certified,missing intraday index leavesB08F7 unresolved. Account finite1000 scenarios distinct from opportunity-ledger sums.
Evidence research/foxconn_overnight_20260916_b09/REPORT.md and manifest.json. Chinese local conclusion SHA256dbb602123b7a274e05eb926966f3ea631f1a59c4b7fed5e05b0fd3d1fd2be9b6. All market processing/evidence GitHub. Product and bilingual product docs unchanged. Next continuation should prioritize timestamp-valid event/auction data after coverage audit,not add historical price-volume combinations. Unrelated bank workflow failure remains out of scope.

## B10 当前研究

B10完成：2020起1623机会，净>=1%赢家189个，24特征完整1599日含188赢家。样本内A高波动+前日大跌56笔+0.3704%，B20日未深跌+尾盘量比<=0.43238共48笔+0.5403%，C20日深跌78笔+0.3718%；A/C删5赢家均转负。B排除14笔收盘涨停等买入受限代理后34笔均净-0.0419%。年度2022-2026分类231笔-0.2471%、回归177笔-0.0023%；回归近期重复选择C，38笔+0.3730%但删5后-0.2843%。保留3条线索，未升级策略。日内反T暂停、正T冻结不变。

首轮35078545579与补充35078763778均成功；最终代码500135db41c042297fb21e8206dc943264af36f4，固定结果0d17f13a92df1e9458932013e29358f730c21d59。补充只审计成交与账户，35个已有文件哈希均一致。输入/B08现金、时点扰动/前缀、年度截止/前缀拟合检查通过。受限代理不是逐笔成交证明，全部历史已看过，非新独立OOS；未取得新市场数据、未合main/交易/监控。后续冻结线索并核验新信息时点和成交，避免原样本继续调参。

固定证据：[报告](../research/foxconn_overnight_20260916_b10/REPORT.md)、[成交审计](../research/foxconn_overnight_20260916_b10/fullfit_execution_summary.csv)。本地中文正式成果content_id=foxconn-t0-20260916-b10，SHA-256 d16b60a8b650442ee9815390aaf3bcc05d25695fb8bc8a84f8ab430080394c5e。

## B11当前工作

B11完成（研究候选，非实盘认证）。主窗2022起、排除买入受限代理。事前避亏年度流程172→88笔，均净-0.0273%→+0.0330%，避25大亏但误删21大赢家，早期更差，暂不叠加C。

C（B10全历史发现的20日深跌阈值）61笔开盘均净+0.4734%，10:00无止损+1.1389%，1%止损+0.9601%，2%止损+1.1145%；2%最差单笔-3.0840%优于无止损-4.5521%，均值小幅降低。2%悲观bar+1.0413%；最高/最低/双侧5笔删除后分别+0.5171%/+1.4310%/+0.8061%，仅对称诊断。C只有四年14个月，入场选择偏差仍在；年度入场流程172笔10:00+2%仅+0.1326%、悲观成交-0.0180%，近期37笔与C重合，不是独立验证。

优先保留C+10:00+2%及无止损对照；A次级，B延后负。分币向下取整、跳空按实际价格、2笔无条件受限退出延后而非删除。所有1103机会均解析成功，无缺失；不是资金约束账户，仍缺委托/到账/独立前瞻。日内反T暂停、正T冻结不变，未合main/交易/监控。

首轮35086745300、解释输出35087298084、分币修正最终35087815032均成功。最终代码b8deb2b7a8dc8ce28b120e1cef8646d5b16742f7，固定结果087b33677618f6048ee5490bb2e155d253db382e。输入/B08现金、训练截止/前缀、分区现金、跳空/止损/期限/延后/未来bar与悲观成交测试通过。解释性补充前12输出哈希同；分币修正改变止损统计而不改参数，风险5表/覆盖/镜像/延迟案例8文件哈希不变。

本地中文正式成果content_id=foxconn-t0-20260916-b11，SHA-256 2861df1fd938795d456570c598f69922211a93108b153b9ebb949766fe8dbf58。源数据/计算/逐笔留GitHub。[固定报告](https://github.com/chixig/daily_stock_analysis/blob/087b33677618f6048ee5490bb2e155d253db382e/research/foxconn_overnight_20260916_b11/REPORT.md)、[完整结果](https://github.com/chixig/daily_stock_analysis/tree/087b33677618f6048ee5490bb2e155d253db382e/research/foxconn_overnight_20260916_b11)。

## B12当前事实

事实：B12现有数据执行压力与事件检验完成，研究运行35124725052成功；代码5b63eeb548ae73b5087d2fb4dbf87abd9510c3f0，结果18b5840d86d075dc7a4499c3dcff94926a21eb09，15项输出。C2%删最佳现金整段均净+1.1075%，删最佳收益率之和整段+0.8319%；每段首次15笔+1.4280%，但现金仅2516.30元且删5赢家后负，暂不升级。下一bar收价且每边20bp均净+0.6944%，无止损+0.7231%。原始63信号先分15事件后筛至61，区别B11排除后16簇。

真实一分钟与61笔买卖日均无交集；买入收盘价对齐，卖出日线/五分钟极值最大差各0.13元，原因存疑，可能影响止损路径，不能宣称价格一致性全部通过。122条细数据需求为买卖用途记录，非独立日期数。执行门槛未通过，资金账户/自动前瞻未启动；下一步补候选日期细行情并解释价格差异，冻结C及退出参数。旧历史非独立OOS，无实际交易。

输入/收益复现/事件前缀与守恒/延迟价约束检查通过，补充3项摘要未改变首轮12输出哈希。本地结论《隔夜T执行压力与事件集中度检验.md》SHA256：5bebd274c019d6f425f89cb8e6e4c8e65895b22c2544b3327131c54f798e0d10。仅本研究工作流success，不认证其他工作流或真实成交。

## B13当前工作

冻结候选；追溯原始极值差、潜在止损歧义及补数路径，待运行结果。
