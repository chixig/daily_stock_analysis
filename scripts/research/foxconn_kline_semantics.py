"""Measure opening-bar semantics, source differences, daily reconciliation and snapshot labels."""
from pathlib import Path
import json
import pandas as pd
import numpy as np

ROOT=Path('research/foxconn_kline_20261005'); RAW=ROOT/'raw'; AUDIT=ROOT/'audit'
FIELDS=['open','high','low','close']
TIMES=(pd.date_range('2000-01-01 09:31','2000-01-01 11:30',freq='min').strftime('%H:%M').tolist()+pd.date_range('2000-01-01 13:01','2000-01-01 15:00',freq='min').strftime('%H:%M').tolist())

def norm(d):
    d=d.rename(columns={'timestamp':'datetime','turnover':'amount','vol':'volume'}).copy()
    d['datetime']=pd.to_datetime(d['datetime']);d['date']=d['datetime'].dt.strftime('%Y-%m-%d')
    for c in FIELDS+['volume','amount']:
        if c in d:d[c]=pd.to_numeric(d[c],errors='raise')
    return d.sort_values('datetime').reset_index(drop=True)

def fold_hf(d):
    auction=d[d['datetime'].dt.strftime('%H:%M')=='09:30'].set_index('date')
    x=d[d['datetime'].dt.strftime('%H:%M')!='09:30'].copy()
    first=x['datetime'].dt.strftime('%H:%M')=='09:31'
    for c in ['open','high','low','volume','amount']:
        a=x.loc[first,'date'].map(auction[c])
        if c=='open':x.loc[first,c]=a.values
        elif c=='high':x.loc[first,c]=np.maximum(x.loc[first,c].values,a.values)
        elif c=='low':x.loc[first,c]=np.minimum(x.loc[first,c].values,a.values)
        else:x.loc[first,c]=x.loc[first,c].values+a.values
    return x

def compare(a,b,name,cols=FIELDS):
    q=a.merge(b,on='datetime',suffixes=('_a','_b'))
    errors=pd.DataFrame({c:(q[c+'_a']-q[c+'_b']).abs() for c in cols})
    bad=(errors[cols]>0.005).any(axis=1)
    q.loc[bad].to_csv(AUDIT/f'{name}_conflicts.csv.gz',index=False)
    summary={'overlap':len(q),'ohlc_conflicts_gt_half_cent':int(bad.sum()),
      'conflict_times':q.loc[bad,'datetime'].dt.strftime('%H:%M').value_counts().head(12).to_dict(),
      'by_field':{c:{'bad':int((errors[c]>0.005).sum()),'max':float(errors[c].max()),'median':float(errors[c].median())} for c in cols}}
    for c in ['volume','amount']:
        if c+'_a' in q and c+'_b' in q:
            ratio=q.loc[q[c+'_b']>0,c+'_a']/q.loc[q[c+'_b']>0,c+'_b']
            summary[c+'_ratio_quantiles']=ratio.quantile([0,0.01,0.5,0.99,1]).to_dict()
            summary[c+'_exact_count']=int(np.isclose(q[c+'_a'],q[c+'_b'],atol=.1,rtol=1e-6).sum())
    return summary

def aggregate_daily(d):
    return d.groupby('date').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),amount=('amount','sum'),rows=('datetime','size'))

def run():
    AUDIT.mkdir(exist_ok=True)
    hf=norm(pd.read_parquet(RAW/'hf_601138.parquet')); folded=fold_hf(hf)
    old=norm(pd.read_csv(RAW/'b13_1m.csv')); main=norm(pd.read_csv(RAW/'main_1m.csv'))
    result={'hf_folded_b13':compare(folded,old,'hf_folded_b13'),'hf_raw_b13':compare(hf,old,'hf_raw_b13')}
    freshpath=RAW/'tdx_1m_fresh.csv.gz'
    fresh=None
    if freshpath.exists():
        fresh=norm(pd.read_csv(freshpath));fresh=fresh.drop_duplicates('datetime')
        for name,x in [('hf_folded',folded),('main',main),('b13',old)]:result[name+'_fresh']=compare(x,fresh,name+'_fresh')
    daily=pd.read_csv(RAW/'old_5m/601138_daily_raw.csv');daily['date']=daily['date'].str[:10]
    for name,x in [('hf_folded',folded),('main',main),('b13',old),('fresh',fresh)]:
        if x is None:continue
        q=aggregate_daily(x).reset_index().merge(daily,on='date',suffixes=('_min','_day'))
        cols=FIELDS+['volume','amount']
        for c in cols:q[c+'_diff']=q[c+'_min']-q[c+'_day']
        q.to_csv(AUDIT/f'{name}_daily_reconcile.csv',index=False)
        result[name+'_daily']={'days':len(q),'ohlc_bad_days':int((q[[c+'_diff' for c in FIELDS]].abs()>.005).any(axis=1).sum()),
        'by_field':{c:{'max_abs_diff':float(q[c+'_diff'].abs().max()),'median_abs_diff':float(q[c+'_diff'].abs().median()),'bad_days':int((q[c+'_diff'].abs()>.005).sum())} for c in cols}}
    # Compare 09:30 source to 09:31 pre-fold and volume totals at the opening.
    auc=hf[hf['datetime'].dt.strftime('%H:%M')=='09:30'];result['hf_0930']={'rows':len(auc),'nonzero_volume':int((auc.volume>0).sum()),'nonflat_ohlc':int((auc[FIELDS].max(axis=1)-auc[FIELDS].min(axis=1)>.005).sum())}
    snapshots=pd.concat([pd.read_csv(f) for f in sorted((RAW/'old_snapshots').glob('*.csv'))],ignore_index=True)
    snapshots=norm_snapshot(snapshots)
    snapshot_results=[]
    for target_name,target in [('hf',hf),('folded',folded),('b13',old),('main',main)]:
        for shift in [0,1]:
            x=snapshots[['datetime','price','volume']].copy();x['datetime']+=pd.Timedelta(minutes=shift)
            q=x.merge(target[['datetime','close','volume']],on='datetime',suffixes=('_snapshot','_bar'))
            delta=(q.price-q.close).abs()
            ratio=q.loc[q.volume_bar>0,'volume_snapshot']/q.loc[q.volume_bar>0,'volume_bar']
            snapshot_results.append({'target':target_name,'shift_minutes':shift,'overlap':len(q),'close_within_half_cent':int((delta<=.005).sum()),'median_price_diff':float(delta.median()),'volume_ratio_quantiles':ratio.quantile([.01,.5,.99]).to_dict()})
    result['snapshot_alignment']=snapshot_results
    (AUDIT/'semantic_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)


def norm_snapshot(x):
    x=x.copy();x['datetime']=pd.to_datetime(x['datetime']);return x.sort_values('datetime')

if __name__=='__main__':run()
