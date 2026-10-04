"""Package verified calculations with explicit limits; keep snapshots independent."""
import gzip
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

BASE=Path('research/foxconn_kline_20261005');ROOT=Path('research/foxconn_kline_repair_20261005');D=ROOT/'delivery'
def main():
    c=json.loads((D/'coverage.json').read_text())
    v=json.loads((D/'independent_verification.json').read_text())
    assert v['status']=='PASS'
    shutil.copyfile(BASE/'delivery/03_工业富联_每日分时.html',D/'03_工业富联_每日分时.html')
    shutil.copyfile(ROOT/'audit/publisher_row_count_comparison.csv',D/'publisher_row_count_comparison.csv')
    with gzip.open(BASE/'canonical/601138_intraday.csv.gz','rb') as src:
        with (D/'601138_intraday.csv').open('wb') as dst:shutil.copyfileobj(src,dst)
    note=f'''# 工业富联逐笔成交重建候选与全历史分时

整理于2026-10-05。本批1/5分钟数据覆盖{c['start']}—{c['end']}，{c['days']}个交易日。
全历史分时仍为2018-06-08—2026-09-30的通达信原生快照，484560个点。分时价格不参与OHLC重建。

## 本批计算与验证事实

- 取得公开逐笔源中工业富联{c['raw_trades']:,}条原下载行；剔除完全相同的重复行后为{c['unique_trades']:,}条唯一记录；1分钟{c['one_minute_rows']:,}个时间格点、5分钟{c['five_minute_rows']:,}个时间格点。
- 发布方每日条数核对：{c['publisher_row_count_check']['all_declared_row_counts_match']}；这只认证提取没有遗漏发布方已存档的行，不能认证发布方收录了交易所全部成交。
- 日线开高低收、股数和金额对账通过{c['daily_reconciliation_pass_days']}/{c['days']}日。失败日期：{c['daily_reconciliation_failed_dates']}。完整逐日差值见daily_transaction_quality.csv。
- 独立numpy重算与保存结果一致；CSV/Parquet往返核验通过。图表验证见chart_verification.json。
- 有{c['no_recorded_trade_minutes']}个分钟没有公开源成交记录，OHLC留空，不补造价格。并不据此断言交易所当时没有成交。

采集过程曾把canonical与serving两种相同存储同时读取，产生{c['exact_duplicate_rows_removed']:,}个完全重复行。原下载文件保留，计算先按全部5个源字段去除完全重复；成交编号相同但其它字段不同不会静默去除，会被质量检查标记。后续采集只选择一种存储。

## 明确口径

北京时间，不复权，价格元/股、成交量股、金额元。按time_s秒时间排序，同秒按源tran_id排序。
常规1分钟为[09:30:00,09:31:00)等区间，datetime记录结束时间；午间最后一格纳入11:30:00，收盘最后一格纳入15:00:00记录。
开盘竞价(time_s在09:15至09:30之前)单存opening_auction.csv，不并入9:31常规分钟。
日线对账含开盘竞价和常规交易，排除15:00以后及午休记录。五分钟按上述1分钟合并。
每根OHLC取该区间已取得成交的首价、最高、最低、末价；不是从每天分时点推断。
开盘竞价、原1分钟首根合并方式和秒边界口径不同，比较时需看具体定义。

## 仍未完成的任务

上市以来全部分钟真实极值尚未认证。旧332个异常日集中在2019—2021年，本批2026年逐笔不能修复这些日期。
另取得2018—2026年公开年度分钟档案，可以使旧332日中205日的日线极值对账相符，但仍留下127日并增加3个新问题日，且底层供应商未披露；不能据此宣称修复或覆盖原件。
旧591根版本冲突涉及的10个近期日期都已有逐笔记录，但新源也尚未获交易所独立完整性认证，所以不能宣称通过票数或优先级确定了交易所真值。
公开逐笔源底层供应商未披露，time_s只有秒精度，同秒先后依赖提供者成交编号；日线对账相符仍不能证明每笔全收录、分秒顺序和全部分钟极值正确。
本包是逐笔记录重建候选交付；2018-06-08—2026-03-31仍需有权访问的完整历史逐笔数据。旧全历史分钟包保留作候选证据，不能称最终全量干净数据。

## 来源

逐笔：phields/a-share-l2-trades，固定版本2f4c13ee70cabf3f8b831acf7e1686481a762eaa。
https://huggingface.co/datasets/phields/a-share-l2-trades/tree/2f4c13ee70cabf3f8b831acf7e1686481a762eaa
分时：原固定通达信快照。source_time保留09:30—11:29、13:00—14:59原标签；datetime按序对应结束标签。原量为手，乘100转股，手级精度。
公开年度档案：wind17/china-a-share-zip，固定版本ca4c51770f1fafb40317cc35bfd92e7c2be17827；发布者用户名不能当作Wind公司来源证明。
通达信官方说明分钟图可能遗漏逐笔极值：https://zxfile.tdx.com.cn/zx/201612/3185123/3185123_fj.pdf
聚宽官方说明部分分钟K线来自快照：https://test.demo.joinquant.com/community/post/detailMobile?postId=21247
原件、脚本及完整审计：https://github.com/chixig/daily_stock_analysis/tree/research/foxconn-kline-20261005/research/foxconn_kline_repair_20261005
'''
    (D/'数据说明.md').write_text(note)
    members=[p for p in sorted(D.iterdir()) if p.suffix in ['.csv','.html','.json','.md']]
    archive=D/'工业富联_20260401至20260930_逐笔重建候选_附全历史分时.zip'
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in members:
            entry=zipfile.ZipInfo(p.name,date_time=(2026,10,5,0,0,0));entry.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(entry,p.read_bytes())
    manifest={p.name:{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in members+[archive]}
    (D/'package_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
    (D/'SHA256SUMS.txt').write_text('\n'.join(v['sha256']+'  '+k for k,v in manifest.items())+'\n')
    print(json.dumps({'archive':str(archive),'bytes':archive.stat().st_size,'sha256':manifest[archive.name]['sha256']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
