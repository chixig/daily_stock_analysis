# 工业富联额外公开数据检索（2026-10-05）

状态：active。用户要求继续自行寻找公开来源并实际验证。目标仍为2018-06-08—2026-09-30的601138真实分钟OHLC和每日分时；本记录不将目录宣传作为已获取或已验证事实。

## 实际进入GitHub抽取的来源

| 来源 | 固定版本 | 用途及边界 |
|---|---|---|
| [suncong/ashare_1min](https://huggingface.co/datasets/suncong/ashare_1min) | c05c0da3940e167d689392852e9d490107a2c3e1 | 六个宽表字段，按目标股票列抽取；无README，价格来源与时间口径待验 |
| [ANTICH/traderharness-ashare-5y](https://huggingface.co/datasets/ANTICH/traderharness-ashare-5y) | 3bf5151ab3e94851bb09dd8ade815563c44b15a6 | 2021—2026分年5m档案，生成代码fetch_5year_data.py使用BaoStock；不能默认独立供应商 |
| [phields/a-share-l2-market-depth](https://huggingface.co/datasets/phields/a-share-l2-market-depth) | 558381a6b22c9012ffcfa5c4f972eaa1633e2dcd | 同发布方盘口快照，文件目录覆盖30日，含7月15日；只作交叉诊断，不以快照合成真实OHLC |

脚本：`scripts/research/foxconn_kline_public_r2.py`。结果和目标原件：`research/foxconn_kline_repair_20261005/public_r2/`。统计结论以该目录evaluation.json及后续验证为准。

## 本轮明确排除或尚无可用标的记录

- [FinMultiTime](https://arxiv.org/html/2506.05019v1)：分钟级是新闻；表中股票价格为日线，不能补分钟OHLC。
- [FrancisYang77/100stock_1min](https://huggingface.co/datasets/FrancisYang77/100stock_1min)：发布方明确由通联L2快照合成，validation_only、research_eligible=false；不是逐笔极值。
- cooronxon/AShareTickData：cf50faff46a1118524c83b386f32e47d710441f4，18日六股票，无601138。
- jck3114/ashare-book-benchmark-train：914f6e2f3b86b5182e4e679aa861794a9e9907bd，仅2012—2017训练数据，早于本股上市且匿名sid。
- ailune99/a-stock-1min-data（80ed6a5796f3f27584e20020010d22f9501e7132）、CT-666/a-stock-1m-kline（2fee5926682e056b4f3242adc319257a8bad29ea）：只有.gitattributes，无数据。
- deerfieldgreen/stk-intraday-data-1min：美股；AlphaDojo/dojo_stock_kline：日线；zhengr/stock-tick-data：只600000、300502；均不能补本股历史分钟。
- [astock-data-toolkit](https://github.com/tiantianlaolao/astock-data-toolkit)：说明1m约90交易日、5m约488日，所谓15年并非分钟全历史；仅程序。
- A-share-replay：仍调用通达信历史分时成交接口，不是新增独立逐笔档案。
- [free-stockdb](https://github.com/hello245m/free-stockdb)：sync_url.txt只有示例配置，没有可用公开镜像；接口能力不等于已提供数据。
- [GSAS开放数据目录](https://www.gsas.edu.hk/china-stock-market-open-benchmark-datasets/)：本轮1min-Bar及Transaction Info公开链接均HTTP403，未取得文件；不绕过权限。
- mushuju分钟下载接口明确必需授权key，未取得权限，不作为免费可用源。

## 本轮新增获取及复核

- [Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data](https://huggingface.co/datasets/Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data)：固定8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441，全部146个交易日文件已抽取601138，34894行，2022-01-04—08-10，无获取失败。public_extra保留每个原生目标文件、成员哈希及逐日比较。原文件包含OHLC/成交量额与盘口字段，不是本项目从分时推造OHLC；无供应商及聚合方法说明，仍为候选。
- qfzcxdl/StockData（b1d13702003d7f084a9645c548caabbe74b82457）：实查两Parquet元数据和代码范围，系美股，未找到601138。
- [adrianteller8838/StockChina-Minute](https://huggingface.co/datasets/adrianteller8838/StockChina-Minute)：固定dc0aab6652a63cd1a6e3997b988663175b476428，README宣传5267股票，但实际1452路径中1450个CSV仅000001.XSHE—002893.XSHE；没有601138文件，不能计入覆盖。
- [luke0708/stock-data](https://github.com/luke0708/stock-data)：全量ZIP指日线，分钟/逐笔为通达信懒缓存；没有新增独立历史分钟档案。
- [aitech17/A_history](https://github.com/aitech17/A_history)：README提供2005—2021分钟/tick百度公开分享（1W2TMPTHLWblKy1gBwMCIEQ，公开码i4ru）；网页工具未能打开，本轮未取得文件，不宣称已验证覆盖。
- [submato/ashare-l2](https://github.com/submato/ashare-l2)：公开夸克5—6月分享8bae13aef6a9、公开码Gxcc。GitHub端分享令牌请求30秒超时，错误已记录，未取得文件。
- [CUHK-SZ-quant/Factor_Sample_V2](https://github.com/CUHK-SZ-quant/Factor_Sample_V2)使用同名AllSymbols_1min文件及09:30—15:00筛选，但没有数据和档案上游对应证明；不据此认定新档案来自Wind或有大学认证。

## 已得到的反证与限制

suncong：1889日453360个非空分钟，2018-06-11—2026-03-26；上市日与2026-03-16缺失。2023-11-29全240行OHLC结构不合法，开盘字段约9万而其余价格15元左右，原件保留，不按猜测比例修补。362日日线OHLC失败；原332日中仅77日极值相符、255仍失败，不能整体替换。

ANTICH：2021/22样本399日19152根5m，日线OHLC及股数全相符，2773根与旧5m有字段差异。生成程序TraderHarness的scripts/fetch_5year_data.py明确调用BaoStock；min5_clean.py删除零/负量并去重。这是BaoStock派生档案，不是独立供应商。初次本项目glob误读自己输出导致行数翻倍已修正；最终原始两文件零重复，不把该错误归咎源数据。

盘口快照：四日目标记录已获取。2026-07-15最终累计257338笔、91756030股；逐笔257058笔、91664430股，少280笔/91600股。允许10秒发布延迟后，首个正累计缺口仍在09:51:42出现。三日重新读取canonical完整12字段（4/21、7/15、7/16），关键五字段与此前serving逐笔完全一致，未补回缺失。此为来源之间的不一致证据，盘口快照不用于造分钟极值。

## 盘后交易分类纠正

[上交所2026规则](https://www.sse.com.cn/lawandrules/sselawsrules2025/trade/universal/c/c_20260424_10816492.shtml)2026-07-06生效，盘后固定价格交易扩至全部A股；[时段说明](https://one.sse.com.cn/onething/gptz/)为15:05—15:30。此前把所有15:00后记录统称待解释盘后，分类过粗，应区分15:00附近的可能延迟收盘消息和15:05后的固定价格交易候选。完整12字段显示7/16盘后273行没有盘中相同委托字段元组，不能说它们是重复垃圾。原秒标签全部保留，缺少交易类型字段时不擅自认证或搬移。

最终全量质量统计及本次补充包见public_r2/supplemental_delivery/summary.json；原有1m/5m及原生每日分时交付保持独立。2019—2021的332日、旧591分钟冲突没有因增加公开来源而自动解决。

## 全量验收结论（2026-10-05本轮）

2022档案146日全部每日239行，时间集合一致，零缺日、重复、空OHLC和非法OHLC。每日累计量额与区间累计一致。146日日线OHLC相符，4日量额明显不足（1/6少16500股、2/7少179000股、6/20少507000股、6/21少492811股）；另外9日只有金额差额超过1元。最终142日OHLC和股数通过，133日再加金额1元条件通过，不能将三个样本通过外推全量。连续时间+1分钟而竞价原标签不变的假设下，34748个可对齐分钟中18247根仍与旧版不同；假设仅用于比较，不认证哪个版本是真值。

125日逐笔全部重新按交易阶段分类：10日共有38553条15:00:01记录，每日单价；45日共有15526条15:05—15:30记录，均在7/6新规之后、价格等于各日收盘价，15:30后记录0。前10日只纳入15:00:01、排除15:05后成交时，日线开高低收及股数金额全部吻合，整体124/125日通过，剩7/15。原“11日未对账、其中7日可解释”是旧分类版本，新增分类解释了另3日，不能继续作为最新结论。

另交收盘归属推定候选：只把已获取的15:00:01成交纳入15:00分钟，10根1m改变，其余29990根价量保持一致；相应5m重新聚合，并独立读取10日原始成交验证1m和5m。原秒标签、旧版、竞价和盘后窗口记录均保留。该操作只推定时间归属，价格取逐笔原值；时间语义仍未获源方确认，故不冒充认证版。7/15的缺数仍不能恢复；不因日线对账而宣称每分钟真值已获证明。

固定最终证据：[71c7655e](https://github.com/chixig/daily_stock_analysis/tree/71c7655e5f49399d267758ca0b0ea438abb0653e/research/foxconn_kline_repair_20261005/public_r2)，[流程37262963777](https://github.com/chixig/daily_stock_analysis/actions/runs/37262963777)。补充ZIP13成员、2620464字节，SHA256为94fa5edab4a78617ed48122b8964dbbbecd1ff35b23dd4b64ac69cb95ea8f5f5。
