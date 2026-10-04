"""Supplement snapshots and independently re-query recent TDX bars; preserve raw records."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import shutil
import pandas as pd
from pytdxdata import TdxData
from pytdxdata.models import Market, KlinePeriod

OUT = Path('research/foxconn_kline_20261005')
RAW = OUT / 'raw'
AUDIT = OUT / 'audit'


def bar_row(bar):
    d = asdict(bar)
    dt = getattr(bar, 'datetime', None)
    if dt is None:
        dt = pd.Timestamp(year=d['year'], month=d['month'], day=d['day'], hour=d.get('hour', 0), minute=d.get('minute', 0))
    d['datetime'] = str(dt)
    return d


async def collect():
    RAW.mkdir(parents=True, exist_ok=True)
    AUDIT.mkdir(parents=True, exist_ok=True)
    src = Path('data/601138_intraday/pytdxdata_1min/snapshot_yearly')
    target = RAW / 'old_snapshots'
    target.mkdir(exist_ok=True)
    dates = set()
    for f in sorted(src.glob('*.csv')):
        shutil.copyfile(f, target/f.name)
        d = pd.read_csv(f, usecols=['date'])
        dates.update(d['date'].str[:10])
    daily = pd.read_csv(RAW / 'old_5m/601138_daily_raw.csv')
    valid = daily[(daily['date'] >= '2018-06-08') & (daily['date'] <= '2026-09-30')]
    valid = valid[pd.to_numeric(valid['tradestatus'], errors='raise') == 1]
    missing = sorted(set(valid['date'])-dates)
    # Repeat representative snapshots to verify positional mapping and historical parser stability.
    probes = ['2018-06-08','2019-01-02','2020-01-02','2026-04-30','2026-08-17','2026-08-24','2026-08-25','2026-09-11']
    tasks = sorted(set(missing + probes))
    manifest = {'missing_snapshot_dates_before': missing, 'snapshot_requests': []}
    async with TdxData() as td:
        for period, name, count in [(KlinePeriod.DAY, 'tdx_daily_fresh', 3500), (KlinePeriod.MIN_1, 'tdx_1m_fresh', 60000)]:
            try:
                bars = await asyncio.wait_for(td.get_kline(Market.SH, '601138', period, count=count), timeout=240)
                d = pd.DataFrame([bar_row(b) for b in bars])
                d.to_csv(RAW/f'{name}.csv.gz', index=False)
                manifest[name] = {'rows':len(d),'columns':list(d.columns),'first':str(d['datetime'].min()) if len(d) else None,'last':str(d['datetime'].max()) if len(d) else None}
                print(name, manifest[name], flush=True)
            except Exception as e:
                manifest[name] = {'error':repr(e)}
                print(name,repr(e),flush=True)
        dest = RAW/'snapshot_fresh'; dest.mkdir(exist_ok=True)
        for day in tasks:
            result = {'date':day}
            try:
                items = await asyncio.wait_for(td.get_minute(Market.SH,'601138',date=int(day.replace('-',''))),timeout=50)
                rows=[asdict(b) for b in items]
                (dest/f'{day}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2))
                result.update(rows=len(rows),first=rows[:1],last=rows[-1:])
            except Exception as e:result['error']=repr(e)
            manifest['snapshot_requests'].append(result)
            (AUDIT/'aux_acquisition.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
            print(json.dumps(result,ensure_ascii=False),flush=True)
    (AUDIT/'aux_acquisition.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':
    asyncio.run(collect())
