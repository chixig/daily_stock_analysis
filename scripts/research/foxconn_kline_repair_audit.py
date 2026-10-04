"""Read-only forensic audit; raw evidence is never rewritten or filled from snapshots."""
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import pandas as pd
import numpy as np
from pytdxdata import TdxData
from pytdxdata.models import Market, KlinePeriod
from foxconn_kline_semantics import norm, aggregate_daily, FIELDS

BASE=Path('research/foxconn_kline_20261005')
OUT=Path('research/foxconn_kline_repair_20261005')
RAW=OUT/'raw'; AUDIT=OUT/'audit'

def write_json(name,obj):
    (AUDIT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))

def compare(a,b,name):
    q=a.merge(b,on='datetime',suffixes=('_a','_b'))
    for c in FIELDS:q[c+'_diff']=q[c+'_a']-q[c+'_b']
    bad=(q[[c+'_diff' for c in FIELDS]].abs()>.005).any(axis=1)
    q[bad].to_csv(AUDIT/(name+'.csv.gz'),index=False)
    return {'overlap':len(q),'conflicts':int(bad.sum()),'by_field':{c:int((q[c+'_diff'].abs()>.005).sum()) for c in FIELDS}}

def audit():
    q=pd.read_csv(BASE/'canonical/daily_quality.csv')
    cols=['open','high','low']
    bad=(q[[c+'_diff' for c in cols]].abs()>.005).any(axis=1)
    q['year']=q.date.str[:4]
    q['mismatch_fields']=q.apply(lambda r:','.join(c for c in cols if abs(r[c+'_diff'])>.005),axis=1)
    q[bad].to_csv(AUDIT/'daily_problem_dates.csv',index=False)
    result={'daily_mismatches':int(bad.sum()),'daily_by_field':{},'by_year':q[bad].groupby('year').size().to_dict(),'by_source':q[bad].groupby('source').size().to_dict()}
    for c in cols:
        z=q[q[c+'_diff'].abs()>.005]
        result['daily_by_field'][c]={'days':len(z),'minute_above_daily':int((z[c+'_diff']>.005).sum()),'minute_below_daily':int((z[c+'_diff']<-.005).sum()),'absolute_quantiles':z[c+'_diff'].abs().quantile([0,.5,.9,1]).to_dict(),'examples':z.sort_values(c+'_diff',key=abs,ascending=False)[['date',c+'_minute',c+'_daily',c+'_diff']].head(8).to_dict('records')}
    x=norm(pd.read_parquet(BASE/'canonical/601138_1min.parquet'))
    s=norm(pd.read_parquet(BASE/'canonical/601138_intraday.parquet'))
    z=x.merge(s[['datetime','price']],on='datetime')
    outside=(z.price<z.low-.005)|(z.price>z.high+.005)
    z[outside].to_csv(AUDIT/'snapshot_outside_bar_range.csv.gz',index=False)
    result['snapshot_outside_ohlc_range']={'points':int(outside.sum()),'days':int(z[outside].date.nunique()),'note':'Sampling-time alignment must be validated before treating this as proof of a wrong bar.'}
    cf=pd.read_csv(BASE/'audit/canonical_source_price_conflicts.csv.gz')
    cf['datetime']=pd.to_datetime(cf.datetime)
    cf['date']=cf.datetime.dt.strftime('%Y-%m-%d');cf['time']=cf.datetime.dt.strftime('%H:%M')
    cf.to_csv(AUDIT/'conflict_pairs.csv.gz',index=False)
    result['source_conflicts']={'pair_rows':len(cf),'unique_bars':int(cf.datetime.nunique()),'days':int(cf.date.nunique()),'date_counts':cf.groupby('date').datetime.nunique().to_dict(),'time_counts_top':cf.groupby('time').datetime.nunique().sort_values(ascending=False).head(15).to_dict(),'pairs':cf.groupby(['source_selected','source_other']).size().to_dict().__str__()}
    old5=norm(pd.read_csv(BASE/'raw/old_5m/601138_5min_all.csv'))
    d5=aggregate_daily(old5).reset_index()
    dd=pd.read_csv(BASE/'canonical/daily_reference.csv')
    m=d5.merge(dd,on='date',suffixes=('_minute','_daily'))
    for c in FIELDS:m[c+'_diff']=m[c+'_minute']-m[c+'_daily']
    m.to_csv(AUDIT/'baostock5_daily.csv',index=False)
    result['baostock5_daily']={'days':len(m),'by_field':{c:int((m[c+'_diff'].abs()>.005).sum()) for c in FIELDS}}
    write_json('diagnosis.json',result)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

async def acquire():
    manifest=[]
    async with TdxData() as td:
        for period,name,count in [(KlinePeriod.MIN_5,'tdx_direct_5m',110000),(KlinePeriod.MIN_1,'tdx_repeat_1m',60000)]:
            info={'source':name,'period':str(period),'requested_count':count}
            try:
                bars=await asyncio.wait_for(td.get_kline(Market.SH,'601138',period,count=count),timeout=240)
                rows=[]
                for b in bars:
                    d=asdict(b);d['datetime']=str(b.datetime);rows.append(d)
                d=pd.DataFrame(rows)
                p=RAW/(name+'.csv.gz');d.to_csv(p,index=False)
                info.update(rows=len(d),first=str(d.datetime.min()),last=str(d.datetime.max()),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
                x=norm(d)
                reference=norm(pd.read_parquet(BASE/('canonical/601138_'+('5min' if period==KlinePeriod.MIN_5 else '1min')+'.parquet')))
                info['canonical_comparison']=compare(x,reference,name+'_canonical_conflicts')
                if period==KlinePeriod.MIN_5:
                    old=norm(pd.read_csv(BASE/'raw/old_5m/601138_5min_all.csv'))
                    info['baostock_comparison']=compare(x,old,name+'_baostock_conflicts')
                days=aggregate_daily(x).reset_index().merge(pd.read_csv(BASE/'canonical/daily_reference.csv'),on='date',suffixes=('_minute','_daily'))
                for c in FIELDS:days[c+'_diff']=days[c+'_minute']-days[c+'_daily']
                days.to_csv(AUDIT/(name+'_daily.csv'),index=False)
                info['daily']={'days':len(days),'by_field':{c:int((days[c+'_diff'].abs()>.005).sum()) for c in FIELDS}}
            except Exception as e:info['error']=repr(e)
            manifest.append(info);write_json('acquisition.json',manifest)
            print(json.dumps(info,ensure_ascii=False),flush=True)

if __name__=='__main__':
    for p in [RAW,AUDIT]:p.mkdir(parents=True,exist_ok=True)
    audit();asyncio.run(acquire())
