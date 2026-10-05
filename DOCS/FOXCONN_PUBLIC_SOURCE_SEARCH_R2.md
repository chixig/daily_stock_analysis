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

## 后续可核查线索

Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data：8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441，仅2022.zip，无来源说明；可抽取601138与年度wind17档案比对，先检查是否相同副本。qfzcxdl/StockData：b1d13702003d7f084a9645c548caabbe74b82457，两Parquet、有OHLC/time字段，频率待实际抽取验证。两者均不计入已修复覆盖。

生成程序核查：TraderHarness的`traderharness/data/min5_clean.py`会删除零/负量行，按代码/时间保留最后一版。`scripts/fetch_5year_data.py`声明BaoStock来源。因此此档案与旧BaoStock表的匹配只能提供版本复核，不能作为供应商独立投票。
