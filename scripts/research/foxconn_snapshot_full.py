"""Retrieve every active trading day's native TDX price/volume/average snapshot."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import pandas as pd
from pytdxdata import TdxData
from pytdxdata.models import Market

ROOT=Path('research/foxconn_kline_20261005');RAW=ROOT/'raw';AUDIT=ROOT/'audit'

async def run():
    daily=pd.read_csv(RAW/'old_5m/601138_daily_raw.csv')
    days=sorted(set(daily.loc[(daily.tradestatus.astype(int)==1)&(daily.date>='2018-06-08')&(daily.date<='2026-09-30'),'date'].str[:10]))
    out=RAW/'snapshot_full';out.mkdir(exist_ok=True)
    sem=asyncio.Semaphore(4);failures=[];allrows=[]
    async with TdxData() as td:
        async def one(day):
            async with sem:
                for attempt in range(2):
                    try:
                        items=await asyncio.wait_for(td.get_minute(Market.SH,'601138',date=int(day.replace('-',''))),timeout=45)
                        if len(items)!=240:raise ValueError(f'Expected 240 positions, got {len(items)}')
                        rows=[]
                        for i,b in enumerate(items):
                            d=asdict(b);d.update(trade_date=day,position=i)
                            rows.append(d)
                        return rows
                    except Exception as exc:
                        if attempt:failures.append({'date':day,'error':repr(exc)});return []
                        await asyncio.sleep(1)
        for year in sorted({d[:4] for d in days}):
            rows=[];ydays=[d for d in days if d.startswith(year)]
            for offset in range(0,len(ydays),40):
                pieces=await asyncio.gather(*(one(d) for d in ydays[offset:offset+40]))
                rows.extend(r for part in pieces for r in part)
                print(year,offset+len(pieces),'/',len(ydays),'rows',len(rows),'failures',len(failures),flush=True)
            pd.DataFrame(rows).to_csv(out/f'{year}.csv.gz',index=False)
            allrows.extend(rows)
            (AUDIT/'snapshot_full_acquisition.json').write_text(json.dumps({'requested_days':len(days),'acquired_days':len(allrows)//240,'rows':len(allrows),'failures':failures},ensure_ascii=False,indent=2))
    print(json.dumps({'requested_days':len(days),'acquired_days':len(allrows)//240,'rows':len(allrows),'failures':failures},ensure_ascii=False),flush=True)

if __name__=='__main__':asyncio.run(run())
