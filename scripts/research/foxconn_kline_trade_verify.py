"""Independent numpy verification against every acquired transaction and CSV roundtrip."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT=Path('research/foxconn_kline_repair_20261005');RAW=ROOT/'raw/phields';CLEAN=ROOT/'trade_reconstruction';DELIVERY=ROOT/'delivery'
def main():
    one=pd.read_parquet(CLEAN/'601138_1min_trades.parquet');five=pd.read_parquet(CLEAN/'601138_5min_trades.parquet')
    assert len(one)==240*one.datetime.dt.date.nunique()
    assert len(five)==48*five.datetime.dt.date.nunique()
    assert not one.datetime.duplicated().any() and not five.datetime.duplicated().any()
    auction=pd.read_csv(DELIVERY/'opening_auction.csv').set_index('date')
    verified=0;groups_checked=0;auction_days=0
    for p in sorted(RAW.glob('*.parquet')):
        t=pd.read_parquet(p).drop_duplicates().sort_values(['time_s','tran_id']);s=t.time_s.to_numpy();v=t.volume.to_numpy(dtype='int64');price=t.price_x10000.to_numpy(dtype='int64')
        auction_keep=(v>0)&(price>0)&(s>=33300)&(s<34200)
        if auction_keep.any():
            ap=price[auction_keep];av=v[auction_keep];saved_a=auction.loc[p.stem]
            expected_a={'open':ap[0]/10000,'high':ap.max()/10000,'low':ap.min()/10000,'close':ap[-1]/10000,'volume':av.sum(),'amount':(ap*av).sum()/10000,'trade_count':len(ap)}
            for c,value in expected_a.items():assert np.isclose(saved_a[c],value,rtol=0,atol=1e-6),f'{p.stem} auction {c}'
            auction_days+=1
        keep=(v>0)&(price>0)&(((s>=34200)&(s<=41400))|((s>=46800)&(s<=54000)))
        s=s[keep];v=v[keep];price=price[keep]
        k=(s//60+1)*60;k[s==41400]=41400;k[s==54000]=54000
        for size,target in [(60,one),(300,five)]:
            labels=((k+size-1)//size)*size
            keys,begin,count=np.unique(labels,return_index=True,return_counts=True)
            end=begin+count-1
            arrays={'open':price[begin]/10000,'high':np.maximum.reduceat(price,begin)/10000,'low':np.minimum.reduceat(price,begin)/10000,'close':price[end]/10000,'volume':np.add.reduceat(v,begin),'amount':np.add.reduceat(price*v,begin)/10000,'trade_count':count}
            saved=target[target.datetime.dt.strftime('%Y-%m-%d')==p.stem].set_index('datetime')
            dt=pd.to_datetime(p.stem)+pd.to_timedelta(keys,unit='s');z=saved.loc[dt]
            for c,a in arrays.items():assert np.allclose(z[c].to_numpy(),a,rtol=0,atol=1e-6),f'{p.stem} {size} {c}'
            empty=saved.drop(index=dt)
            assert empty[['open','high','low','close']].isna().all().all()
            assert (empty[['volume','amount','trade_count']]==0).all().all()
            groups_checked+=len(keys)
        verified+=len(t)
    for name,x in [('601138_1min_trades',one),('601138_5min_trades',five)]:
        y=pd.read_csv(DELIVERY/(name+'.csv'));y['datetime']=pd.to_datetime(y.datetime)
        pd.testing.assert_frame_equal(x.reset_index(drop=True),y.reset_index(drop=True),check_dtype=False,rtol=0,atol=1e-6)
    result={'status':'PASS','unique_source_records_examined':verified,'auction_days_verified':auction_days,'nonempty_interval_groups_verified':groups_checked,'one_minute_rows':len(one),'five_minute_rows':len(five),'checks':['all unique recorded regular trades contribute exactly once','opening auction OHLC, count, volume and amount independently match','numpy first/max/min/last match saved bars','integer transaction volume and amount match','empty intervals contain null OHLC and zero trade count','1m and 5m complete timestamp grids','CSV and Parquet roundtrip'],'upstream_independent_completeness_certified':False}
    (DELIVERY/'independent_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
