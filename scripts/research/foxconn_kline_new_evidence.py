"""Evaluate newly acquired bars and actual transactions without mutating the delivery."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from foxconn_kline_semantics import norm,fold_hf,aggregate_daily,FIELDS,TIMES
from foxconn_kline_repair_audit import compare

BASE=Path('research/foxconn_kline_20261005');OUT=Path('research/foxconn_kline_repair_20261005');RAW=OUT/'raw';AUDIT=OUT/'audit'

def dump(name,d):
    (AUDIT/name).write_text(json.dumps(d,ensure_ascii=False,indent=2,default=str))

def archive_bars():
    frames=[]
    for p in sorted((RAW/'wind17').glob('*.csv')):
        x=pd.read_csv(p,encoding='gb18030')
        x.columns=['symbol','datetime','open','close','high','low','volume','amount']
        x['volume']=x.volume*100
        frames.append(norm(x))
    x=pd.concat(frames,ignore_index=True).sort_values('datetime')
    raw=x.copy();x=fold_hf(x)
    x.to_parquet(RAW/'wind17_normalized.parquet',index=False)
    can=norm(pd.read_parquet(BASE/'canonical/601138_1min.parquet'))
    dd=pd.read_csv(BASE/'canonical/daily_reference.csv')
    daily=aggregate_daily(x).reset_index().merge(dd,on='date',suffixes=('_minute','_daily'))
    for c in FIELDS+['volume','amount']:daily[c+'_diff']=daily[c+'_minute']-daily[c+'_daily']
    daily.to_csv(AUDIT/'wind17_daily_comparison.csv',index=False)
    pairs=x.merge(can,on='datetime',suffixes=('_archive','_old'))
    for c in FIELDS:pairs[c+'_diff']=pairs[c+'_archive']-pairs[c+'_old']
    bad=(pairs[[c+'_diff' for c in FIELDS]].abs()>.005).any(axis=1)
    pairs[bad].to_csv(AUDIT/'wind17_old_conflicts.csv.gz',index=False)
    outside=can.merge(x[['datetime','high','low']],on='datetime',suffixes=('_old','_archive'))
    s=norm(pd.read_parquet(BASE/'canonical/601138_intraday.parquet'))
    zs=x.merge(s[['datetime','price']],on='datetime')
    sr=(zs.price<zs.low-.005)|(zs.price>zs.high+.005)
    result={'raw_rows':len(raw),'folded_rows':len(x),'dates':int(x.date.nunique()),'first':str(x.datetime.min()),'last':str(x.datetime.max()),'duplicate_timestamps':int(x.datetime.duplicated().sum()),'daily_by_field':{c:int((daily[c+'_diff'].abs()>.005).sum()) for c in FIELDS},'daily_volume_abs_quantiles':daily.volume_diff.abs().quantile([0,.5,.9,1]).to_dict(),'comparison':{'overlap':len(pairs),'conflicts':int(bad.sum()),'fields':{c:int((pairs[c+'_diff'].abs()>.005).sum()) for c in FIELDS},'years':pairs[bad].groupby(pairs[bad].datetime.dt.year).size().to_dict()},'snapshot_outside_ranges':int(sr.sum()),'outside_days':int(zs[sr].date.nunique()),'valid_ohlc':bool(((x.high>=x[FIELDS].max(axis=1))&(x.low<=x[FIELDS].min(axis=1))).all())}
    dump('wind17_evaluation.json',result);print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

def make_trade_bars(x,day,edge):
    # Retain auction and regular-session transactions; audit post-close records separately.
    z=x[(x.time_s>=33900)&(x.time_s<=54000)&(x.price_x10000>0)&(x.volume>0)].copy()
    sec=z.time_s.to_numpy()
    bins=(sec//60+1)*60 if edge=='left' else ((sec+59)//60)*60
    bins=np.where(sec<34200,34260,bins)
    bins=np.where(sec==54000,54000,bins)
    z['datetime']=pd.to_datetime(day)+pd.to_timedelta(bins,unit='s')
    z['price']=z.price_x10000/10000;z['amount']=z.price*z.volume
    bars=z.groupby('datetime',sort=True).agg(open=('price','first'),high=('price','max'),low=('price','min'),close=('price','last'),volume=('volume','sum'),amount=('amount','sum'),trades=('tran_id','size')).reset_index()
    return norm(bars),z

def trade_bars():
    refs={'canonical':norm(pd.read_parquet(BASE/'canonical/601138_1min.parquet')),'b13':norm(pd.read_csv(BASE/'raw/b13_1m.csv')),'main':norm(pd.read_csv(BASE/'raw/main_1m.csv')),'hf':fold_hf(norm(pd.read_parquet(BASE/'raw/hf_601138.parquet')))}
    dd=pd.read_csv(BASE/'canonical/daily_reference.csv').set_index('date')
    results=[]
    for p in sorted((RAW/'phields').glob('*.parquet')):
        day=p.stem;x=pd.read_parquet(p).sort_values(['time_s','tran_id'])
        item={'date':day,'rows':len(x),'duplicate_time_id':int(x.duplicated(['time_s','tran_id']).sum()),'negative_or_zero_price':int((x.price_x10000<=0).sum()),'post_close_rows':int((x.time_s>54000).sum()),'variants':{}}
        for edge in ['left','right']:
            bars,trades=make_trade_bars(x,day,edge)
            bars.to_parquet(AUDIT/(day+'_trades_'+edge+'.parquet'),index=False)
            agg=aggregate_daily(bars).iloc[0]
            detail={'bars':len(bars),'labels':bars.datetime.dt.strftime('%H:%M').tolist(),'daily_differences':{c:float(agg[c]-dd.loc[day,c]) for c in FIELDS+['volume','amount']},'comparisons':{}}
            for name,ref in refs.items():detail['comparisons'][name]=compare(bars,ref,name+'_'+day+'_trades_'+edge)
            item['variants'][edge]=detail
        results.append(item)
    dump('l2_evaluation.json',results)
    for item in results:
        for v in item['variants'].values():v.pop('labels',None)
    print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':archive_bars();trade_bars()
