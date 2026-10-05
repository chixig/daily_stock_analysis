"""Additional public archive target extraction. No full-market files are retained."""
from pathlib import Path
src=Path('scripts/research/foxconn_kline_public_r2.py').read_text().split("for fld in ['open'")[0]
src=src.replace("['601138','sh601138','601138.SH','SH601138']","['601138','sh601138','sh.601138','601138.SH','SH601138']")
src=src.replace("d=p.read_row_groups(groups,columns=cols).to_pandas();d=d[d[key].astype(str).str.contains('601138',regex=False)]","frames=[]\n    for batch in p.iter_batches(batch_size=65536,row_groups=groups,columns=cols):\n     part=batch.to_pandas();part=part[part[key].astype(str).str.contains('601138',regex=False)]\n     if len(part):frames.append(part)\n    d=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=cols)")
src=src.replace("if not st or any(str(st.min)<=t<=str(st.max) for t in ['601138','sh601138','sh.601138','601138.SH','SH601138']):groups.append(i)","lo=__import__('re').findall(r'[0-9]{6}',str(st.min)) if st else [];hi=__import__('re').findall(r'[0-9]{6}',str(st.max)) if st else []\n     if not st or (lo and hi and lo[0]<='601138'<=hi[0]):groups.append(i)")
src=src.replace("rec['selected_groups']=groups", "rec['selected_groups']=groups;rec['stock_bound_samples']=[{'min':str(p.metadata.row_group(i).column(j).statistics.min),'max':str(p.metadata.row_group(i).column(j).statistics.max)} for i in [0,min(1,p.metadata.num_row_groups-1),p.metadata.num_row_groups-1] if p.metadata.row_group(i).column(j).statistics]")
exec(src)
OUT=Path('research/foxconn_kline_repair_20261005/public_extra');OUT.mkdir(parents=True,exist_ok=True)
for i in [0,1]:
 probe('qfzcxdl/StockData','b1d13702003d7f084a9645c548caabbe74b82457',f'data/train-0000{i}-of-00002.parquet',f'qfzcxdl_{i}','bars')
from remotezip import RemoteZip
repo='Foxintohumanbeing/2022_Chinese_Stock_Market_Minbar_Data';rev='8b9cc9779a1c6b09d93a2b03db44ee1ddc3e7441'
r=dict(repo=repo,revision=rev);REPORT.append(r)
try:
 with RemoteZip(f'https://huggingface.co/datasets/{repo}/resolve/{rev}/2022.zip',timeout=60) as z:
  matches=[v for v in z.infolist() if '601138' in v.filename and not v.is_dir()]
  r['files_total']=len(z.infolist());r['members']=[dict(path=v.filename,bytes=v.file_size) for v in z.infolist()];r['matches']=[dict(path=v.filename,bytes=v.file_size,crc=v.CRC) for v in matches]
  for i,v in enumerate(matches):
   if v.file_size>50_000_000:continue
   b=z.read(v);p=OUT/(f'fox2022_{i}_'+Path(v.filename).name);p.write_bytes(b)
   r.setdefault('saved',[]).append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),preview=b[:400].decode('utf-8',errors='replace')))
except Exception as e:r['error']=repr(e)
save();print(json.dumps(r,ensure_ascii=False),flush=True)
# The archive is partitioned by trading date, not by symbol: inspect three dates.
import io,pyarrow.compute as pc
try:
 with RemoteZip(f'https://huggingface.co/datasets/{repo}/resolve/{rev}/2022.zip',timeout=120) as z:
  files=sorted([v for v in z.infolist() if v.filename.startswith('2022/') and v.filename.endswith('.parquet')],key=lambda v:v.filename)
  for v in [files[0],files[len(files)//2],files[-1]]:
   item={'repo':repo,'revision':rev,'member':v.filename};REPORT.append(item)
   try:
    if v.file_size>300_000_000:raise ValueError('Member exceeds 300MB bound')
    b=z.read(v);pf=pq.ParquetFile(io.BytesIO(b));names=pf.schema_arrow.names
    item.update(member_sha256=hashlib.sha256(b).hexdigest(),columns=names,rows=pf.metadata.num_rows)
    keys=[n for n in names if n.lower() in ['symbol','ticker','code','stock_code','securityid','instrument','order_book_id','sec_code','证券代码','代码','security_id']]
    if not keys:item['status']='stock_key_requires_review';continue
    key=keys[0];frames=[]
    for batch in pf.iter_batches(batch_size=16384):
     d=batch.to_pandas();d=d[d[key].astype(str).str.contains('601138',regex=False)]
     if len(d):frames.append(d)
    d=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=names)
    item['target_rows']=len(d)
    if len(d):
     dest=OUT/(Path(v.filename).stem+'_601138.parquet');d.to_parquet(dest,index=False)
     item['target_sha256']=hashlib.sha256(dest.read_bytes()).hexdigest();item['head']=d.head(1).to_dict('records');item['tail']=d.tail(1).to_dict('records')
    del b
   except Exception as e:item['error']=repr(e)
   finally:save();print(json.dumps(item,ensure_ascii=False,default=str),flush=True)
except Exception as e:REPORT.append({'fox2022_sample_error':repr(e)});save()
# Open public share code as published by the data owner; never bypass account gates.
try:
 u='https://drive-pc.quark.cn/1/clouddrive/share/sharepage/token?pr=ucpro&fr=pc'
 response=requests.post(u,json={'pwd_id':'8bae13aef6a9','passcode':'Gxcc'},timeout=30)
 payload=response.json();share={'repo':'submato/ashare-l2','public_share':'8bae13aef6a9','http_status':response.status_code,'status':payload.get('status'),'code':payload.get('code'),'message':payload.get('message')}
 token=payload.get('data',{}).get('stoken')
 if token:
  r=requests.get('https://drive-pc.quark.cn/1/clouddrive/share/sharepage/detail',params={'pr':'ucpro','fr':'pc','pwd_id':'8bae13aef6a9','stoken':token,'pdir_fid':'0','force':'0','_page':'1','_size':'100','_sort':'file_type:asc,file_name:asc'},timeout=30)
  data=r.json();share['directory_status']=r.status_code;share['directory_code']=data.get('code');share['directory_message']=data.get('message');share['files']=[{k:v.get(k) for k in ['fid','file_name','size','dir']} for v in data.get('data',{}).get('list',[])]
 REPORT.append(share)
except Exception as e:REPORT.append({'repo':'submato/ashare-l2','error':repr(e)})
save()
