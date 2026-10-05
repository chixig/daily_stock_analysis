"""Additional public archive target extraction. No full-market files are retained."""
from pathlib import Path
src=Path('scripts/research/foxconn_kline_public_r2.py').read_text().split("for fld in ['open'")[0]
src=src.replace("['601138','sh601138','601138.SH','SH601138']","['601138','sh601138','sh.601138','601138.SH','SH601138']")
src=src.replace("d=p.read_row_groups(groups,columns=cols).to_pandas();d=d[d[key].astype(str).str.contains('601138',regex=False)]","frames=[]\n    for batch in p.iter_batches(batch_size=65536,row_groups=groups,columns=cols):\n     part=batch.to_pandas();part=part[part[key].astype(str).str.contains('601138',regex=False)]\n     if len(part):frames.append(part)\n    d=pd.concat(frames,ignore_index=True) if frames else pd.DataFrame(columns=cols)")
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
  r['files_total']=len(z.infolist());r['matches']=[dict(path=v.filename,bytes=v.file_size,crc=v.CRC) for v in matches]
  for i,v in enumerate(matches):
   if v.file_size>50_000_000:continue
   b=z.read(v);p=OUT/(f'fox2022_{i}_'+Path(v.filename).name);p.write_bytes(b)
   r.setdefault('saved',[]).append(dict(path=str(p),sha256=hashlib.sha256(b).hexdigest(),bytes=len(b),preview=b[:400].decode('utf-8',errors='replace')))
except Exception as e:r['error']=repr(e)
save();print(json.dumps(r,ensure_ascii=False),flush=True)
