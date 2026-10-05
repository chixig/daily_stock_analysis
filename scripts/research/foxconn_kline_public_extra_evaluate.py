"""Evaluate raw three-day native minute examples without filling missing bars."""
from pathlib import Path
import pandas as pd,json,numpy as np
B=Path('research/foxconn_kline_20261005');O=Path('research/foxconn_kline_repair_20261005/public_extra');F=['open','high','low','close']
old=pd.read_parquet(B/'canonical/601138_1min.parquet');old.datetime=pd.to_datetime(old.datetime)
daily=pd.read_csv(B/'canonical/daily_reference.csv').set_index('date');report=[]
for p in sorted(O.glob('*AllSymbols_1min_601138.parquet')):
 d=pd.read_parquet(p).sort_values('datetime');d.datetime=pd.to_datetime(d.datetime);day=d.datetime.iloc[0].strftime('%Y-%m-%d')
 expected=set(pd.date_range(day+' 09:31',day+' 11:30',freq='min').strftime('%H:%M'))|set(pd.date_range(day+' 13:01',day+' 15:00',freq='min').strftime('%H:%M'))
 times=set(d.datetime.dt.strftime('%H:%M'));r=dict(date=day,rows=len(d),missing_end_labeled_times=sorted(expected-times),extra_times=sorted(times-expected),duplicate_timestamps=int(d.datetime.duplicated().sum()),null_ohlc=int(d[F].isna().any(axis=1).sum()))
 agg={'open':d.open.iloc[0],'high':d.high.max(),'low':d.low.min(),'close':d.close.iloc[-1],'volume':d.volume.sum(),'amount':d.turnover.sum()}
 r['daily_differences']={k:float(v-daily.loc[day,k]) for k,v in agg.items()};r['acc_volume_minus_sum']=float(d.acc_volume.iloc[-1]-d.volume.sum());r['acc_turnover_minus_sum']=float(d.acc_turnover.iloc[-1]-d.turnover.sum())
 r['alignment_trials']=[]
 for shift in [-1,0,1]:
  z=d.copy();z['source_datetime']=z.datetime;z.datetime+=pd.Timedelta(minutes=shift)
  m=z.merge(old,on='datetime',suffixes=('_new','_old'))
  bad=pd.Series(False,index=m.index)
  for c in F:m[c+'_diff']=m[c+'_new']-m[c+'_old'];bad|=m[c+'_diff'].abs()>.005
  r['alignment_trials'].append(dict(shift_minutes=shift,overlap=len(m),ohlc_conflicts=int(bad.sum()),by_field={c:int((m[c+'_diff'].abs()>.005).sum()) for c in F},volume_exact_matches=int((m.volume_new==m.volume_old).sum())))
  if shift==0:m.to_csv(O/(day+'_previous_comparison.csv.gz'),index=False)
 r['source_certified']=False;report.append(r)
(O/'evaluation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
