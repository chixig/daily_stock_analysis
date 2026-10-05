"""Audit public archive at native labels; classify recent trade sessions without rewriting timestamps."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib,zipfile
R=Path('research/foxconn_kline_repair_20261005');B=Path('research/foxconn_kline_20261005');O=R/'public_r2';E=R/'public_extra';D=O/'supplemental_delivery';D.mkdir(exist_ok=True)
F=['open','high','low','close'];ref=pd.read_csv(B/'canonical/daily_reference.csv').set_index('date');old=pd.read_parquet(B/'canonical/601138_1min.parquet');old.datetime=pd.to_datetime(old.datetime)
frames=[];qc=[]
for p in sorted(E.glob('*AllSymbols_1min_601138.parquet')):
 d=pd.read_parquet(p).sort_values('datetime');d.datetime=pd.to_datetime(d.datetime);day=d.datetime.iloc[0].strftime('%Y-%m-%d');tm=d.datetime.dt.strftime('%H:%M')
 invalid=(d.low>d.high)|(d.open<d.low-1e-7)|(d.open>d.high+1e-7)|(d.close<d.low-1e-7)|(d.close>d.high+1e-7)|(d[F]<=0).any(axis=1)
 r={'date':day,'rows':len(d),'duplicates':int(d.datetime.duplicated().sum()),'null_ohlc':int(d[F].isna().any(axis=1).sum()),'invalid_ohlc':int(invalid.sum()),'negative_volume':int((d.volume<0).sum()),'negative_turnover':int((d.turnover<0).sum()),'zero_volume':int((d.volume==0).sum())}
 expected=set(pd.date_range(day+' 09:30',day+' 11:29',freq='min').strftime('%H:%M'))|set(pd.date_range(day+' 13:00',day+' 14:56',freq='min').strftime('%H:%M'))|{'09:25','15:00'}
 r['native_grid_missing']=';'.join(sorted(expected-set(tm)));r['native_grid_extra']=';'.join(sorted(set(tm)-expected))
 vals={'open':d.open.iloc[0],'high':d.high.max(),'low':d.low.min(),'close':d.close.iloc[-1],'volume':d.volume.sum(),'amount':d.turnover.sum()}
 for k,v in vals.items():r[k+'_diff']=float(v-ref.loc[day,k])
 r['daily_ohlcv_pass']=all(abs(r[k+'_diff'])<.005 for k in F) and r['volume_diff']==0
 r['daily_ohlcv_amount_1yuan_pass']=r['daily_ohlcv_pass'] and abs(r['amount_diff'])<=1
 r['cumulative_volume_error_rows']=int(((d.acc_volume-d.volume.cumsum()).abs()>1e-7).sum());r['cumulative_turnover_error_rows_1yuan']=int(((d.acc_turnover-d.turnover.cumsum()).abs()>1).sum())
 r['max_cumulative_turnover_error']=float((d.acc_turnover-d.turnover.cumsum()).abs().max())
 # Alignment hypothesis only. Opening auction kept separate, closing auction stays 15:00.
 z=d[tm!='09:25'].copy();continuous=z.datetime.dt.strftime('%H:%M')!='15:00';z.loc[continuous,'datetime']+=pd.Timedelta(minutes=1)
 m=z.merge(old,on='datetime',suffixes=('_new','_old'));bad=pd.Series(False,index=m.index)
 for k in F:bad|=(m[k+'_new']-m[k+'_old']).abs()>.005
 r['hypothesis_overlap']=len(m);r['hypothesis_ohlc_conflicts']=int(bad.sum())
 r['native_sha256']=hashlib.sha256(p.read_bytes()).hexdigest();qc.append(r)
 x=d[['symbol','datetime',*F,'volume','turnover','acc_volume','acc_turnover']].rename(columns={'datetime':'source_datetime','turnover':'amount','acc_volume':'source_acc_volume','acc_turnover':'source_acc_amount'})
 x['session_by_native_label']=np.where(tm=='09:25','opening_auction',np.where(tm=='15:00','closing_auction','continuous'))
 x['source']='Foxintohumanbeing_8b9cc977';x['minute_semantics_verified']=False;x['daily_ohlcv_pass']=r['daily_ohlcv_pass'];frames.append(x)
q=pd.DataFrame(qc);q.to_csv(D/'2022_daily_quality.csv',index=False);x=pd.concat(frames,ignore_index=True);x.to_csv(D/'2022_native_1min_ohlcv_candidate.csv.gz',index=False)
expected_dates=set(ref.loc[q.date.min():q.date.max()].index);actual=set(q.date)
summary={'archive_2022':{'days':len(q),'rows':len(x),'start':q.date.min(),'end':q.date.max(),'missing_reference_dates':sorted(expected_dates-actual),'row_counts':{str(k):int(v) for k,v in q.rows.value_counts().items()},'duplicate_rows':int(q.duplicates.sum()),'null_ohlc_rows':int(q.null_ohlc.sum()),'invalid_ohlc_rows':int(q.invalid_ohlc.sum()),'native_grid_bad_days':int(((q.native_grid_missing!='')|(q.native_grid_extra!='')).sum()),'daily_ohlcv_pass_days':int(q.daily_ohlcv_pass.sum()),'daily_ohlcv_amount_1yuan_pass_days':int(q.daily_ohlcv_amount_1yuan_pass.sum()),'failures':q[~q.daily_ohlcv_amount_1yuan_pass].to_dict('records'),'cumulative_volume_error_rows':int(q.cumulative_volume_error_rows.sum()),'cumulative_turnover_error_rows_1yuan':int(q.cumulative_turnover_error_rows_1yuan.sum()),'max_abs_amount_diff':float(q.amount_diff.abs().max()),'hypothesis_overlap':int(q.hypothesis_overlap.sum()),'hypothesis_ohlc_conflicts':int(q.hypothesis_ohlc_conflicts.sum()),'source_certified':False}}
# Distinguish near-close emissions and post-July-6 fixed-price window. All raw timestamps stay unchanged.
recent=[];late_frames=[]
for p in sorted((R/'raw/phields').glob('*.parquet')):
 day=p.stem
 if day not in ref.index:continue
 d=pd.read_parquet(p).drop_duplicates().sort_values(['time_s','tran_id']);d['amount']=d.price_x10000.astype('int64')*d.volume.astype('int64')/10000
 a=d[(d.time_s>54000)&(d.time_s<54300)];b=d[(d.time_s>=54300)&(d.time_s<=55800)];c=d[d.time_s<54300]
 late=d[d.time_s>54000].copy();late['date']=day;late['session_candidate']=np.where(late.time_s<54300,'near_close_unverified',np.where((day>='2026-07-06')&(late.time_s<=55800),'fixed_price_window','outside_rule_window'));late_frames.append(late)
 r={'date':day,'near_close_rows':len(a),'near_close_volume':int(a.volume.sum()),'near_close_min_s':None if a.empty else int(a.time_s.min()),'near_close_max_s':None if a.empty else int(a.time_s.max()),'near_close_unique_prices':int(a.price_x10000.nunique()),'fixed_window_rows':len(b),'fixed_window_volume':int(b.volume.sum()),'fixed_window_after_rule_start':day>='2026-07-06','fixed_window_prices_equal_daily_close':bool(((b.price_x10000/10000-ref.loc[day,'close']).abs()<.005).all()),'other_post_close_rows':int((d.time_s>55800).sum()),'near_close_first_id':None if a.empty else int(a.tran_id.iloc[0]),'session_last_id':int(d[d.time_s<=54000].tran_id.iloc[-1])}
 vals={'open':c.price_x10000.iloc[0]/10000,'high':c.price_x10000.max()/10000,'low':c.price_x10000.min()/10000,'close':c.price_x10000.iloc[-1]/10000,'volume':c.volume.sum(),'amount':c.amount.sum()}
 for k,v in vals.items():r['including_near_close_'+k+'_diff']=float(v-ref.loc[day,k])
 r['including_near_close_daily_pass']=all(abs(r['including_near_close_'+k+'_diff'])<=.005 for k in F) and r['including_near_close_volume_diff']==0 and abs(r['including_near_close_amount_diff'])<=.02
 recent.append(r)
t=pd.DataFrame(recent);t.to_csv(D/'2026_session_classification.csv',index=False);pd.concat(late_frames,ignore_index=True).to_csv(D/'2026_post_close_classified.csv.gz',index=False)
summary['recent_session_audit']={'days':len(t),'near_close_days':t[t.near_close_rows>0].to_dict('records'),'fixed_price_window_days':int((t.fixed_window_rows>0).sum()),'fixed_price_window_rows':int(t.fixed_window_rows.sum()),'fixed_price_before_rule_days':t[(t.fixed_window_rows>0)&~t.fixed_window_after_rule_start].date.tolist(),'fixed_price_price_mismatch_days':t[(t.fixed_window_rows>0)&~t.fixed_window_prices_equal_daily_close].date.tolist(),'including_near_close_daily_pass_days':int(t.including_near_close_daily_pass.sum()),'still_failing':t[~t.including_near_close_daily_pass].to_dict('records'),'other_post_close_rows':int(t.other_post_close_rows.sum()),'timestamps_modified':False}
(D/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
(D/'README.md').write_text('''# 新公开来源补充验证包\n\n本包为候选证据，不覆盖此前正式交付。2022_native文件是发布方原生OHLC，保留原时间标签；不是从每日分时推断。上游供应商和分钟聚合语义未证实。09:25和15:00竞价单列，连续分钟疑似起始标签，未重标或填空。日线对账通过不证明每分钟极值真实。\n\n2026分类文件保留全部15:00后原记录和原秒标签。near_close_unverified为15:00至15:05前，可能是收盘撮合发布延迟；不自动搬入15:00。fixed_price_window为2026-07-06起15:05至15:30，符合新盘后固定价格时段；仅时间/价格吻合不能代替交易类型字段。\n\n来源：\n- https://huggingface.co/datasets/Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data/tree/8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441\n- https://huggingface.co/datasets/phields/a-share-l2-trades/tree/2f4c13ee70cabf3f8b831acf7e1686481a762eaa\n- 上交所2026-04-24发布、2026-07-06实施规则：https://star.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20260424_10816474.shtml\n- 交易时段：https://one.sse.com.cn/onething/gptz/\n\n来源原件、散列及逐日差异见GitHub public_extra和public_r2目录。数据运算均在GitHub Actions执行。summary.json记录全量验收结果。\n''')
files=sorted(p for p in D.iterdir() if p.is_file() and p.name not in ['SHA256.json']);manifest={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files};(D/'SHA256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
zpath=O/'public_source_supplement_20261005.zip'
with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED) as z:
 for p in sorted(D.iterdir()):z.write(p,p.name)
with zipfile.ZipFile(zpath) as z:
 assert z.testzip() is None
 for name,digest in manifest.items():assert hashlib.sha256(z.read(name)).hexdigest()==digest
(O/'supplement_delivery_manifest.json').write_text(json.dumps({'zip':zpath.name,'bytes':zpath.stat().st_size,'sha256':hashlib.sha256(zpath.read_bytes()).hexdigest(),'members':len(manifest)+1,'verified':True},indent=2))
print(json.dumps(summary,ensure_ascii=False,indent=2))
