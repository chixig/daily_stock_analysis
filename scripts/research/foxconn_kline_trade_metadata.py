"""Compare acquired target rows to the publisher's declared ticker calendar."""
import io
import json
from pathlib import Path
import pandas as pd
import requests

ROOT=Path('research/foxconn_kline_repair_20261005')
REV='2f4c13ee70cabf3f8b831acf7e1686481a762eaa'
def main():
    base=f'https://huggingface.co/datasets/phields/a-share-l2-trades/resolve/{REV}/'
    r=requests.get(base+'metadata/ticker_calendar.parquet',timeout=120);r.raise_for_status()
    x=pd.read_parquet(io.BytesIO(r.content))
    x=x[x.ticker.astype(str).eq('601138')].copy()
    x['trade_date']=pd.to_datetime(x.trade_date).dt.strftime('%Y-%m-%d')
    rows=[]
    for row in x.to_dict('records'):
        p=ROOT/'raw/phields'/(row['trade_date']+'.parquet')
        xraw=pd.read_parquet(p) if p.exists() else pd.DataFrame()
        row['raw_downloaded_rows']=len(xraw)
        row['acquired_rows']=len(xraw.drop_duplicates())
        row['row_count_match']=row['acquired_rows']==row['row_count']
        rows.append(row)
    pd.DataFrame(rows).to_csv(ROOT/'audit/publisher_row_count_comparison.csv',index=False)
    result={'publisher_revision':REV,'declared_days':len(rows),'acquired_days':sum(r['acquired_rows']>0 for r in rows),'all_declared_row_counts_match':all(r['row_count_match'] for r in rows),'failed_dates':[r['trade_date'] for r in rows if not r['row_count_match']],'independent_exchange_completeness_certified':False}
    (ROOT/'audit/publisher_row_count_summary.json').write_text(json.dumps(result,indent=2))
    print(json.dumps(result),flush=True)
    assert result['all_declared_row_counts_match'],result

if __name__=='__main__':main()
