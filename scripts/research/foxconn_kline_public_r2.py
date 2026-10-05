"""Bounded public archive probes; run only on GitHub, preserve raw target rows."""
import json,hashlib,traceback
from pathlib import Path
import requests,fsspec,pyarrow.parquet as pq,pandas as pd
OUT=Path('research/foxconn_kline_repair_20261005/public_r2');OUT.mkdir(parents=True,exist_ok=True)
REPORT=[]
def save():
 (OUT/'acquisition.json').write_text(json.dumps(REPORT,ensure_ascii=False,indent=2,default=str))
def probe(repo,rev,path,name,mode):
 rec=dict(repo=repo,revision=rev,path=path,name=name);REPORT.append(rec)
 try:
  u=f'https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}'
  with fsspec.open(u,'rb',block_size=1024*1024,cache_type='bytes') as f:
   p=pq.ParquetFile(f);names=p.schema_arrow.names
   rec.update(rows=p.metadata.num_rows,groups=p.metadata.num_row_groups,columns=names[:35],matching_columns=[n for n in names if '601138' in n],metadata={k.decode():v.decode()[:2000] for k,v in (p.schema_arrow.metadata or {}).items() if k==b'pandas'})
   if mode=='wide':
    target=[n for n in names if '601138' in n];idx=[n for n in names if any(t in n.lower() for t in ['time','date','index'])]
    if not target:rec['status']='stock_column_absent';return
    cols=list(dict.fromkeys(target+idx));d=p.read(columns=cols).to_pandas();rec['index']=str(d.index);rec['index_names']=d.index.names
   else:
    keys=[n for n in names if n in ['ticker','symbol','code','stock_code','ts_code','instrument']]
    if not keys:rec['status']='unknown_stock_key';return
    key=keys[0];j=names.index(key);groups=[]
    for i in range(p.metadata.num_row_groups):
     st=p.metadata.row_group(i).column(j).statistics
     if not st or any(str(st.min)<=t<=str(st.max) for t in ['601138','sh601138','601138.SH','SH601138']):groups.append(i)
    rec['selected_groups']=groups
    if len(groups)>200:rec['status']='too_many_groups_for_probe';return
    cols=names if mode=='bars' else [n for n in names if not n.startswith(('bid','ask'))]
    d=p.read_row_groups(groups,columns=cols).to_pandas();d=d[d[key].astype(str).str.contains('601138',regex=False)]
   rec.update(target_rows=len(d),head=d.head(2).reset_index().to_dict('records'),tail=d.tail(2).reset_index().to_dict('records'))
   if len(d):
    dest=OUT/(name+'.parquet');d.to_parquet(dest);rec['sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();rec['bytes']=dest.stat().st_size
   rec['status']='ok'
 except Exception as e:rec['error']=repr(e);rec['trace']=traceback.format_exc()[-1200:]
 finally:save();print(json.dumps(rec,ensure_ascii=False,default=str),flush=True)
for fld in ['open','high','low','close','volume','amount']:
 probe('suncong/ashare_1min','c05c0da3940e167d689392852e9d490107a2c3e1',fld+'.parquet','suncong_'+fld,'wide')
for year in [2021,2022,2023,2024,2025,2026]:
 probe('ANTICH/traderharness-ashare-5y','3bf5151ab3e94851bb09dd8ade815563c44b15a6',f'5min_clean/year={year}/part-6.parquet',f'ANTICH_{year}','bars')
repo='phields/a-share-l2-market-depth';rev='558381a6b22c9012ffcfa5c4f972eaa1633e2dcd'
r=requests.get(f'https://huggingface.co/api/datasets/{repo}/revision/{rev}',timeout=60);r.raise_for_status()
paths=[v['rfilename'] for v in r.json()['siblings']]
for day in ['2026-07-14','2026-07-15','2026-07-16','2026-04-01']:
 for i,path in enumerate([p for p in paths if p.startswith(f'data/l2_snapshots/trade_date={day}/code_prefix=60/') and p.endswith('.parquet')]):
  probe(repo,rev,path,f'depth_{day}_{i}','snapshot')
