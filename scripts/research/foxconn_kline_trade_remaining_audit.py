"""Audit remaining session discrepancies and the original disputed bars without altering prices."""
import json
from pathlib import Path
import pandas as pd

ROOT=Path('research/foxconn_kline_repair_20261005');BASE=Path('research/foxconn_kline_20261005');D=ROOT/'delivery'
def main():
    q=pd.read_csv(D/'daily_transaction_quality.csv').set_index('date')
    meta=pd.read_csv(ROOT/'audit/publisher_row_count_comparison.csv')
    ref=pd.read_csv(BASE/'canonical/daily_reference.csv').set_index('date')
    rows=[];postframes=[]
    for day in q.index:
        x=pd.read_parquet(ROOT/'raw/phields'/(day+'.parquet')).drop_duplicates().sort_values(['time_s','tran_id'])
        x=x[(x.price_x10000>0)&(x.volume>0)&(x.time_s>=33300)]
        late=x[x.time_s>54000].copy();late['date']=day
        if len(late):postframes.append(late)
        amount=(x.price_x10000*x.volume).sum()/10000
        r={'date':day,'post_close_rows':len(late),'post_close_volume':int(late.volume.sum()),'post_close_amount':float((late.price_x10000*late.volume).sum()/10000),'post_close_first_time':int(late.time_s.min()) if len(late) else None,'post_close_last_time':int(late.time_s.max()) if len(late) else None,'post_close_price_count':int(late.price_x10000.nunique()),'including_post_close_volume_diff':float(x.volume.sum()-ref.loc[day,'volume']),'including_post_close_amount_diff':float(amount-ref.loc[day,'amount']),'including_post_close_close_diff':float(x.price_x10000.iloc[-1]/10000-ref.loc[day,'close'])}
        r['all_records_daily_reconciliation_pass']=abs(r['including_post_close_volume_diff'])<.5 and abs(r['including_post_close_amount_diff'])<.02 and abs(r['including_post_close_close_diff'])<.005 and abs(x.price_x10000.max()/10000-ref.loc[day,'high'])<.005 and abs(x.price_x10000.min()/10000-ref.loc[day,'low'])<.005
        rows.append(r)
    lateq=pd.DataFrame(rows);lateq.to_csv(D/'post_close_reconciliation.csv',index=False)
    if postframes:pd.concat(postframes,ignore_index=True).to_csv(ROOT/'audit/post_close_source_records.csv.gz',index=False)
    new=pd.read_parquet(ROOT/'trade_reconstruction/601138_1min_trades.parquet')
    old=pd.read_parquet(BASE/'canonical/601138_1min.parquet');old['datetime']=pd.to_datetime(old.datetime)
    disputed=old[old.source_conflict].merge(new,on='datetime',suffixes=('_previous','_trade'))
    disputed.to_csv(D/'original_591_conflicts_transaction_comparison.csv',index=False)
    different=(pd.concat([(disputed[c+'_previous']-disputed[c+'_trade']).abs()>.005 for c in ['open','high','low','close']],axis=1)).any(axis=1)
    conflict_dates=sorted(disputed.datetime.dt.strftime('%Y-%m-%d').unique().tolist())
    s={'actual_days':len(q),'publisher_declared_days':len(meta),'dates_without_publisher_count':sorted(set(q.index)-set(meta.trade_date)),'original_disputed_minutes':len(disputed),'disputed_minutes_different_from_previous':int(different.sum()),'original_conflict_dates':conflict_dates,'conflict_dates_failing_regular_daily_reconciliation':[d for d in conflict_dates if not q.loc[d,'daily_reconciliation_pass']],'regular_daily_failed_days':int((~q.daily_reconciliation_pass).sum()),'failed_dates_reconciling_only_when_post_close_included':lateq[lateq.date.isin(q[~q.daily_reconciliation_pass].index)&lateq.all_records_daily_reconciliation_pass].date.tolist(),'all_records_still_failed_dates':lateq[~lateq.all_records_daily_reconciliation_pass].date.tolist(),'post_close_records':int(lateq.post_close_rows.sum()),'interpretation':'Post-close records remain at original times; no reassignment to 15:00. Matching daily totals does not establish the meaning or true event time of these records.'}
    (D/'remaining_evidence_audit.json').write_text(json.dumps(s,ensure_ascii=False,indent=2));print(json.dumps(s,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
