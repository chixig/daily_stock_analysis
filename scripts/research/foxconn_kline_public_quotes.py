"""Probe documented public quote endpoints and preserve actual responses and comparisons."""
import json
from pathlib import Path
import requests
import pandas as pd
from foxconn_kline_semantics import norm,FIELDS

BASE=Path('research/foxconn_kline_20261005');ROOT=Path('research/foxconn_kline_repair_20261005');RAW=ROOT/'raw/public_quotes';AUDIT=ROOT/'audit'

def main():
    RAW.mkdir(exist_ok=True);results=[]
    probes=[]
    for scale in ['1','5']:
        probes.append(('sina_'+scale,'https://quotes.sina.cn/cn/api/jsonp_v2.php/=/CN_MarketDataService.getKLineData',{'symbol':'sh601138','scale':scale,'ma':'no','datalen':'1970'}))
    probes.append(('eastmoney_1','https://push2his.eastmoney.com/api/qt/stock/trends2/get',{'fields1':'f1,f2,f3,f4,f5,f6,f7,f8,f9,f10,f11,f12,f13','fields2':'f51,f52,f53,f54,f55,f56,f57,f58','ut':'7eea3edcaed734bea9cbfc24409ed989','ndays':'5','iscr':'0','secid':'1.601138'}))
    probes.append(('eastmoney_5','https://push2his.eastmoney.com/api/qt/stock/kline/get',{'fields1':'f1,f2,f3,f4,f5,f6','fields2':'f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61','ut':'7eea3edcaed734bea9cbfc24409ed989','klt':'5','fqt':'0','secid':'1.601138','beg':'0','end':'20500000'}))
    for name,url,params in probes:
        item={'name':name,'endpoint':url,'params':params}
        try:
            r=requests.get(url,params=params,timeout=30);item['http_status']=r.status_code
            (RAW/(name+'.txt')).write_text(r.text)
            r.raise_for_status()
            if name.startswith('sina'):
                data=json.loads(r.text.split('=(',1)[1].rsplit(');',1)[0])
                if not data:raise ValueError('Source returned no minute records')
                d=pd.DataFrame(data).rename(columns={'day':'datetime'})
            else:
                data=r.json()['data'];rows=data['trends' if name.endswith('1') else 'klines']
                d=pd.DataFrame([a.split(',') for a in rows]);columns=['datetime','open','close','high','low','volume','amount']
                d=d.iloc[:,:7];d.columns=columns;d['volume']=pd.to_numeric(d.volume)*100
            d=norm(d);d.to_parquet(RAW/(name+'.parquet'),index=False)
            item.update(rows=len(d),first=str(d.datetime.min()),last=str(d.datetime.max()),invalid_or_missing_ohlc=int((d[FIELDS].isna().any(axis=1)|(d[FIELDS]<=0).any(axis=1)).sum()))
            ref=norm(pd.read_parquet(BASE/('canonical/601138_'+('1min' if name.endswith('1') else '5min')+'.parquet')))
            q=d.merge(ref,on='datetime',suffixes=('_quote','_canonical'))
            for c in FIELDS:q[c+'_diff']=q[c+'_quote']-q[c+'_canonical']
            bad=(q[[c+'_diff' for c in FIELDS]].abs()>.005).any(axis=1)
            q[bad].to_csv(AUDIT/(name+'_canonical_conflicts.csv.gz'),index=False)
            item['comparison']={'overlap':len(q),'conflicts':int(bad.sum()),'by_field':{c:int((q[c+'_diff'].abs()>.005).sum()) for c in FIELDS}}
        except Exception as e:item['error']=repr(e)
        results.append(item);(AUDIT/'public_quote_acquisition.json').write_text(json.dumps(results,ensure_ascii=False,indent=2));print(json.dumps(item,ensure_ascii=False),flush=True)

if __name__=='__main__':main()
