"""Check canonical parquet against optimized serving copies, retaining all event fields."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import pandas as pd,numpy as np,json,requests,hashlib,fsspec,pyarrow.parquet as pq
R=Path('research/foxconn_kline_repair_20261005');O=R/'public_r2';D=O/'canonical_trade_probe';D.mkdir(exist_ok=True)
REPO='phields/a-share-l2-trades';REV='2f4c13ee70cabf3f8b831acf7e1686481a762eaa';KEY=['ticker','time_s','tran_id','price_x10000','volume']
x=requests.get(f'https://huggingface.co/api/datasets/{REPO}/revision/{REV}',timeout=40);x.raise_for_status();paths=[v['rfilename'] for v in x.json()['siblings']]
ref=pd.read_csv('research/foxconn_kline_20261005/canonical/daily_reference.csv').set_index('date')
def fetch(day):
 item={'date':day,'revision':REV,'files':[]};frames=[]
 try:
  for path in [p for p in paths if p.startswith(f'data/l2_trades/trade_date={day}/code_prefix=60/') and p.endswith('.parquet')]:
   with fsspec.open(f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/{path}','rb',block_size=1024*1024,cache_type='bytes') as f:
    p=pq.ParquetFile(f);j=p.schema_arrow.names.index('ticker');groups=[]
    for i in range(p.metadata.num_row_groups):
     st=p.metadata.row_group(i).column(j).statistics
     if not st or str(st.min)<='601138'<=str(st.max):groups.append(i)
    item['files'].append({'path':path,'groups':groups})
    for batch in p.iter_batches(batch_size=65536,row_groups=groups):
     import pyarrow.compute as pc
     target=batch.filter(pc.equal(batch.column(batch.schema.get_field_index('ticker')),'601138'))
     if target.num_rows:frames.append(target.to_pandas())
  d=pd.concat(frames,ignore_index=True).drop_duplicates().sort_values(['time_s','tran_id'])
  dest=D/(day+'.parquet');d.to_parquet(dest,index=False);item['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();item['rows']=len(d)
  old=pd.read_parquet(R/'raw/phields'/f'{day}.parquet').drop_duplicates()
  comp=d[KEY].merge(old[KEY],on=KEY,how='outer',indicator=True)
  item['canonical_only']=int((comp._merge=='left_only').sum());item['previous_only']=int((comp._merge=='right_only').sum())
  comp[comp._merge!='both'].to_csv(D/(day+'_basic_field_differences.csv.gz'),index=False)
  regular=d[d.time_s<=54000];late=d[d.time_s>54000]
  ident=['ticker','price_x10000','volume','sale_order_id','buy_order_id','sale_order_price_x10000','buy_order_price_x10000','sale_order_volume','buy_order_volume','side']
  a=late.reset_index(drop=True).reset_index(names='late_index');m=a.merge(regular[ident].drop_duplicates(),on=ident,how='inner')
  item.update(post_close_rows=len(late),post_close_exact_order_tuple_in_session=int(m.late_index.nunique()),post_close_order_tuple_volume_matched=int(m.drop_duplicates('late_index').volume.sum()),all_volume_diff=float(d.volume.sum()-ref.loc[day,'volume']),session_volume_diff=float(regular.volume.sum()-ref.loc[day,'volume']),post_close_sample=late.head(3).to_dict('records'))
 except Exception as e:item['error']=repr(e)
 (D/(day+'.json')).write_text(json.dumps(item,ensure_ascii=False,indent=2,default=str));print(json.dumps(item,ensure_ascii=False,default=str),flush=True);return item
with ThreadPoolExecutor(max_workers=3) as p:res=list(p.map(fetch,['2026-04-21','2026-07-15','2026-07-16']))
(D/'summary.json').write_text(json.dumps(res,ensure_ascii=False,indent=2,default=str))
