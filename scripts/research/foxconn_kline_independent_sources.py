"""Acquire publicly accessible single-stock archive members and trade evidence on GitHub."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
from pathlib import Path
import zipfile
import requests
import pandas as pd
import pyarrow.parquet as pq
import fsspec
from remotezip import RemoteZip

OUT=Path('research/foxconn_kline_repair_20261005');RAW=OUT/'raw';AUDIT=OUT/'audit'
ZIP_REPO='wind17/china-a-share-zip';ZIP_REV='ca4c51770f1fafb40317cc35bfd92e7c2be17827'
L2_REPO='phields/a-share-l2-trades';L2_REV='2f4c13ee70cabf3f8b831acf7e1686481a762eaa'

def url(repo,rev,path):return f'https://huggingface.co/datasets/{repo}/resolve/{rev}/{path}'
def save(name,obj):
    (AUDIT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str))
def archives():
    results=json.loads((AUDIT/'archive_acquisition.json').read_text()) if (AUDIT/'archive_acquisition.json').exists() else []
    dest=RAW/'wind17';dest.mkdir(exist_ok=True)
    for year in range(2018,2027):
        if list(dest.glob(f'{year}_*_sh601138.csv')):continue
        item={'year':year,'repo':ZIP_REPO,'revision':ZIP_REV}
        try:
            with RemoteZip(url(ZIP_REPO,ZIP_REV,f'{year}.zip'),timeout=60) as z:
                entries=z.infolist();hits=[f for f in entries if '601138' in f.filename and not f.is_dir()]
                item.update(member_count=len(entries),sample=[f.filename for f in entries[:8]],matches=[{'path':f.filename,'bytes':f.file_size} for f in hits])
                for i,f in enumerate(hits):
                    if f.file_size>100_000_000:raise ValueError('Single member exceeds research probe limit')
                    data=z.read(f)
                    p=dest/(f'{year}_{i}_'+Path(f.filename).name);p.write_bytes(data)
                    item.setdefault('downloaded',[]).append({'path':str(p),'sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'preview':data[:450].decode('utf-8',errors='replace')})
        except Exception as e:item['error']=repr(e)
        results.append(item);save('archive_acquisition.json',results);print(json.dumps(item,ensure_ascii=False),flush=True)

def l2():
    dest=RAW/'phields';dest.mkdir(exist_ok=True)
    info=requests.get('https://huggingface.co/api/datasets/'+L2_REPO+'/revision/'+L2_REV,timeout=40);info.raise_for_status()
    paths=[x['rfilename'] for x in info.json()['siblings']]
    results=json.loads((AUDIT/'l2_acquisition.json').read_text()) if (AUDIT/'l2_acquisition.json').exists() else []
    days=sorted({p.split('trade_date=')[1].split('/')[0] for p in paths if p.startswith('data/l2_trades/trade_date=') and '/code_prefix=60/' in p})
    pending=[d for d in days if not (dest/(d+'.parquet')).exists()][:20]
    def fetch_day(day):
        item={'date':day,'repo':L2_REPO,'revision':L2_REV,'files':[]};frames=[]
        optimized=[p for p in paths if p.startswith(f'serving_v1/l2_trades/trade_date={day}/code_prefix=60/bucket=000/') and p.endswith('.parquet')]
        targets=optimized or [p for p in paths if p.startswith(f'data/l2_trades/trade_date={day}/code_prefix=60/') and p.endswith('.parquet')]
        item['layout']='serving_v1_bucket_000' if optimized else 'canonical_data'
        try:
            for path in targets:
                record={'path':path};item['files'].append(record)
                # Range requests only fetch the footer and row groups whose ticker bounds contain 601138.
                with fsspec.open(url(L2_REPO,L2_REV,path),mode='rb',block_size=1024*1024,cache_type='bytes') as f:
                    pf=pq.ParquetFile(f);record['schema']=str(pf.schema_arrow)
                    idx=pf.schema_arrow.names.index('ticker');rg=[]
                    for i in range(pf.metadata.num_row_groups):
                        st=pf.metadata.row_group(i).column(idx).statistics
                        lo=str(st.min) if st else '';hi=str(st.max) if st else '999999'
                        if lo<='601138'<=hi:rg.append(i)
                    record['selected_groups']=rg
                    if rg:
                        d=pf.read_row_groups(rg,columns=['ticker','time_s','tran_id','price_x10000','volume']).to_pandas()
                        frames.append(d[d.ticker.astype(str)=='601138'])
            if frames:
                x=pd.concat(frames,ignore_index=True).sort_values(['time_s','tran_id'])
                p=dest/(day+'.parquet');x.to_parquet(p,index=False)
                item.update(rows=len(x),first=x.head(3).to_dict('records'),last=x.tail(3).to_dict('records'),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
            else:item['rows']=0
        except Exception as e:item['error']=repr(e)
        return item
    with ThreadPoolExecutor(max_workers=4) as pool:
        for future in as_completed([pool.submit(fetch_day,day) for day in pending]):
            item=future.result();results.append(item);save('l2_acquisition.json',results);print(json.dumps(item,ensure_ascii=False),flush=True)

if __name__=='__main__':
    for p in [RAW,AUDIT]:p.mkdir(parents=True,exist_ok=True)
    archives();l2()
