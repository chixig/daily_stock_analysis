"""Compare additional native bars with original candidates and independent daily references."""
import json
from pathlib import Path
import pandas as pd,numpy as np
BASE=Path('research/foxconn_kline_20261005');ROOT=Path('research/foxconn_kline_repair_20261005');OUT=ROOT/'public_r2';F=['open','high','low','close']
results={}
def save():
 (OUT/'evaluation.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,default=str))
def compare_bars(x,name,freq):
 x=x.copy();x['datetime']=pd.to_datetime(x.datetime);x=x.sort_values('datetime')
 raw=len(x);dup=int(x.duplicated('datetime').sum());null=int(x[F].isna().any(axis=1).sum())
 # No price imputation or deduplication before recording source structure.
 valid=x[F].notna().all(axis=1);badstruct=(x.high<x[F].max(axis=1)-.005)|(x.low>x[F].min(axis=1)+.005)
 z=x[valid].copy();z['date']=z.datetime.dt.strftime('%Y-%m-%d')
 d=z.groupby('date').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),amount=('amount','sum'),rows=('datetime','size')).reset_index()
 ref=pd.read_csv(BASE/'canonical/daily_reference.csv');q=d.merge(ref,on='date',suffixes=('_source','_daily'))
 for c in F+['volume','amount']:q[c+'_diff']=q[c+'_source']-q[c+'_daily']
 q['extrema_match']=(q[['high_diff','low_diff']].abs()<=.005).all(axis=1)
 q['ohlc_match']=(q[[c+'_diff' for c in F]].abs()<=.005).all(axis=1)
 q.to_csv(OUT/(name+'_daily.csv'),index=False)
 old=pd.read_parquet(BASE/f'canonical/601138_{freq}.parquet');old['datetime']=pd.to_datetime(old.datetime)
 m=z.merge(old,on='datetime',suffixes=('_new','_old'))
 for c in F:m[c+'_diff']=m[c+'_new']-m[c+'_old']
 conflict=(m[[c+'_diff' for c in F]].abs()>.005).any(axis=1)
 m[conflict].to_csv(OUT/(name+'_minute_conflicts.csv.gz'),index=False)
 problem=pd.read_csv(ROOT/'audit/daily_problem_dates.csv').date.astype(str)
 p=q[q.date.isin(problem)]
 r=dict(rows=raw,non_null_rows=len(z),null_ohlc_rows=null,duplicate_timestamps=dup,invalid_ohlc_structure=int(badstruct.sum()),start=str(z.datetime.min()),end=str(z.datetime.max()),days=z.date.nunique(),time_counts=z.datetime.dt.strftime('%H:%M').value_counts().sort_index().to_dict(),daily_compared=len(q),daily_ohlc_failures=int((~q.ohlc_match).sum()),daily_extrema_failures=int((~q.extrema_match).sum()),daily_field_failures={c:int((q[c+'_diff'].abs()>.005).sum()) for c in F},daily_volume_exact_matches=int((q.volume_diff==0).sum()),daily_amount_within_1_yuan=int((q.amount_diff.abs()<=1).sum()),original_332_overlap=len(p),original_332_now_extrema_match=int(p.extrema_match.sum()),original_332_still_extrema_fail=int((~p.extrema_match).sum()),overlap_bars=len(m),ohlc_conflict_bars=int(conflict.sum()),by_field={c:int((m[c+'_diff'].abs()>.005).sum()) for c in F},source_certified=False)
 z.to_parquet(OUT/(name+'_normalized.parquet'),index=False)
 return r

def main():
 # Provider-wide panels: preserve their timestamp labels, only project the target symbol.
 pieces={}
 for field in F+['volume','amount']:
  p=OUT/('suncong_'+field+'.parquet')
  if p.exists():
   d=pd.read_parquet(p);target=[c for c in d.columns if '601138' in str(c)]
   if len(target)==1:pieces[field]=d[target[0]]
 if len(pieces)==6:
  z=pd.DataFrame(pieces);results['suncong_index']={'type':str(type(z.index)),'names':z.index.names,'head':list(map(str,z.index[:3]))}
  if isinstance(z.index,pd.DatetimeIndex):
   z.index.name='datetime';z=z.reset_index();results['suncong']=compare_bars(z,'suncong','1min')
  else:results['suncong_status']='timestamp_mapping_needs_review'
 save()
 all5=[]
 for p in sorted(OUT.glob('ANTICH_20[0-9][0-9].parquet')):
  d=pd.read_parquet(p)
  if 'datetime' not in d:
   for c in ['timestamp','time','date']:
    if c in d:d=d.rename(columns={c:'datetime'});break
  if 'amount' not in d and 'turnover' in d:d=d.rename(columns={'turnover':'amount'})
  if {'datetime',*F,'volume','amount'}.issubset(d):all5.append(d)
  else:results[p.stem+'_schema']=list(d.columns)
 if all5:results['ANTICH']=compare_bars(pd.concat(all5,ignore_index=True),'ANTICH','5min')
 save()
 # Save compact per-day snapshot endpoints; detailed analysis follows schema inspection.
 for p in sorted(OUT.glob('depth_*.parquet')):
  d=pd.read_parquet(p);results[p.stem]={'rows':len(d),'columns':list(d.columns),'head':d.head(2).to_dict('records'),'tail':d.tail(3).to_dict('records')}
 save();print(json.dumps(results,ensure_ascii=False,indent=2,default=str),flush=True)
if __name__=='__main__':main()
