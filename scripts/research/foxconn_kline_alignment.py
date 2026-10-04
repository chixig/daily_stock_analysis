"""Test second-level timestamp offsets and quantify competing public-source limitations."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from foxconn_kline_semantics import norm,aggregate_daily,FIELDS

BASE=Path('research/foxconn_kline_20261005');ROOT=Path('research/foxconn_kline_repair_20261005');AUDIT=ROOT/'audit';RAW=ROOT/'raw'
def main():
    can=norm(pd.read_parquet(BASE/'canonical/601138_1min.parquet'))
    archive=norm(pd.read_parquet(RAW/'wind17_normalized.parquet'))
    dd=pd.read_csv(BASE/'canonical/daily_reference.csv')
    oldq=pd.read_csv(BASE/'canonical/daily_quality.csv')
    aq=pd.read_csv(AUDIT/'wind17_daily_comparison.csv')
    aa=(aq[[c+'_diff' for c in ['open','high','low']]].abs()>.005).any(axis=1)
    oq=(oldq[[c+'_diff' for c in ['open','high','low']]].abs()>.005).any(axis=1)
    known=set(oldq[oq].date);new=set(aq[aa].date)
    stats={'archive_old_problem_days_resolved_daily_only':len(known-set(new)),'archive_new_problem_days':len(set(new)-known),'archive_remaining_old_problem_days':len(known&set(new)),'archive_problem_years':aq[aa].groupby(aq[aa].date.str[:4]).size().to_dict(),'archive_daily_mismatches':len(new),'archive_daily_volume_large_days':int((aq.volume_diff.abs()>1000).sum()),'archive_daily_amount_large_days':int((aq.amount_diff.abs()>1000).sum())}
    # New direct 5m pages must also be checked for missing and duplicate grid points.
    td=norm(pd.read_csv(RAW/'tdx_direct_5m.csv.gz'))
    counts=td.groupby('date').size()
    stats['tdx5_grid']={'duplicates':int(td.datetime.duplicated().sum()),'not_48_rows':counts[counts!=48].to_dict()}
    (AUDIT/'source_limitations.json').write_text(json.dumps(stats,ensure_ascii=False,indent=2))
    allrows=[]
    for p in sorted((RAW/'phields').glob('*.parquet')):
        day=p.stem;z=pd.read_parquet(p).sort_values(['time_s','tran_id'])
        z=z[(z.time_s>=33900)&(z.time_s<=54000)&(z.price_x10000>0)&(z.volume>0)].copy()
        z['price']=z.price_x10000/10000;z['amount']=z.price*z.volume
        ref=can[can.date==day][['datetime',*FIELDS,'volume','amount']].copy()
        for shift in range(-120,121):
            seconds=z.time_s.to_numpy()+shift
            bins=(seconds//60+1)*60
            bins=np.where(z.time_s.to_numpy()<34200,34260,bins)
            bins=np.where(z.time_s.to_numpy()==54000,54000,bins)
            w=z.copy();w['datetime']=pd.to_datetime(day)+pd.to_timedelta(bins,unit='s')
            b=w.groupby('datetime').agg(open=('price','first'),high=('price','max'),low=('price','min'),close=('price','last'),volume=('volume','sum'),amount=('amount','sum')).reset_index()
            q=b.merge(ref,on='datetime',suffixes=('_trade','_bar'))
            err=pd.DataFrame({c:(q[c+'_trade']-q[c+'_bar']).abs() for c in FIELDS})
            allrows.append({'date':day,'shift_seconds':shift,'overlap':len(q),'ohlc_conflicts':int((err>.005).any(axis=1).sum()),'highlow_conflicts':int((err[['high','low']]>.005).any(axis=1).sum()),'median_close_error':float(err.close.median()),'volume_correlation':float(q.volume_trade.corr(q.volume_bar)),'median_volume_absolute_error':float((q.volume_trade-q.volume_bar).abs().median())})
    x=pd.DataFrame(allrows);x.to_csv(AUDIT/'l2_second_offset_sweep.csv',index=False)
    best=x.sort_values(['date','ohlc_conflicts','median_close_error']).groupby('date').head(5).to_dict('records')
    output={'limitations':stats,'best_offsets':best,'zero_offset':x[x.shift_seconds==0].to_dict('records')}
    (AUDIT/'alignment_summary.json').write_text(json.dumps(output,ensure_ascii=False,indent=2))
    print(json.dumps(output,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
