"""Separate candidate: assign observed 15:00:01 closing prints to 15:00 with explicit inference flag."""
from pathlib import Path
import json,hashlib,zipfile,gzip,base64
import pandas as pd,numpy as np
import foxconn_kline_trade_build as chart_module
R=Path('research/foxconn_kline_repair_20261005');D=R/'public_r2/supplemental_delivery';F=['open','high','low','close'];O=R/'public_r2'
s=json.loads((D/'summary.json').read_text());one=pd.read_parquet(R/'trade_reconstruction/601138_1min_trades.parquet');one.datetime=pd.to_datetime(one.datetime);original=one.copy()
late=pd.read_csv(D/'2026_post_close_classified.csv.gz',dtype={'date':str});patches=[]
one['closing_label_inferred']=False
for day,a in late[late.session_candidate=='near_close_unverified'].groupby('date'):
 assert set(a.time_s)=={54001} and a.price_x10000.nunique()==1
 i=one.index[one.datetime==pd.Timestamp(day+' 15:00:00')];assert len(i)==1;i=i[0];before=one.loc[i].copy();px=a.sort_values(['time_s','tran_id']).price_x10000/10000
 one.loc[i,'open']=px.iloc[0] if pd.isna(before.open) else before.open
 one.loc[i,'high']=max(px.max(),before.high) if pd.notna(before.high) else px.max();one.loc[i,'low']=min(px.min(),before.low) if pd.notna(before.low) else px.min();one.loc[i,'close']=px.iloc[-1]
 one.loc[i,'volume']+=int(a.volume.sum());one.loc[i,'amount']+=int((a.price_x10000.astype('int64')*a.volume.astype('int64')).sum())/10000;one.loc[i,'trade_count']+=len(a);one.loc[i,'no_recorded_trade']=False;one.loc[i,'closing_label_inferred']=True
 patches.append({'date':day,'source_time':'15:00:01','candidate_bar_end':'15:00:00','added_rows':len(a),'added_volume':int(a.volume.sum()),'added_amount':float((a.price_x10000.astype('int64')*a.volume.astype('int64')).sum()/10000),'observed_price':px.iloc[0],'before_close':before.close,'after_close':one.loc[i,'close'],'assignment_status':'INFERRED_NOT_SOURCE_TIMESTAMP'})
 # Independent direct full-field raw reconstruction for changed 1m bars.
 raw=pd.read_parquet(R/'raw/phields'/f'{day}.parquet').drop_duplicates().sort_values(['time_s','tran_id']);r=raw[(raw.time_s>=53940)&(raw.time_s<=54001)]
 expected=[r.price_x10000.iloc[0]/10000,r.price_x10000.max()/10000,r.price_x10000.min()/10000,r.price_x10000.iloc[-1]/10000]
 assert np.allclose(one.loc[i,F].astype(float),expected,atol=1e-8,rtol=0)
 assert int(one.loc[i,'volume'])==int(r.volume.sum()) and int(one.loc[i,'trade_count'])==len(r)
 assert abs(one.loc[i,'amount']-int((r.price_x10000.astype('int64')*r.volume.astype('int64')).sum())/10000)<.001
q=pd.read_csv(D/'2026_session_classification.csv');passes=q.set_index('date').including_near_close_daily_pass
one['daily_reconciliation_pass']=one.datetime.dt.strftime('%Y-%m-%d').map(passes);one['time_assignment_status']=np.where(one.closing_label_inferred,'INFERRED_CLOSING_AUCTION','SOURCE_INTERVAL')
unchanged=~one.closing_label_inferred
for k in F+['volume','amount','trade_count']:pd.testing.assert_series_equal(one.loc[unchanged,k],original.loc[unchanged,k],check_names=False)
z=one.copy();z.datetime=z.datetime.dt.ceil('5min');five=z.groupby('datetime').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),amount=('amount','sum'),trade_count=('trade_count','sum'),no_trade_minutes=('no_recorded_trade','sum'),daily_reconciliation_pass=('daily_reconciliation_pass','all'),closing_label_inferred=('closing_label_inferred','any')).reset_index();five['symbol']='601138.SH';five['source']='phields_l2_2f4c13e';five['time_assignment_status']=np.where(five.closing_label_inferred,'INFERRED_CLOSING_AUCTION','SOURCE_INTERVAL')
for day in [v['date'] for v in patches]:
 raw=pd.read_parquet(R/'raw/phields'/f'{day}.parquet').drop_duplicates().sort_values(['time_s','tran_id']);r=raw[(raw.time_s>=53700)&(raw.time_s<=54001)];b=five[five.datetime==pd.Timestamp(day+' 15:00:00')].iloc[0]
 assert np.allclose(b[F].astype(float),[r.price_x10000.iloc[0]/10000,r.price_x10000.max()/10000,r.price_x10000.min()/10000,r.price_x10000.iloc[-1]/10000],atol=1e-8,rtol=0)
 assert int(b.volume)==int(r.volume.sum()) and int(b.trade_count)==len(r)
 assert abs(b.amount-int((r.price_x10000.astype('int64')*r.volume.astype('int64')).sum())/10000)<.001
for name,d in [('2026_1min_closing_assignment_candidate',one),('2026_5min_closing_assignment_candidate',five)]:
 d.to_csv(D/(name+'.csv'),index=False,float_format='%.6f');v=pd.read_csv(D/(name+'.csv'));assert len(v)==len(d)
 for k in F+['volume','amount']:assert np.allclose(v[k],d[k],atol=1e-5,rtol=0,equal_nan=True)
pd.DataFrame(patches).to_csv(D/'2026_closing_assignment_changes.csv',index=False)
(D/'opening_auction.csv').write_bytes((R/'delivery/opening_auction.csv').read_bytes())
chart_module.DELIVERY=D
for d,mode,name in [(one,'1min','01_收盘归属推定候选_1分钟.html'),(five,'5min','02_收盘归属推定候选_5分钟.html')]:
 chart_module.chart(d,mode,name);p=D/name;h=p.read_text();h=h.replace('按公开逐笔源的记录时间和成交编号重建；开盘竞价单独保存，无成交分钟OHLC留空。上游来源尚未获独立完整性认证。','修订候选：10日15:00:01成交推定归入15:00，价格均来自原始逐笔；原秒标签另存，时间归属未获源方确认。124日量价额对账通过，7月15日缺数。开盘竞价另存、空分钟留空。');p.write_text(h)
 assert '10日15:00:01' in h and '__DATA__' not in h
s['closing_assignment_candidate']={'one_minute_rows':len(one),'five_minute_rows':len(five),'changed_one_minute_bars':len(patches),'unchanged_one_minute_bars_verified':int(unchanged.sum()),'no_recorded_trade_minutes':int(one.no_recorded_trade.sum()),'daily_pass_days':int(passes.sum()),'failed_dates':passes[~passes].index.tolist(),'changed_1m_5m_direct_raw_checks':True,'csv_roundtrip':True,'source_times_preserved_in_classified_file':True,'assignment_certified':False}
def clean(x):
 if isinstance(x,dict):return {k:clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
s=clean(s);(D/'summary.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,allow_nan=False))
with (D/'README.md').open('a') as f:f.write('\n## 收盘归属推定修订候选\n\n新增2026_1min/5min_closing_assignment_candidate及两份离线图。仅把10日原始15:00:01的真实成交记录推定归入15:00收盘K线，原始成交价量不变；修订10根1m，其余29990根价量保持原版。推定依据为统一一秒标签、每批单一成交价和日线量价额吻合，仍缺源方时间语义确认。closing_label_inferred及逐行changes记录明确标示。124日通过量价额对账，7月15日仍失败；不得称交易所真值或用于宣称全历史已解决。开盘竞价另存；盘后固定价格记录保留原秒标签，未并入常规240分钟。修改的1m/5m均重新读取原始逐笔独立核验，CSV回读通过。原图表交互测试可复用模板；新图本轮仅做生成与内容检查，未重新浏览器交互验收。\n')
files=sorted(p for p in D.iterdir() if p.is_file() and p.name!='SHA256.json');manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(D/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
zp=O/'public_source_supplement_20261005.zip'
with zipfile.ZipFile(zp,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(D.iterdir()):z.write(p,p.name)
with zipfile.ZipFile(zp) as z:
 assert z.testzip() is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
(O/'supplement_delivery_manifest.json').write_text(json.dumps({'zip':zp.name,'bytes':zp.stat().st_size,'sha256':hashlib.sha256(zp.read_bytes()).hexdigest(),'members':len(manifest)+1,'verified':True},indent=2))
print(json.dumps(s['closing_assignment_candidate'],ensure_ascii=False,indent=2))
