---
id: foxconn-overnight-plan-b08
title: 工业富联收盘买次日开盘卖研究方案 V1.0
type: project
status: proposed
graph: false
domain: 投资研究
direction_id: foxconn-t0
content_id: foxconn-t0-20260916-b08
created: 2026-09-16
updated: 2026-09-16
confidence: medium
need_review: true
---

# 工业富联收盘买、次日开盘卖研究方案 V1.0

## 1. 决策、目标与边界

**用户决定（2026-09-16）：暂停“开盘卖、收盘买”反T研究，转向研究“收盘买、次日开盘卖”，本次先形成详细方案并查看 GitHub 既有数据。** 本文为 proposed 研究设计，数据盘点已做，新隔夜回测尚未运行。沿用 direction_id=foxconn-t0，新批次 B08；不另立长期方向，不改冻结日内正T四阶段。

观点：核心问题不是找到最高胜率，而是判断工业富联是否存在扣成本后、有足够重复性且可实际捕捉的隔夜收益，以及什么事前条件能改善收益或尾部风险。反T失效不推出隔夜盈利；日内正T的反向与隔夜不是同一标签。

先研究独立的1000股隔夜浮动仓：交易日t收盘买，下一交易日t+1开盘卖，未触发时持现金。1000股及佣金沿用研究假设，不代表真实账户。底仓+浮动仓的组合放到独立策略通过后检查；不混入底仓自然上涨收益。

## 2. 已核验的 GitHub 资产及限制

本次通过 gh API 只读检查仓库目录、清单、覆盖报告、审计、部分结果和代码，未克隆仓库、下载行情包或运行回测。可见仓库中确认投资研究入口为 chixig/daily_stock_analysis；并未对所有仓库内容做穷尽审计。

固定结果提交：`4ca9fe8092262031d52c27ef321784fe990c8a88`。B07分支本次头提交为`091594ceeef76dd90fa60e7ae4f247bb806a5ac4`，比较结果显示仅新增文档更新，研究数据未变。

| 资产 | 本次查到的事实 | 可复用用途与限制 |
|---|---|---|
| B01日线及现金流底表 | 旧审计载明2018-06-08至2026-09-11共2007日 | 可重建相邻交易日隔夜标签；2007日不等于2007笔隔夜交易，最后一日缺下一开盘，停牌/事件另处理 |
| 五分钟历史ZIP及审计 | 包已存GitHub；旧审计载明1624个交易日，开价差>0.01元为0日，收价差>0.01元为4日 | 用于14:50信号和延迟卖出近似；必须先检查实际覆盖、bar起止含义及4个差异日 |
| pytdxdata一分钟K线 | coverage.json：2026-08-17至09-11，4800行、20日 | 近期精细核对；不能称长期一分钟K线 |
| pytdxdata分时快照 | coverage.json：2018-06-08至2026-09-11，2006日、481440行，时间09:30—14:59 | 旧审计缺2019-08-16；首价与日线开价差>0.01元有1777日，不能用首价替代集合竞价开盘价 |
| 上证指数、NASDAQ、SOX | B02/B03已有文件及历史覆盖检查 | 上证可作市场背景；海外只用t收盘前已结束的交易日，不得用当晚美股解释成t日买入信号；上证不是行业指数 |
| B01—B07代码及结果 | 成本、分期、镜像、逐年训练、扰动/前缀检查已有实现 | 复用基础设施；旧cashflow是同日O/C函数，不能简单改标签就当隔夜引擎 |
| 除权线索 | 旧审计列9个action_ratio异常日期 | 仅线索，非已核验分红台账；要核对登记日、除息日、派息和股数变化 |

事实（旧结果、本次读取，未重算）：B07同一BASE在2020—2023有32笔、平均净收益−0.764%；2024以来30笔、+1.355%；2020以来62笔、+0.261%，删五大赢家后−0.194%。它说明时代差异和利润集中度需要正面检验，不证明任何隔夜结论。

重点经验：不把高胜率当高期望；不因早期反证不利而删年份；每个过滤同时交代被排除的交易；禁止无限AND组合；已反复看过的历史不能重新命名为独立样本外；保留低频线索但不升级为可交易规则。

## 3. 先固定标签、信号和交易时点

令n(t)为交易所日历的下一交易日，不是简单自然日+1；如股票停牌，主表记录未能按计划退出，不能跳过停牌后伪装成普通一夜持仓。

理论价格标签：`r_price(t)=O[n(t)]/C[t]-1`。另列含权益经济收益；价格与总收益不得混在同一列。

| 版本 | 决策输入截止 | 买入与卖出 | 地位 |
|---|---|---|---|
| ON0无条件基准 | 收盘前已决定每日参与 | t收盘价→下一交易日开盘价 | 隔夜价格及成本基准，成交仍是假设 |
| ON1前日信息版 | t−1收盘已知信息 | t收盘集合竞价→下一交易日开盘集合竞价 | 全历史可做的条件基准，信息有一日滞后但时点清楚 |
| ON2当日尾盘版 | t日14:50已完成且已收到的bar | t收盘集合竞价→下一交易日开盘集合竞价 | 优先研究的实际候选；仅在尾盘数据合格区间评价 |
| ON2执行压力 | 与ON2同一信号 | 收盘成交近似；次日09:30后首个可用窗口及09:35固定窗口卖出 | 分开报告时延侵蚀，不从多个出口挑最佳 |

ON2必须用截至14:50累计高低价、累计量及当时价格；禁止用15:00收盘、全天最高最低价、全天成交量计算14:50信号。若bar标记14:50实际是起始时刻，该bar不能用于14:50决策。数据无发布延迟字段时记录假设并做延后一根bar压力。

日线最终CLV/量比可以用于ON1，也可作为事后机制诊断；不能当作ON2可执行信号。买入后才出现的公告、美股涨跌、次日竞价仅可用于归因；若以后研究次日动态退出，应另立版本并更换成交时点。

交易机制依据：上交所材料说明收盘集合竞价14:57—15:00、开盘集合竞价9:15—9:25，收盘集合竞价不接受撤单。2018-08-20之前机制不同，早期历史另标。2026修订通知含暂缓条文且网页状态标签与正文日期不一致，执行前按正文及暂缓条款再次核对；本方案不依赖盘后固定价格交易。理论开收价不等于保证足额成交。

## 4. 第一阶段：数据审计与无条件基准

1. 固定原始提交、输入SHA-256、下载来源、数据截至日、时区和交易日历；日线/五分钟/快照分层，不能静默填补。先用截至2026-09-11旧样本；新增数据另做增量版本。
2. 检查相邻买卖日期、重复、缺失、价格单位、成交量是否累计、整手、停牌、涨跌停及公司行动；日线与分钟对账。缺数据、无信号、未成交分别计数。
3. 重建未复权现金账和仅使用当时已发生公司行动的连续价格特征。跨除息夜既报告价格收益，也报告股息应收及税后敏感性；未知分红税不可填0。无法核实事件时该组明确未完成，全样本策略不能据此认证。
4. 同时报告全历史、2020以来主窗、2020—2023、2024以来、逐年、完整滚动12个月；按买入日归属，跨年交易同时保留卖出日。不完整2026年度明确YTD。
5. ON0与买入持有、日内O→C做收益来源对照：普通非事件日可检查`(1+r_overnight)*(1+r_intraday_next)=C_next/C_t`，不能简单相加。周五/节前与普通夜分组展示真实日历暴露天数。
6. 主输出：N、月/季度覆盖、净胜率、平均/中位净收益、PF、累计现金、每笔费用、最差笔、尾部5%平均损失、最大回撤、最长连亏、资金占用；隔夜持仓期间即使不能交易也持续计入风险。

第一阶段回答：毛收益有无空间、成本是否吞噬空间、优势在哪些时期、是否只靠少数大跳空。无条件亏损不自动否决条件策略，但只能进入下述固定有限假设，不追加无边界搜索。

## 5. 第二阶段：有限条件研究

观点／提议：第一轮最多8条单条件，先不做交叉组合、机器学习或按四阶段分别调参。方向性机制均为推测，须允许数据推翻。

统一变量：ON1使用t−1最终日线；ON2使用t日14:50截面。`CLV=(P−L)/(H−L)`，H=L记未知；`R3`为相对三个交易日前收盘的连续价格收益；量比ON1为当日量/此前20日均量，ON2为截至14:50累计量/此前20日同一时点均量，不能直接复用全天量阈值口径。所有阈值为研究提议，非已验证最优参数。

| ID | 固定条件 | 推测与要检验的反证 |
|---|---|---|
| F1 | CLV≥0.8 | 强势延续或追高透支 |
| F2 | CLV≤0.2 | 尾盘弱势修复或继续下跌 |
| F3 | R3≤−4% | 短线超跌回补或趋势下行 |
| F4 | R3≥4% | 动量延续或获利兑现 |
| F5 | 同时点量比≤0.8 | 抛压衰减或关注度不足 |
| F6 | 同时点量比≥1.5 | 信息冲击延续或拥挤交易 |
| F7 | 个股当日收益−上证同区间收益>0 | 相对强势是否延续；无合格指数分钟时ON2此条件记不可用 |
| F8 | 下一交易日与t相隔≥3个自然日 | 长休市窗口的收益与尾部风险是否不同 |

每条均展示命中与未命中、同有效日期基准、条件相对基准增量、缺失率；正负两边都披露。ON1/ON2属于不同信息规格，最多16条完整规则，不能只公布赢家。F8两版本相同只计算一次，登记别名。

已有四阶段只使用冻结定义、以t−1已知状态做描述分组；不强迫四阶段各产出策略，不把阶段分组的最好格子选成第17条候选。波动率、市场趋势也先作诊断，若拟成为过滤须进入下一版本另登记。

第一轮结束后至多提出2个具有单因子支持且机制不同的二条件组合，需单独写明证据、反证和新增试验数后再进入下一研究批次，不在本轮边跑边加。相邻阈值仅作固定敏感性：CLV尾端0.15/0.20/0.25及0.75/0.80/0.85；R3幅度3/4/5%；量比低0.7/0.8/0.9、高1.3/1.5/1.7；不改主参数，不组合邻域择优。

## 6. 第三阶段：成本、成交和账户验证

每笔净利润：`实际卖出股数×实际卖价−实际买入股数×实际买价−双边佣金−卖出日税费−其他费用+权益收益`，完整持仓变化需逐笔守恒。收益率以实际买入资金（含买入费用）为分母，另报未含费名义收益以便核对。

沿用的研究佣金为0.0001354、每单最低5元；旧代码单边滑点0.0005，过户费用恒定情景0.00001。上述仅旧模型假设，不是账户已确认费率。新模型按买/卖各自日期配置税费，不能把买入日税率用于跨政策日卖出；历史过户费需补查。并列“历史费率”和“统一现行费率情景”，不能混称真实历史。

滑点固定每边0/5/10/20基点：0仅理想上界，5为旧基准，10为主要压力，20为更苛刻压力。佣金最低收费直接逐单计算；按100/500/1000股做资金规模敏感性，不把历史低价时代的最低佣金影响忽略。

成交约束：买涨停、卖跌停、无量、停牌、竞价量不足/未知均建标记。缺盘口时提供理想成交与保守排除/延后退出两种情景，不能声称模拟真实排队。未卖出头寸保留、持续盯市至可退出，禁止删除坏交易或按计划开盘价强平；未平仓浮动仓不再叠加新仓。部分成交费用及剩余仓单独登记。

资金账户：主策略固定1000股、不可融资；冻结起始日所需1000股资金及缓冲假设，现金不足则记录跳过及累计影响，不事后补充无限资金。并列固定初始资金等权投入作为可比情景，明确它是不同仓位模型。年化只从包含闲置现金与持仓市值的账户权益计算，不用每笔均收益乘252。

若独立策略通过，再比较同一初始资本下：现金、买入持有、冻结日内正T、隔夜、日内+隔夜。底仓与浮动仓按可卖批次周转；如果隔夜退出占用同一开盘操作，先去重和净额撮合，再计算费用，不双算卖出、资金和利润。

## 7. 稳健性、证伪与收口

固定统计：日历月区块重采样，2000次、seed=601138，均净收益及条件增量95%区间；对有效候选同时进行多重比较调整（例如Holm，清楚列出检验家族），邻域和阶段表保留探索标签。区块区间也不能抹去既有历史被多次探索的事实。

必做压力：删最大1/5/10笔赢家；留一年检验及逐年贡献；5日相邻事件聚类；周末/节假日前后；公司行动组；两种信息截止；双倍滑点；延迟一根bar；日线与分钟公共样本。所有删除仅是敏感性，不从正式台账抹去事件。既报元，也报百分比，避免高价年份自然支配1000股现金利润。

分级门槛均为本次提议：

- **观察线索**：N<60、覆盖少于3个年份、任一早/近期子窗N<20，或区间跨零；即使高胜率也保留这个等级。低频事件不删除。
- **历史稳健候选**：主窗与早/近期平均净收益均>0，至少3个年份净正；总N≥60且早/近期各≥20；主窗删5赢家后现金与均净收益仍正；10基点每边压力仍正；公共样本延迟退出仍正；平均净收益和条件增量区间支持正值且多重比较通过。无法取得足够执行样本则不认证执行；样本较小不能靠放宽门槛升级。
- **未通过/证伪**：利润集中在单年/少数大跳空，成本后转负，修正时间泄漏或除息后消失，或无法按所声称时点执行。写出具体失败原因，不把“全部规则没通过”包装成空仓盈利策略。

门槛是研究收口标准，非统计定律，也不是交易许可。无需为了达到N而降低主阈值。稳健候选若为0，本轮可以正确结束。

历史年度步进：2020—2021作最早训练，2022起逐年只按此前数据选择符合门槛的一条规则或NONE，选择排序依次为删5赢家后平均净收益、N、规则ID；跨年未退出标签不得进入训练。称“回溯步进诊断”，不称干净OOS。

真正前瞻从规则与信号流程冻结、在买入前留有时间戳的首日开始；不是把2026-09-12以后自动视为前瞻。可建议先观察60个交易日、30次触发后复核；不足则延期，仅为初步复核而非收益认证。启动监控或模拟记录另在后续实施，不在本次自动创建。

相反方向线索：对净亏区域，独立计算相同隔夜日期的“有旧仓、收盘卖次日开盘买”相对持有的现金增量，计全成本和补仓资金，不简单取反。登记不等于恢复已暂停的日内反T，也不引入裸卖空。

## 8. 实施次序与交付

| 阶段 | 交付 | 完成判据 |
|---|---|---|
| A数据与基准 | 覆盖/异常/权益事件表、ON0分期统计、收益来源分解 | 缺失和未平仓可解释，跨日现金流与时间校验通过 |
| B有限假设 | 全量试验登记、ON1/ON2每规则结果与反证 | 无未来字段；命中/非命中/未知可还原全集，不隐藏失败 |
| C执行与稳健 | 成本/延迟/未成交压力、账户曲线、有限候选清单 | 公共样本可比、现金和库存守恒、尾部损失完整 |
| D结论 | 支持证据、反对证据、证伪条件、是否值得前瞻 | 明确通过、观察或不采用；未验证项不称完成 |

新代码/行情/逐笔台账拟保存在GitHub独立分支`research/foxconn-overnight-20260916-b08`及`research/foxconn_overnight_20260916_b08/`，本次尚未创建。source/work/archive仍在GitHub，结果固定提交和SHA-256；本地output仅方案、研究结论、来源链接和交付哈希。保留全部B01—B07历史，反T仅暂停不删除。

最小审计检查：下一交易日映射；买前特征available_at；未来价格/量扰动不改变既有信号；前缀计算一致；缺失不转false；跨年标签清除；成交数量/现金/权益守恒；未平仓计入回撤；佣金下限与买卖日期税费；分组并集/交集；bar端点核对；最后一天无退出价格不生成完成交易。

本轮结论（观点）：已有数据足以启动长期隔夜基准和前日信息规则；14:50尾盘版的开工前置条件是分钟字段语义与覆盖审计。应先回答隔夜收益究竟来自哪里，再判断哪些条件有增量；目前没有证据承诺该方案优于已暂停反T。

## 9. 证据入口

以下GitHub均固定至结果提交，数据截至日为2026-09-11；访问核对日2026-09-16，不等于行情更新日。

- [B07覆盖表](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260915_b07/coverage.csv)
- [B07结果](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260915_b07/results.csv)
- [B07清单及哈希](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260915_b07/manifest.json)
- [B01审计及除权线索](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/research/foxconn_t0_20260913/results/audit.json)
- [分钟覆盖](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/data/601138_intraday/pytdxdata_1min/coverage.json)
- [分钟探测记录](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/data/601138_intraday/pytdxdata_1min/probe_report.json)
- [旧现金流与审计代码](https://github.com/chixig/daily_stock_analysis/blob/4ca9fe8092262031d52c27ef321784fe990c8a88/scripts/research/foxconn_t0_audit.py)
- [上交所收盘机制说明](https://edu.sse.com.cn/best/article/gsxlsc/c/4725367.shtml)
- [上交所2018调整通知](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml)
- [上交所2026交易规则通知及暂缓实施附件](https://www.sse.com.cn/lawandrules/sselawsrules2025/fund/trading/c/c_20260424_10817739.shtml)


## Execution contract frozen before first B08 run
User authorized execution 2026-09-16. Independent study branch only, no main merge/live trading/monitoring. All market computation and detailed evidence remain on GitHub. Full original Chinese design above; thresholds unchanged.
First run uses vendor cash-dividend implementation table (Sina; nine events match prior action flags),20% overnight tax baseline with0/10/20 sensitivities. Primary announcement and settlement audit not yet complete. Accounts credit ex-date dividend receivables as a scenario, not actual bankable cash certification. Price-only and corporate-event rows retained.
ON2 F7 is unavailable without intraday SSE data; never substitute daily final SSE close. ON2 F8 aliases ON1 F8. Missing features are explicit unknown. Historical numeric gates and execution certification kept separate.
The two fixed exit approximations are first09:30-09:35 bar close and09:35 next-bar open; both carry timestamps, neither is a guaranteed auction fill. Full-day minute QC affects execution comparison only, not signal selection.14:45 features stress one-bar information latency.
Annual selector training requires N60,three positive years,positive mean/delete5 mean and cash; starts2022 and may selectNONE. Gates are frozen before outcomes. Retrospective selection is diagnostic, not the full historical candidate gate and not independent OOS.
Conservative account assumes full1000-share orders only,rejects close at upper-limit proxy,defers lower-limit opening sells,halts new additions while held,cash constrained. Partial fills and auction queues unavailable, so execution remains uncertified. Drawdown samples open and close, not tick-level extrema. No strategy combination before independent strategy passes.
