"""Confirm optimized publisher partitions reproduce the acquired canonical records."""
import json
import time
from pathlib import Path
import pandas as pd
import requests
import fsspec
import pyarrow.parquet as pq

ROOT=Path('research/foxconn_kline_repair_20261005')
REV='2f4c13ee70cabf3f8b831acf7e1686481a762eaa';REPO='phields/a-share-l2-trades'
def main():
    info=requests.get('https://huggingface.co/api/datasets/'+REPO+'/revision/'+REV,timeout=40).json()
    paths=[x['rfilename'] for x in info['siblings']];results=[]
    for day in ['2026-04-01','2026-04-02','2026-04-03']:
        start=time.monotonic();frames=[];groups=[]
        targets=[p for p in paths if f'serving_v1/l2_trades/trade_date={day}/code_prefix=60/bucket=000/' in p and p.endswith('.parquet')]
        for path in targets:
            url=f'https://huggingface.co/datasets/{REPO}/resolve/{REV}/{path}'
            with fsspec.open(url,'rb',block_size=1024*1024,cache_type='bytes') as f:
                pf=pq.ParquetFile(f);idx=pf.schema_arrow.names.index('ticker');rg=[]
                for i in range(pf.metadata.num_row_groups):
                    st=pf.metadata.row_group(i).column(idx).statistics
                    if not st or str(st.min)<='601138'<=str(st.max):rg.append(i)
                if rg:
                    x=pf.read_row_groups(rg,columns=['ticker','time_s','tran_id','price_x10000','volume']).to_pandas()
                    frames.append(x[x.ticker.astype(str).eq('601138')])
                groups.append({'path':path,'selected':rg,'total_groups':pf.metadata.num_row_groups})
        x=pd.concat(frames,ignore_index=True).sort_values(['time_s','tran_id']).reset_index(drop=True)
        y=pd.read_parquet(ROOT/'raw/phields'/(day+'.parquet')).sort_values(['time_s','tran_id']).reset_index(drop=True)
        raw_count=len(y);y=y.drop_duplicates().reset_index(drop=True)
        pd.testing.assert_frame_equal(x,y)
        results.append({'date':day,'rows':len(x),'canonical_unique_exact_match':True,'canonical_raw_rows':raw_count,'canonical_duplicate_rows':raw_count-len(y),'elapsed_seconds':time.monotonic()-start,'groups':groups})
    (ROOT/'audit/serving_probe.json').write_text(json.dumps(results,indent=2));print(json.dumps(results),flush=True)

if __name__=='__main__':main()
