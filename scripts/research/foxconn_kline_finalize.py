"""Build complete, reproducible minute data with explicit quality flags and offline charts."""
from pathlib import Path
import base64
import gzip
import hashlib
import json
import shutil
import subprocess
import zipfile
import numpy as np
import pandas as pd
from foxconn_kline_semantics import norm, fold_hf, aggregate_daily, TIMES, FIELDS

ROOT=Path('research/foxconn_kline_20261005');RAW=ROOT/'raw';AUDIT=ROOT/'audit';CLEAN=ROOT/'canonical';DELIVER=ROOT/'delivery'
START='2018-06-08';END='2026-09-30'


def save_frame(x,name):
    x.to_parquet(CLEAN/f'{name}.parquet',index=False,compression='zstd')
    x.to_csv(CLEAN/f'{name}.csv.gz',index=False,float_format='%.6f',compression={'method':'gzip','mtime':0})


def aggregate5(x):
    z=x.copy();z['bin']=z['datetime'].dt.ceil('5min')
    y=z.groupby('bin',sort=True).agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),amount=('amount','sum'),count=('datetime','size'),source=('source','first'),source_conflict=('source_conflict','max'),quality_flag=('quality_flag','first')).reset_index().rename(columns={'bin':'datetime'})
    assert (y['count']==5).all(), 'Never aggregate incomplete minute bins'
    y=y.drop(columns='count');y['symbol']='601138.SH'
    return y[['symbol','datetime',*FIELDS,'volume','amount','source','source_conflict','quality_flag']]


def chart(x,name,title,mode,quality):
    data={'days':{},'rows':len(x),'quality':quality}
    d=x.copy();d['date']=d.datetime.dt.strftime('%Y-%m-%d');d['time']=d.datetime.dt.strftime('%H:%M')
    columns=['time',*FIELDS,'volume','amount'] if mode!='intraday' else ['time','price','volume','provider_avg_price']
    for date,g in d.groupby('date',sort=True):data['days'][date]=g[columns].values.tolist()
    packed=base64.b64encode(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)).decode()
    template=Path('scripts/research/foxconn_chart_template.html').read_text()
    desc='1分钟：HF历史OHLC与通达信近期OHLC按固定优先级接续；5分钟由五个完整1分钟区间严格聚合。首根纳入开盘附加记录。'
    if mode=='intraday':desc='原生通达信分时价格、成交量和累计均价。源位置标签保存在CSV的source_time列，图中统一为分钟结束标签；分时价格不冒充分钟OHLC。'
    html=template.replace('__TITLE__',title).replace('__MODE__',mode).replace('__DESCRIPTION__',desc).replace('__DATA__',packed)
    (DELIVER/name).write_text(html)


def main():
    for p in [AUDIT,CLEAN,DELIVER]:p.mkdir(parents=True,exist_ok=True)
    daily=pd.read_csv(RAW/'old_5m/601138_daily_raw.csv');daily['date']=daily['date'].str[:10]
    daily=daily[(daily.tradestatus.astype(int)==1)&(daily.date>=START)&(daily.date<=END)].sort_values('date')
    dates=daily.date.tolist();assert len(dates)==len(set(dates))
    tdxday=norm(pd.read_csv(RAW/'tdx_daily_fresh.csv.gz'))
    assert set(dates)==set(tdxday.date), 'Independent daily trading calendars differ'
    hf=norm(pd.read_parquet(RAW/'hf_601138.parquet'))
    raw_auction=hf[hf.datetime.dt.strftime('%H:%M')=='09:30'].copy()
    raw_auction.to_parquet(CLEAN/'opening_source_records.parquet',index=False)
    hf=fold_hf(hf);hf['source']='hf_0930_fold'
    b13=norm(pd.read_csv(RAW/'b13_1m.csv'));b13['source']='b13_tdx'
    oldmain=norm(pd.read_csv(RAW/'main_1m.csv'));oldmain['source']='main_tdx'
    fresh=norm(pd.read_csv(RAW/'tdx_1m_fresh.csv.gz'));fresh['source']='tdx_20261005'
    candidates=[hf,b13,oldmain,fresh]
    # Preserve complete direct bars. A newer frozen direct TDX source wins overlapping bars;
    # this reproducible selection is not a claim that time alone proves price accuracy.
    x=pd.concat([a[['datetime','date',*FIELDS,'volume','amount','source']] for a in candidates],ignore_index=True)
    x=x[(x.date>=START)&(x.date<=END)].drop_duplicates('datetime',keep='last').sort_values('datetime').reset_index(drop=True)
    assert set(x.date)==set(dates)
    for date,g in x.groupby('date'):
        assert g.datetime.dt.strftime('%H:%M').tolist()==TIMES, f'Minute grid failure {date}'
    assert not x.datetime.duplicated().any()
    x[FIELDS]=x[FIELDS].round(2)
    x['amount']=x.amount.round(2)
    assert np.isfinite(x[FIELDS+['volume','amount']]).all().all()
    assert (x[FIELDS]>0).all().all() and (x[['volume','amount']]>=0).all().all()
    assert np.all(np.abs(x.volume-x.volume.round())<.01)
    x['volume']=x.volume.round().astype('int64')
    assert (x.high>=x[['open','close','low']].max(axis=1)).all()
    assert (x.low<=x[['open','close','high']].min(axis=1)).all()
    conflicts=[]
    for candidate in candidates:
        p=x[['datetime',*FIELDS,'volume','amount','source']].merge(candidate[['datetime',*FIELDS,'volume','amount','source']],on='datetime',suffixes=('_selected','_other'))
        delta=pd.DataFrame({c:(p[c+'_selected']-p[c+'_other']).abs() for c in FIELDS})
        bad=(delta>.005).any(axis=1)&(p.source_selected!=p.source_other)
        conflicts.append(p[bad])
    conflicts=pd.concat(conflicts,ignore_index=True)
    conflicts.to_csv(AUDIT/'canonical_source_price_conflicts.csv.gz',index=False)
    x['source_conflict']=x.datetime.isin(set(conflicts.datetime))
    # Daily price checks: keep competing references and explicit flags, never patch bars from day extrema.
    q=aggregate_daily(x).reset_index().merge(daily[['date',*FIELDS,'volume','amount']],on='date',suffixes=('_minute','_daily'))
    for c in FIELDS+['volume','amount']:q[c+'_diff']=q[c+'_minute']-q[c+'_daily']
    q['daily_ohl_match']=(q[[c+'_diff' for c in ['open','high','low']]].abs()<=.005).all(axis=1)
    q['daily_close_match']=q.close_diff.abs()<=.005
    q['legacy_close_definition']=((q.date<'2018-08-20')&~q.daily_close_match)
    q['daily_price_match']=q.daily_ohl_match&q.daily_close_match
    q['volume_abs_diff']=q.volume_diff.abs()
    q['volume_relative_diff']=q.volume_abs_diff/q.volume_daily
    q['amount_relative_diff']=q.amount_diff.abs()/q.amount_daily
    q['volume_precision_ok']=(q.volume_abs_diff<=100)|(q.volume_relative_diff<=1e-6)
    q['amount_precision_ok']=(q.amount_diff.abs()<=1000)|(q.amount_relative_diff<=1e-6)
    q['source_conflict_bars']=q.date.map(x.groupby('date').source_conflict.sum()).astype(int)
    q['source']=q.date.map(x.groupby('date').source.first())
    q['strict_eligible']=q.daily_price_match&q.volume_precision_ok&q.amount_precision_ok&(q.source_conflict_bars==0)
    q['quality_flag']=q.apply(lambda r:';'.join((["daily_extrema_mismatch"] if not r.daily_ohl_match else [])+(["legacy_close_definition_review"] if r.legacy_close_definition else (["daily_close_mismatch"] if not r.daily_close_match else []))+(["volume_mismatch"] if not r.volume_precision_ok else [])+(["amount_mismatch"] if not r.amount_precision_ok else [])+(["minute_source_conflicts"] if r.source_conflict_bars else [])) or 'checks_passed',axis=1)
    q.to_csv(CLEAN/'daily_quality.csv',index=False)
    tdx=tdxday[['date',*FIELDS]].copy();tdx[FIELDS]=tdx[FIELDS].round(2)
    tq=q.merge(tdx,on='date')
    for c in FIELDS:tq['tdx_'+c+'_diff']=tq[c+'_minute']-tq[c]
    tq.to_csv(AUDIT/'canonical_tdx_daily_comparison.csv',index=False)
    x['quality_flag']=x.date.map(q.set_index('date').quality_flag);x['symbol']='601138.SH'
    x=x[['symbol','datetime',*FIELDS,'volume','amount','source','source_conflict','quality_flag']]
    five=aggregate5(x)
    save_frame(x,'601138_1min');save_frame(five,'601138_5min')
    # Native daily snapshots, obtained afresh across every day. Never substitute bar closes.
    s=pd.concat([pd.read_csv(f) for f in sorted((RAW/'snapshot_full').glob('*.csv.gz'))],ignore_index=True)
    assert set(s.trade_date)==set(dates)
    assert s.groupby('trade_date').size().eq(240).all()
    s=s.sort_values(['trade_date','position']).reset_index(drop=True)
    assert s.groupby('trade_date').position.apply(lambda a:a.tolist()==list(range(240))).all()
    s['source_time']=s.hour.astype(str).str.zfill(2)+':'+s.minute.astype(str).str.zfill(2)
    s['datetime']=pd.to_datetime(s.trade_date+' '+s.position.map(dict(enumerate(TIMES))))
    s['price']=s.price.round(2);s['provider_avg_price']=s.avg_price.round(6)
    s['volume_lots']=s.vol
    s['volume']=(s.vol*100).round().astype('int64')
    s['source']='tdx_native_snapshot_20261005';s['symbol']='601138.SH'
    assert np.isfinite(s[['price','provider_avg_price','volume']]).all().all()
    assert (s.price>0).all() and (s.volume>=0).all() and not s.datetime.duplicated().any()
    # Snapshot and bars remain independent observations; report disagreement rather than forcing equality.
    sc=s[['datetime','price','volume']].merge(x[['datetime','close','volume']],on='datetime',suffixes=('_snapshot','_bar'))
    sc['price_diff']=sc.price-sc.close
    sc['volume_diff']=sc.volume_snapshot-sc.volume_bar
    sc['date']=sc.datetime.dt.strftime('%Y-%m-%d')
    sc['price_conflict']=sc.price_diff.abs()>.005
    sc[sc.price_conflict].to_csv(AUDIT/'snapshot_bar_price_conflicts.csv.gz',index=False)
    sq=sc.groupby('date').agg(points=('datetime','size'),price_conflicts=('price_conflict','sum'),max_price_diff=('price_diff',lambda a:a.abs().max()),snapshot_volume=('volume_snapshot','sum'),bar_volume=('volume_bar','sum')).reset_index()
    sq['volume_difference']=sq.snapshot_volume-sq.bar_volume
    sq.to_csv(CLEAN/'snapshot_daily_quality.csv',index=False)
    s['bar_close_conflict']=sc.price_conflict.to_numpy()
    s=s[['symbol','datetime','source_time','price','volume','volume_lots','provider_avg_price','source','bar_close_conflict']]
    save_frame(s,'601138_intraday')
    daily.to_csv(CLEAN/'daily_reference.csv',index=False)
    # Compare the new 5m result against the frozen original BaoStock file.
    old5=norm(pd.read_csv(RAW/'old_5m/601138_5min_all.csv'))
    c5=five.merge(old5,on='datetime',suffixes=('_new','_old'))
    mismatch=pd.DataFrame({c:(c5[c+'_new']-c5[c+'_old']).abs() for c in FIELDS}).max(axis=1)>.005
    c5[mismatch].to_csv(AUDIT/'new_old_5m_conflicts.csv.gz',index=False)
    summary={'status':'COMPLETE_COVERAGE_WITH_DISCLOSED_QUALITY_FLAGS','start':START,'end':END,'days':len(dates),'one_minute_rows':len(x),'five_minute_rows':len(five),'intraday_rows':len(s),'missing_days':0,'missing_grid_points':0,'duplicate_timestamps':0,'invalid_ohlc':0,'strict_eligible_days':int(q.strict_eligible.sum()),'daily_ohlc_match_days':int(q.daily_price_match.sum()),'daily_extrema_mismatch_days':int((~q.daily_ohl_match).sum()),'legacy_close_definition_review_days':int(q.legacy_close_definition.sum()),'other_close_mismatch_days':int((~q.daily_close_match&~q.legacy_close_definition).sum()),'volume_precision_warning_days':int((~q.volume_precision_ok).sum()),'amount_precision_warning_days':int((~q.amount_precision_ok).sum()),'source_conflict_bars':int(x.source_conflict.sum()),'snapshot_bar_price_conflict_points':int(sc.price_conflict.sum()),'old5m_price_conflict_bars':int(mismatch.sum()),'source_days':q.source.value_counts().to_dict(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),'tdx_daily_extrema_mismatch_days':int((tq[['tdx_'+c+'_diff' for c in ['open','high','low']]].abs()>.005).any(axis=1).sum())}
    (CLEAN/'coverage.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    quality={r.date:r.quality_flag for r in q.itertuples() if r.quality_flag!='checks_passed'}
    chart(x,'01_工业富联_1分钟K线.html','1 分钟 K 线','1min',quality)
    chart(five,'02_工业富联_5分钟K线.html','5 分钟 K 线','5min',quality)
    chart(s,'03_工业富联_每日分时.html','每日分时','intraday',{r.date:'snapshot_bar_disagreement' for r in sq.itertuples() if r.price_conflicts})
    readme=f'''# 工业富联历史分钟数据与离线图表\n\n整理日期：2026-10-05。覆盖2018-06-08—2026-09-30，共{len(dates):,}个交易日。\n\n## 交付文件\n\n- 601138_1min.csv：{len(x):,}根真实OHLCV分钟K线，每日240根。\n- 601138_5min.csv：{len(five):,}根5分钟K线，每日48根，由上述1分钟数据严格聚合。\n- 601138_intraday.csv：{len(s):,}个原生分时价格/量/累计均价点，每日240点，独立于K线。\n- 三个HTML：离线打开，选择日期、前后翻日、查看1/5/20日、悬停和导出所选CSV。\n- daily_quality.csv、snapshot_daily_quality.csv：逐日质量和冲突；daily_reference.csv为官方日线口径的供应商参考值。\n\n## 统一口径\n\n证券601138.SH；北京时间UTC+8；价格元/股、不复权；OHLC按0.01元报价精度去除浮点尾差；成交量股，成交额元。datetime是分钟结束标签：09:31—11:30、13:01—15:00。没有从snapshot推造OHLC，没有插值或用日线极值修补分钟。供应商已有零量平价条保留，不代表该分钟可成交。\n\nHF原文件每日241条，09:30是附加开盘记录；将其与09:31按首开、最高、最低、末收、量额相加合并为首根。重叠核验显示这消除了58根开盘价口径差异，量额也吻合旧1m；原09:30记录另存opening_source_records.parquet。它不能当成09:25实时可用报价。末日2026-08-07原HF只到10:21，已由完整近期源覆盖。\n\n1m重叠优先级：本批重新取得且固定保存的TDX > main固定快照 > B13固定快照 > HF固定快照。不按回测收益选择来源。最终按天来源：{json.dumps(summary['source_days'],ensure_ascii=False)}。5m采用统一1m聚合口径，原BaoStock5m保留为比较证据。\n\n分时为通达信原生price/vol/avg_price。原hour/minute标签为09:30—11:29、13:00—14:59，本文件保留在source_time；按顺序统一到分钟结束时间datetime。原vol单位手，volume=vol×100股（手级精度，不能当作逐股精确计量）；volume_lots保留原值。provider_avg_price为供应商累计均价。没有强行改成1m收盘价。\n\n## “干净”的实际边界\n\n结构核验：三类数据完整覆盖{len(dates):,}日，缺日0、缺分钟0、重复时间戳0、非法OHLC 0。价格准确性不能仅靠时间网格证明。保留质量标志，不能把全量覆盖包装成所有价格已经认证。\n\n- {summary['daily_extrema_mismatch_days']}日的分钟日内开高低与BaoStock日线存在超过半分的差异；与新TDX日线对比有{summary['tdx_daily_extrema_mismatch_days']}日不符。未用日线极值强行填某一分钟。\n- {summary['legacy_close_definition_review_days']}日末分钟收价不同于日线收盘，均在2018-08-20以前；此前上交所收盘价采用末笔前一分钟成交量加权平均，不能强行要求等于末笔。保留legacy_close_definition_review；该解释并非逐笔重建认证。其它收盘差异{summary['other_close_mismatch_days']}日。\n- 量/额采用明确容差：股数差≤100股或相对差≤1e-6；金额差≤1000元或相对差≤1e-6。超出分别{summary['volume_precision_warning_days']}/{summary['amount_precision_warning_days']}日。容差不是“改正”数值。\n- {summary['source_conflict_bars']}根1m在已取得其他OHLC版本间存在价格差；source_conflict显式标注。{summary['snapshot_bar_price_conflict_points']}个分时点与对应1m收价有差异，bar_close_conflict标注。\n- strict_eligible=true共{summary['strict_eligible_days']}日，含义仅为本轮日线价格/量额容差通过且无已知OHLC版本价格冲突；不代表交易所逐笔认证。要求严格筛选时按此列筛日，不得宣称筛选后仍为全量历史。\n\n## 来源与可追溯性\n\nHF候选源：https://huggingface.co/datasets/neigezhu/china-a-share-1min-ohlcv/tree/ba589a11534825044fe5a6b84838f50ba8d8d188 。原单股文件SHA256为5bfaf612539495debbe441049112793ee455e33d8588f0d732e8cd9708675a43。发布者未披露底层供应商，不能据其自述断言独立多源认证。保留其Apache-2.0许可和原始文件。\n\n旧GitHub源：main e428977626fa6575dc8f4a5b0693c11e93f9a4c2；B13文件取自fc832bce87c5963349bd9df9766fbf60089c385d；原5m附件11243418261/运行37044085482。新TDX使用pytdxdata 0.6.1，下载日期2026-10-05，原件固定保存在本研究分支。\n\n上交所历史收盘机制说明：https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20180806_4607055.shtml\n\n完整原件、来源冲突与执行脚本：https://github.com/chixig/daily_stock_analysis/tree/research/foxconn-kline-20261005/research/foxconn_kline_20261005 。本包不覆盖旧研究快照，不重算或认证旧策略收益。\n'''
    (DELIVER/'数据说明.md').write_text(readme)
    shutil.copyfile(CLEAN/'coverage.json',DELIVER/'coverage.json')
    shutil.copyfile(CLEAN/'daily_quality.csv',DELIVER/'daily_quality.csv')
    shutil.copyfile(CLEAN/'snapshot_daily_quality.csv',DELIVER/'snapshot_daily_quality.csv')
    print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':main()
