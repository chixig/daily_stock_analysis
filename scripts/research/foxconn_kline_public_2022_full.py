"""Extract every available 2022 native minbar day for 601138, retaining publisher fields."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
import io,json,hashlib
import pandas as pd,pyarrow.parquet as pq,pyarrow.compute as pc
from remotezip import RemoteZip
O=Path('research/foxconn_kline_repair_20261005/public_extra');M=O/'full_manifest';M.mkdir(exist_ok=True)
REPO='Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data';REV='8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441';URL=f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/2022.zip'
with RemoteZip(URL,timeout=120) as z:members=sorted([v.filename for v in z.infolist() if v.filename.startswith('2022/') and v.filename.endswith('.parquet')])
def fetch(member):
 dest=O/(Path(member).stem+'_601138.parquet');r={'repo':REPO,'revision':REV,'member':member}
 try:
  if dest.exists():r['status']='reused_verified_sample'
  else:
   with RemoteZip(URL,timeout=120) as z:
    v=z.getinfo(member)
    if v.file_size>300_000_000:raise ValueError('member exceeds 300MB probe bound')
    b=z.read(v)
   r['full_member_sha256']=hashlib.sha256(b).hexdigest();r['full_member_bytes']=len(b)
   pf=pq.ParquetFile(io.BytesIO(b));frames=[]
   for batch in pf.iter_batches(batch_size=65536):
    hit=pc.equal(batch.column(batch.schema.get_field_index('symbol')),'601138.SH')
    target=batch.filter(hit)
    if target.num_rows:frames.append(target.to_pandas())
   if not frames:raise ValueError('601138 absent')
   d=pd.concat(frames,ignore_index=True);d.to_parquet(dest,index=False);r['status']='extracted'
  r['target_rows']=pq.ParquetFile(dest).metadata.num_rows;r['target_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest()
 except Exception as e:r['error']=repr(e);r['status']='error'
 (M/(Path(member).stem+'.json')).write_text(json.dumps(r,ensure_ascii=False,indent=2));print(json.dumps(r,ensure_ascii=False),flush=True);return r
with ThreadPoolExecutor(max_workers=3) as pool:
 results=list(pool.map(fetch,members))
summary={'repo':REPO,'revision':REV,'archive_trading_files':len(members),'downloaded_target_files':sum(r['status']!='error' for r in results),'target_rows':sum(r.get('target_rows',0) for r in results),'errors':[r for r in results if r['status']=='error']}
(O/'full_acquisition.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)
