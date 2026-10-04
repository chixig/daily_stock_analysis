"""Reconstruct interval OHLC from all acquired transaction records; preserve no-trade nulls."""
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zipfile
import numpy as np
import pandas as pd

BASE=Path('research/foxconn_kline_20261005');ROOT=Path('research/foxconn_kline_repair_20261005');RAW=ROOT/'raw/phields';CLEAN=ROOT/'trade_reconstruction';DELIVERY=ROOT/'delivery';AUDIT=ROOT/'audit'
FIELDS=['open','high','low','close']
TIMES=list(pd.date_range('2000-01-01 09:31','2000-01-01 11:30',freq='min').strftime('%H:%M'))+list(pd.date_range('2000-01-01 13:01','2000-01-01 15:00',freq='min').strftime('%H:%M'))
def chart(x,mode,name):
    data={'days':{},'rows':len(x),'quality':{}}
    for day,g in x.groupby(x.datetime.dt.strftime('%Y-%m-%d')):
        rows=g.copy();rows['time']=rows.datetime.dt.strftime('%H:%M')
        data['days'][day]=[[None if pd.isna(v) else v for v in a] for a in rows[['time',*FIELDS,'volume','amount']].values.tolist()]
    template=Path('scripts/research/foxconn_trade_chart_template.html').read_text()
    packed=base64.b64encode(gzip.compress(json.dumps(data,ensure_ascii=False,separators=(',',':'),allow_nan=False).encode(),mtime=0)).decode()
    title=('1 分钟' if mode=='1min' else '5 分钟')+' · 逐笔成交重建候选'
    html=template.replace('__TITLE__',title).replace('__MODE__',mode).replace('__DESCRIPTION__','按公开逐笔源的记录时间和成交编号重建；开盘竞价单独保存，无成交分钟OHLC留空。上游来源尚未获独立完整性认证。').replace('__DATA__',packed)
    (DELIVERY/name).write_text(html)

def aggregate(x,label):
    return x.groupby(label,sort=True).agg(open=('price','first'),high=('price','max'),low=('price','min'),close=('price','last'),volume=('volume','sum'),amount_x10000=('amount_x10000','sum'),trade_count=('tran_id','size')).reset_index()

def main():
    for p in [CLEAN,DELIVERY,AUDIT]:p.mkdir(parents=True,exist_ok=True)
    daily=pd.read_csv(BASE/'canonical/daily_reference.csv').set_index('date')
    frames=[];auctions=[];quality=[]
    for p in sorted(RAW.glob('*.parquet')):
        day=p.stem;rawtr=pd.read_parquet(p);alltr=rawtr.drop_duplicates().sort_values(['time_s','tran_id']).reset_index(drop=True)
        positive=(alltr.price_x10000>0)&(alltr.volume>0)
        session=(alltr.time_s>=33300)&(alltr.time_s<=54000)
        tr=alltr[positive&session].copy()
        tr['price']=tr.price_x10000/10000
        tr['amount_x10000']=tr.price_x10000.astype('int64')*tr.volume.astype('int64')
        opening=tr[tr.time_s<34200].copy()
        regular=tr[((tr.time_s>=34200)&(tr.time_s<=41400))|((tr.time_s>=46800)&(tr.time_s<=54000))].copy()
        seconds=regular.time_s.to_numpy();end=(seconds//60+1)*60
        end=np.where(seconds==41400,41400,end);end=np.where(seconds==54000,54000,end)
        regular['datetime']=pd.to_datetime(day)+pd.to_timedelta(end,unit='s')
        bars=aggregate(regular,'datetime')
        grid=pd.DataFrame({'datetime':pd.to_datetime([day+' '+t for t in TIMES])})
        bars=grid.merge(bars,on='datetime',how='left')
        for c in ['volume','amount_x10000','trade_count']:bars[c]=bars[c].fillna(0).astype('int64')
        bars['amount']=bars.amount_x10000/10000;bars['no_recorded_trade']=bars.trade_count.eq(0)
        bars['source']='phields_l2_2f4c13e';bars['symbol']='601138.SH'
        frames.append(bars.drop(columns='amount_x10000'))
        if len(opening):
            auctions.append({'symbol':'601138.SH','date':day,'open':opening.price.iloc[0],'high':opening.price.max(),'low':opening.price.min(),'close':opening.price.iloc[-1],'volume':int(opening.volume.sum()),'amount':int(opening.amount_x10000.sum())/10000,'trade_count':len(opening),'first_time_s':int(opening.time_s.min()),'last_time_s':int(opening.time_s.max()),'source':'phields_l2_2f4c13e'})
        r={'date':day,'raw_trades':len(rawtr),'unique_trades':len(alltr),'exact_duplicate_rows_removed':len(rawtr)-len(alltr),'session_trades':len(tr),'regular_trades':len(regular),'auction_trades':len(opening),'post_close_trades':int((alltr.time_s>54000).sum()),'invalid_trades':int((~positive).sum()),'duplicate_time_id':int(alltr.duplicated(['time_s','tran_id']).sum()),'unassigned_session_trades':len(tr)-len(regular)-len(opening),'no_trade_minutes':int(bars.no_recorded_trade.sum()),'raw_sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
        obs={'open':tr.price.iloc[0],'high':tr.price.max(),'low':tr.price.min(),'close':tr.price.iloc[-1],'volume':int(tr.volume.sum()),'amount':int(tr.amount_x10000.sum())/10000}
        for c,v in obs.items():r[c+'_diff']=float(v-daily.loc[day,c])
        r['daily_reconciliation_pass']=r['invalid_trades']==0 and r['duplicate_time_id']==0 and r['unassigned_session_trades']==0 and all(abs(r[c+'_diff'])<=.005 for c in FIELDS) and r['volume_diff']==0 and abs(r['amount_diff'])<=.02
        quality.append(r)
    one=pd.concat(frames,ignore_index=True);q=pd.DataFrame(quality);auc=pd.DataFrame(auctions)
    one['daily_reconciliation_pass']=one.datetime.dt.strftime('%Y-%m-%d').map(q.set_index('date').daily_reconciliation_pass)
    z=one.copy();z['datetime']=z.datetime.dt.ceil('5min')
    five=z.groupby('datetime',sort=True).agg(open=('open','first'),high=('high','max'),low=('low','min'),close=('close','last'),volume=('volume','sum'),amount=('amount','sum'),trade_count=('trade_count','sum'),no_trade_minutes=('no_recorded_trade','sum'),daily_reconciliation_pass=('daily_reconciliation_pass','all')).reset_index()
    five['source']='phields_l2_2f4c13e';five['symbol']='601138.SH'
    for name,d in [('601138_1min_trades',one),('601138_5min_trades',five)]:
        d.to_parquet(CLEAN/(name+'.parquet'),index=False,compression='zstd');d.to_csv(DELIVERY/(name+'.csv'),index=False,float_format='%.6f')
    auc.to_csv(DELIVERY/'opening_auction.csv',index=False);q.to_csv(DELIVERY/'daily_transaction_quality.csv',index=False)
    old=pd.read_parquet(BASE/'canonical/601138_1min.parquet');old['datetime']=pd.to_datetime(old.datetime)
    pairs=one.merge(old,on='datetime',suffixes=('_trade','_previous'))
    for c in FIELDS:pairs[c+'_diff']=pairs[c+'_trade']-pairs[c+'_previous']
    bad=(pairs[[c+'_diff' for c in FIELDS]].abs()>.005).any(axis=1)
    pairs[bad].to_csv(AUDIT/'transaction_previous_minute_conflicts.csv.gz',index=False)
    nonopening=pairs[pairs.datetime.dt.strftime('%H:%M')!='09:31'].copy()
    widening=(nonopening.high_trade>nonopening.high_previous+.005)|(nonopening.low_trade<nonopening.low_previous-.005)
    examples=nonopening[widening][['datetime','high_trade','high_previous','low_trade','low_previous','close_trade','close_previous']].head(8).to_dict('records')
    expected=daily.loc['2026-04-01':'2026-09-30'].index.astype(str).tolist()
    missing=sorted(set(expected)-set(q.date))
    publisher=json.loads((AUDIT/'publisher_row_count_summary.json').read_text())
    summary={'missing_dates_against_daily_calendar':missing,'publisher_unchecked_dates':sorted(set(q.date)-set(pd.read_csv(AUDIT/'publisher_row_count_comparison.csv').trade_date)),'publisher_row_count_check':publisher,'status':'TRANSACTION_RECONSTRUCTION_CANDIDATE_WITH_UPSTREAM_LIMITATIONS','days':len(q),'start':str(one.datetime.min()),'end':str(one.datetime.max()),'raw_trades':int(q.raw_trades.sum()),'unique_trades':int(q.unique_trades.sum()),'exact_duplicate_rows_removed':int(q.exact_duplicate_rows_removed.sum()),'session_trades':int(q.session_trades.sum()),'one_minute_rows':len(one),'five_minute_rows':len(five),'no_recorded_trade_minutes':int(one.no_recorded_trade.sum()),'daily_reconciliation_pass_days':int(q.daily_reconciliation_pass.sum()),'daily_reconciliation_failed_dates':q[~q.daily_reconciliation_pass].date.tolist(),'unassigned_session_trades':int(q.unassigned_session_trades.sum()),'duplicate_time_id':int(q.duplicate_time_id.sum()),'previous_overlap_minutes':len(pairs),'previous_price_conflicts':int(bad.sum()),'range_widening_minutes_excluding_open':int(widening.sum()),'range_examples':examples,'source_repo':'phields/a-share-l2-trades','source_revision':'2f4c13ee70cabf3f8b831acf7e1686481a762eaa','provider_provenance_disclosed':False,'time_precision':'seconds; within a second sorted by source tran_id','opening_auction':'separate from regular minute bars','empty_minute_ohlc':'null, not interpolated or forward-filled'}
    (DELIVERY/'coverage.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,default=str));print(json.dumps(summary,ensure_ascii=False,indent=2,default=str),flush=True)
    chart(one,'1min','01_逐笔重建_1分钟.html');chart(five,'5min','02_逐笔重建_5分钟.html')

if __name__=='__main__':main()
