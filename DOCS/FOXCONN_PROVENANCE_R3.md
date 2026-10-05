# 来源追溯与同花顺核对说明

核验日期2026-10-05。状态active，沿用foxconn-t0-20261005-kline-repair。用户要求明确332日和591分钟来源，提出可提供同花顺7月15日数据，并要求继续核实可靠来源。计算、原件和来源证据仍在GitHub。

## 332个异常交易日的直接来源

事实：全部来自Hugging Face的[neigezhu/china-a-share-1min-ohlcv](https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv/tree/ba589a11534825044fe5a6b84838f50ba8d8d188)，目标文件`data/stock_1m/SH/601138.parquet`。固定版本ba589a11534825044fe5a6b84838f50ba8d8d188，目标文件SHA256为5bfaf612539495debbe441049112793ee455e33d8588f0d732e8cd9708675a43。2019年156日、2020年129日、2021年47日。

其[来源元数据](https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv/blob/ba589a11534825044fe5a6b84838f50ba8d8d188/metadata/source_provenance.json)仅说明多源异步交叉核验、1分钟、不复权、股数/人民币等口径，没有给出原始行情商、交易所原始文件或可复核的逐笔流水。

存疑：我们知道直接从哪里下载，但不知道发布者最初从哪家供应商取得、是否用快照合成。因此它是来源可定位的历史分钟文件，不能称交易所原始成交数据。现有事实是332日日内分钟极值与BaoStock及通达信日线参考不符；“都因漏成交导致”仍是未完全证实的原因判断。此前说“漏了最高/最低价”过于简化，不能反推缺失成交的具体分钟。

## 591根冲突由哪些版本产生

本轮在GitHub直接重算原冲突表，共651条两两比较、591个不同分钟：

| 本次优先采用的版本 | 对照版本 | 不同分钟数 |
|---|---|---:|
| 2026-10-05新下载通达信，pytdxdata 0.6.1 | B13研究保存的旧通达信版本 | 495 |
| 同上 | 仓库main保存的旧通达信版本 | 122 |
| 同上 | neigezhu的HF分钟文件 | 34 |

同一分钟可能与两份旧文件都不同，不能直接相加为不同分钟。这里绝大多数是同一通达信来源的不同采集版本，而非多家独立供应商。

- [B13旧文件](https://github.com/chixig/daily_stock_analysis/blob/fc832bce87c5963349bd9df9766fbf60089c385d/research/foxconn_overnight_20260917_b13/tdx_recovered_1m.csv)：2026-04-30—09-11，22320行。
- [main旧文件](https://github.com/chixig/daily_stock_analysis/blob/e428977626fa6575dc8f4a5b0693c11e93f9a4c2/data/601138_intraday/pytdxdata_1min/kline_yearly/601138_1m_kline_2026.csv)：2026-08-17—09-30，7680行。
- [新通达信原件](https://github.com/chixig/daily_stock_analysis/blob/9a51ba137149b3e40b6160f3ed8113302a307e15/research/foxconn_kline_20261005/raw/tdx_1m_fresh.csv.gz)：下载日2026-10-05。

按日期：6/15为47根，8/7为22根，8/12为3根，8/13为2根，8/17为156根，8/24为127根，8/25为187根，9/17为32根，9/23为1根，9/24为14根。完整逐行数值留在`provenance_r3/all_conflicting_versions.csv`，汇总见`conflict_source_summary.json`。

新通达信优先只是确定性选择规则，并不证明新值更准确。后来phields逐笔为额外证据，但该发布者未披露具体供应商，不能自动裁定全部分钟真值。

本轮再次逐分钟核对当前逐笔重建候选：591个争议分钟中，590个有完整候选OHLC；22个与新TDX相同，568个不同。按每分钟检查全部旧版本，49个至少有一个版本与逐笔候选相同，541个所有旧版本都不同。剩余2026-08-25 14:58无逐笔候选OHLC，处于收盘集合竞价窗口，单独保留，不能把无可比较值算作价格不同，也不能仅凭空值认定漏成交。对比容差1e-5、相对容差0；完整明细`conflicting_pairs_vs_trade_candidate.csv`，不是只对日线总账。结果说明仍需独立来源及时间标签核验，不证明逐笔候选就是真值。

## 如何用同花顺核验7月15日

用户可提供2026-07-15工业富联601138的全日1分钟K线数值：原时间标签、开高低收、成交量、成交额，选择不复权，并保留应用名称/版本及量的单位。完整CSV或Excel优于图片；若只能看屏幕，优先核对09:50—09:53附近及全日成交量、成交额，但不能据此认定其他分钟无缺口。7/15盘口与逐笔累计差额在允许10秒消息延迟后，最早于09:51:42出现。

已提供[240分钟对照模板](../research/foxconn_kline_repair_20261005/provenance_r3/20260715_ths_comparison_template.csv)，包含现有逐笔候选值和留空的同花顺字段。不得用前值填充缺失同花顺数据；两方时间标签若不同先查定义，不先改价格。

事实：[同花顺iFinD官方FAQ](https://ftwc.51ifind.com/gwstatic/static/ds_web/quantapi-web/help-center/faq.html)在解释接口和终端1分钟K线差异时，明确其分钟线由快照合成，不同采样源可有差异。这个说明针对iFinD，不能未经核实推广到所有同花顺产品，但足以否定“只要来自同花顺就一定是完整逐笔极值”。用户提供的同花顺数据能增加独立交叉证据；若与当前逐笔不同，应查具体时点和口径，不盲目选品牌覆盖。

## 继续验证的具体标准

1. 优先取得能解释上游供应商、复权、分钟边界和集合竞价处理的历史文件；同一底层源的镜像或不同采集版本只算版本复核。
2. 对10日15:00:01成交，继续查事件时间与消息发布时间语义；phields当前schema只写午夜起秒数，未提供这一区分，归入收盘仍是推定。
3. 对2022档案，来源及起始/结束标签未被公开文档确认。日线总额通过不能替代每分钟验证，仍保留4日股数差异和9日金额差异。
4. 对7/15，接入用户提供的同花顺记录后先逐分钟比较，再核全天成交量额；不以价格截图伪造缺失的280条成交。

本轮已复核发布者schema、来源元数据、公开讨论和官方FAQ。phields/SHA目录为空；当前phields逐笔版本未更新，没有可补回的新版本。继续检索发现的深交所2019—2021学术数据及2015派生指标不覆盖本股，不作为新证据。

公开新线索：[aitech17/A_history](https://github.com/aitech17/A_history)的[百度分享](https://pan.baidu.com/s/1W2TMPTHLWblKy1gBwMCIEQ)，发布者公开码i4ru验证成功。已实际列出“高频数据”目录8个文件，包括`new_tick2019-2021.zip`（20304043228字节）、`tick2018.zip`（5946412406字节）、多年1min的CSV/HDF5包及1291字节`数据说明.txt`。文件名中的tick并不自动等于完整逐笔，尚未确认包含601138。

实际访问：share/list、tplconfig和sharedownload均errno=0，但读取说明文本的下载链接HTTP403，补充正常浏览器User-Agent及Referer后仍403。未下载行情或说明，不将此线索计作新增覆盖；403的原因尚未确认，不擅称必须会员或登录。下载复核流程[37282751837](https://github.com/chixig/daily_stock_analysis/actions/runs/37282751837)成功保存诊断。后续应优先取得小型说明及压缩包目录，确认目标股票、数据类型、上游和字段，再按目标股提取；不要先下载20GB全部市场档案。

另一明确的原始来源方向是[上证所信息网络有限公司历史数据产品](https://www.sseinfo.com/services/assortment/market/hqywwd/wdcpsms/c/10782125/files/f2ba70dea74a4323bf13b76fffce0e40.pdf)：官方说明分别提供分钟K线和逐笔，逐笔含通道、逐笔序号及发送时间。其[接口文档](https://www.sseinfo.com/services/assortment/document/interface/c/10759166/files/4f38cae1022a4cfa8410bbc2702e2b95.pdf)明确Level-2的`Minute.csv`和各字段。当前只验证公开文档，未取得601138行情文件或证明存在公开免费全历史下载，也未采购。

最终逐分钟比较流程[37282949860](https://github.com/chixig/daily_stock_analysis/actions/runs/37282949860)成功；本轮固定证据提交[0020d07648aaa27e4f48496c11ce4c27509b83ea](https://github.com/chixig/daily_stock_analysis/tree/0020d07648aaa27e4f48496c11ce4c27509b83ea/research/foxconn_kline_repair_20261005/provenance_r3)。未向发布者发送消息。本轮没有增加已认证真实OHLC覆盖。
