"""Restore candidate prices using stored factors, then compare without adopting them."""
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('research/foxconn_kline_repair_20261005');BASE=Path('research/foxconn_kline_20261005')
def main():
    ref=pd.read_csv(BASE/'canonical/daily_reference.csv').set_index('date')
    old=pd.read_parquet(BASE/'canonical/601138_1min.parquet')
    old['datetime']=pd.to_datetime(old.datetime)
    result=[]
    for ver in ['v1','v2']:
        base=ROOT/'raw/qlib'/ver
        cal=pd.to_datetime((base/'calendars/1min.txt').read_text().splitlines())
        frames=[]
        for name in ['open','high','low','close','factor','volume','paused']:
            p=base/'features/sh601138'/(name+'.1min.bin')
            a=np.fromfile(p,dtype='<f4');start=int(a[0])
            frames.append(pd.Series(a[1:],index=cal[start:start+len(a)-1],name=name))
        x=pd.concat(frames,axis=1).reset_index().rename(columns={'index':'datetime'})
        for c in ['open','high','low','close']:x[c]=(x[c]/x.factor).round(2)
        x['date']=x.datetime.dt.strftime('%Y-%m-%d')
        agg=x.groupby('date').agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),rows=('close','size'))
        agg=agg.join(ref[['open','high','low','close']],rsuffix='_daily')
        for c in ['open','high','low','close']:agg[c+'_diff']=agg[c]-agg[c+'_daily']
        mismatches=(agg[[c+'_diff' for c in ['open','high','low']]].abs()>.005).any(axis=1)
        comparisons={}
        for offset in [0,1]:
            z=x.copy();z['datetime']=z.datetime+pd.Timedelta(minutes=offset)
            pair=z.merge(old,on='datetime',suffixes=('_qlib','_previous'))
            bad=np.column_stack([(pair[c+'_qlib']-pair[c+'_previous']).abs()>.005 for c in ['open','high','low','close']]).any(axis=1)
            comparisons[str(offset)]={'overlap':len(pair),'price_conflicts':int(bad.sum())}
        x.to_parquet(ROOT/'audit'/f'qlib_{ver}_restored_candidate.parquet',index=False)
        agg.to_csv(ROOT/'audit'/f'qlib_{ver}_daily_comparison.csv')
        result.append({'version':ver,'rows':len(x),'days':len(agg),'start':str(x.datetime.min()),'end':str(x.datetime.max()),'first_times':x.datetime.head(3).astype(str).tolist(),'factor_range':[float(x.factor.min()),float(x.factor.max())],'nan_price_rows':int(x[['open','high','low','close']].isna().any(axis=1).sum()),'daily_extrema_mismatch_days':int(mismatches.sum()),'daily_close_mismatch_days':int((agg.close_diff.abs()>.005).sum()),'comparison_offsets_minutes':comparisons,'declared_quality':'candidate; price factor restored; underlying collection and synthetic-fill lineage unverified'})
    (ROOT/'audit/qlib_evaluation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
