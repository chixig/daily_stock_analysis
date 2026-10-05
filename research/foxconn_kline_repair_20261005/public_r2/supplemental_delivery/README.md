# 新公开来源补充验证包

本包为候选证据，不覆盖此前正式交付。2022_native文件是发布方原生OHLC，保留原时间标签；不是从每日分时推断。上游供应商和分钟聚合语义未证实。09:25和15:00竞价单列，连续分钟疑似起始标签，未重标或填空。日线对账通过不证明每分钟极值真实。

2026分类文件保留全部15:00后原记录和原秒标签。near_close_unverified为15:00至15:05前，可能是收盘撮合发布延迟；不自动搬入15:00。fixed_price_window为2026-07-06起15:05至15:30，符合新盘后固定价格时段；仅时间/价格吻合不能代替交易类型字段。

来源：
- https://huggingface.co/datasets/Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data/tree/8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441
- https://huggingface.co/datasets/phields/a-share-l2-trades/tree/2f4c13ee70cabf3f8b831acf7e1686481a762eaa
- 上交所2026-04-24发布、2026-07-06实施规则：https://star.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml
- 交易时段：https://one.sse.com.cn/onething/gptz/

来源原件、散列及逐日差异见GitHub public_extra和public_r2目录。数据运算均在GitHub Actions执行。summary.json记录全量验收结果。

## 收盘归属推定修订候选

新增2026_1min/5min_closing_assignment_candidate及两份离线图。仅把10日原始15:00:01的真实成交记录推定归入15:00收盘K线，原始成交价量不变；修订10根1m，其余29990根价量保持原版。推定依据为统一一秒标签、每批单一成交价和日线量价额吻合，仍缺源方时间语义确认。closing_label_inferred及逐行changes记录明确标示。124日通过量价额对账，7月15日仍失败；不得称交易所真值或用于宣称全历史已解决。开盘竞价另存；盘后固定价格记录保留原秒标签，未并入常规240分钟。修改的1m/5m均重新读取原始逐笔独立核验，CSV回读通过。原图表交互测试可复用模板；新图本轮仅做生成与内容检查，未重新浏览器交互验收。
