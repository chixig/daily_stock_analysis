from pathlib import Path
import pandas as pd,numpy as np,json
B=Path('research/foxconn_kline_20261005');R=Path('research/foxconn_kline_repair_20261005');O=R/'public_r2';F=['open','high','low','close'];report={}
daily=pd.read_csv(B/'canonical/daily_reference.csv').set_index('date')
x=pd.read_parquet(O/'suncong_normalized.parquet');x.datetime=pd.to_datetime(x.datetime)
invalid=(x.high<x[F].max(axis=1)-.005)|(x.low>x[F].min(axis=1)+.005)
report['suncong_invalid']={'dates':x[invalid].datetime.dt.strftime('%Y-%m-%d').value_counts().to_dict(),'examples':x[invalid].head(4).to_dict('records'),'volume_non_100_multiple':int((x.volume%100!=0).sum()),'zero_volume_rows':int((x.volume==0).sum())}
x[invalid].to_csv(O/'suncong_invalid_rows.csv',index=False)
q=pd.read_csv(O/'suncong_daily.csv');report['suncong_daily_quantity']={'volume_diff_quantiles':q.volume_diff.quantile([0,.25,.5,.75,1]).to_dict(),'amount_diff_quantiles':q.amount_diff.quantile([0,.25,.5,.75,1]).to_dict(),'volume_diff_below_1000':int((q.volume_diff.abs()<=1000).sum()),'dates_missing_within_range':sorted(set(daily.loc['2018-06-08':'2026-03-26'].index)-set(q.date))}
# Original 332-day comparison between two alternative archives is still not minute-level proof.
wind=R/'audit/wind17_daily.csv'
report['snapshot_diagnosis']=[]
for p in sorted(O.glob('depth_*.parquet')):
 day=p.name.split('_')[1];s=pd.read_parquet(p).sort_values('time_ms');tr=pd.read_parquet(R/'raw/phields'/f'{day}.parquet').drop_duplicates().sort_values(['time_s','tran_id'])
 t=tr.time_s.to_numpy();vol=np.r_[0,tr.volume.cumsum().to_numpy()];amount=np.r_[0,(tr.volume*tr.price_x10000).cumsum().to_numpy()]/10000
 for lag in [0,1,3,10]:
  ix=np.searchsorted(t,s.time_ms.to_numpy()/1000+lag,side='right');s[f'raw_cumulative_volume_plus_{lag}s']=vol[ix];s[f'volume_gap_plus_{lag}s']=s.cumulative_volume-vol[ix]
 s['raw_cumulative_amount_plus_0s']=amount[np.searchsorted(t,s.time_ms.to_numpy()/1000,side='right')];s['amount_gap_plus_0s']=s.cumulative_value-s.raw_cumulative_amount_plus_0s
 s.to_csv(O/(day+'_snapshot_trade_cumulative.csv.gz'),index=False)
 last=s.iloc[-1];ref=daily.loc[day]
 changes=s[(s.volume_gap_plus_10s>0)&(s.time_ms>=34200000)&(s.time_ms<=53700000)]
 r={'date':day,'snapshot_rows':len(s),'last_snapshot_time_ms':int(last.time_ms),'last_snapshot_daily_differences':{'volume':float(last.cumulative_volume-ref.volume),'amount':float(last.cumulative_value-ref.amount),'open':float(last.open_price_x10000/10000-ref.open),'high':float(last.high_price_x10000/10000-ref.high),'low':float(last.low_price_x10000/10000-ref.low),'close':float(last.last_price_x10000/10000-ref.close)},'all_raw_trade_volume_diff':int(tr.volume.sum()-ref.volume),'last_snapshot_vs_all_raw_volume_gap':int(last.cumulative_volume-tr.volume.sum()),'last_snapshot_vs_all_raw_count_gap':int(last.trade_count-len(tr)),'positive_gap_after_10_second_allowance_rows':len(changes),'first_positive_gap_examples':changes[['time_ms','cumulative_volume','volume_gap_plus_0s','volume_gap_plus_10s']].head(10).to_dict('records'),'final_raw_trades':tr.tail(2).to_dict('records')}
 report['snapshot_diagnosis'].append(r)
(O/'diagnosis.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str));print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
