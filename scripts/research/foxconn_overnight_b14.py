import os,sys,json,hashlib,asyncio,subprocess,inspect,dataclasses
from pathlib import Path
import pandas as pd
R=Path('research/foxconn_overnight_20260917_b14')
async def probe(date):
 from pytdxdata import TdxData
 from pytdxdata.models import Market
 async with TdxData() as td:
  rows=await td.get_transactions(Market.SH,'601138',date=int(date.replace('-','')),start=0,count=20000)
  items=[dataclasses.asdict(x) if dataclasses.is_dataclass(x) else vars(x) for x in rows]
  pd.DataFrame(items).to_csv(R/(date+'_transactions.csv'),index=False)
  (R/(date+'_probe.json')).write_text(json.dumps(dict(date=date,rows=len(items),fields=list(items[0])if items else [],first=items[:2],last=items[-2:]),default=str,indent=2))
async def serial_probe(date):
 from pytdxdata import TdxData
 from pytdxdata.protocol.commands.transaction import MacTransactionCmd
 async with TdxData() as td:
  pc=await td._mac_pool.acquire();allrows=[];pages=[]
  try:
   for start in range(0,20000,1000):
    rows=await pc.execute(MacTransactionCmd(1,'601138',int(date.replace('-','')),start,1000))
    items=[dataclasses.asdict(x) for x in rows];pages.append(dict(start=start,count=len(items),first=items[0]['time']if items else None,last=items[-1]['time']if items else None))
    allrows.extend(items)
    pd.DataFrame(allrows).to_csv(R/(date+'_serial_transactions.csv'),index=False)
    (R/(date+'_serial_pages.json')).write_text(json.dumps(pages,indent=2))
    if len(items)<1000:break
  finally:await td._mac_pool.release(pc)
  print(json.dumps(dict(date=date,rows=len(allrows),pages=pages)),flush=True)

def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True)
 from pytdxdata import TdxData
 (R/'provider_methods.txt').write_text(inspect.getsource(TdxData.get_transactions)+'\n'+inspect.getsource(TdxData.get_kline))
 base=Path('research/foxconn_overnight_20260917_b13');manifest=json.loads((base/'manifest.json').read_text());inputs={}
 for name in ['tdx_recovered_1m.csv','recovered_candidate_coverage.csv','unique_required_dates.csv']:
  p=base/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==manifest['files'][str(p)];inputs[str(p)]=h
 dates=['2023-05-16','2023-09-25','2024-08-01','2025-11-28','2026-07-30'];results=[]
 for date in ([] if (R/'probe_summary.json').exists() else dates):
  try:
   cp=subprocess.run([sys.executable,__file__,'--probe',date],capture_output=True,text=True,timeout=75)
   rec=dict(date=date,status='ok'if cp.returncode==0 else 'error',returncode=cp.returncode,detail=(cp.stdout+cp.stderr)[-2000:])
   if (R/(date+'_probe.json')).exists():rec.update(json.loads((R/(date+'_probe.json')).read_text()))
  except subprocess.TimeoutExpired:rec=dict(date=date,status='timeout75s')
  results.append(rec);print(json.dumps(rec,default=str),flush=True)
 if results:(R/'probe_summary.json').write_text(json.dumps(results,default=str,indent=2))
 serial=[]
 for date in dates:
  try:
   cp=subprocess.run([sys.executable,__file__,'--serial',date],capture_output=True,text=True,timeout=75)
   serial.append(dict(date=date,status='ok'if cp.returncode==0 else 'error',detail=(cp.stdout+cp.stderr)[-1800:]))
  except subprocess.TimeoutExpired:serial.append(dict(date=date,status='timeout75s'))
 (R/'serial_summary.json').write_text(json.dumps(serial,indent=2))

 # Assess returned records as observations, not certified tick/OHLC reconstruction.
 ledger=pd.read_csv('research/foxconn_overnight_20260916_b08/daily_ledger.csv',parse_dates=['date']).set_index('date')
 trades=pd.read_csv('research/foxconn_overnight_20260916_b11/exit_trades.csv',parse_dates=['date','actual_exit']);trades=trades[trades.entry.eq('C')&trades.exit_model.eq('1000_S2')]
 quality=[];witness=[]
 for date,route in [(d,r)for d in dates for r in ['original','serial']]:
  p=R/(date+('_serial_transactions.csv'if route=='serial'else '_transactions.csv'))
  if not p.exists() or p.stat().st_size<20:continue
  x=pd.read_csv(p,dtype={'code':str});x=x.sort_values('time',kind='stable');d=ledger.loc[pd.Timestamp(date)]
  row=dict(date=date,route=route,rows=len(x),first=x.time.min(),last=x.time.max(),price_high=float(x.price.max()),price_low=float(x.price.min()),price_last=float(x.iloc[-1].price),daily_high=d.high,daily_low=d.low,daily_close=d.close,high_gap=float(d.high-x.price.max()),low_gap=float(x.price.min()-d.low),close_gap=float(x.iloc[-1].price-d.close),vol_hands=float(x.vol.sum()),daily_volume_shares=float(d.volume),volume_ratio=float(x.vol.sum()*100/d.volume),aggregated_records=int(x.trade_count.gt(1).sum()),trade_count_sum=int(x.trade_count.sum()),duplicate_rows=int(x.duplicated().sum()),raw_hash=hashlib.sha256(p.read_bytes()).hexdigest())
  quality.append(row)
  for _,t in trades[trades.actual_exit.eq(pd.Timestamp(date))].iterrows():
   line=float(__import__('numpy').floor((t.close*1.0005*.98-t.dividend*.8)*100+1e-8)/100);early=x[x.time.ge('09:25:00')&x.time.le('10:00:00')];cross=early[early.price.le(line+1e-7)]
   witness.append(dict(route=route,signal_date=t.date,exit_date=date,stop_line=line,early_observed_low=float(early.price.min())if len(early)else None,first_observed_cross=None if not len(cross)else cross.iloc[0].time,first_observed_cross_price=None if not len(cross)else float(cross.iloc[0].price),old_reason=t.reason,old_clock=t.exit_clock,old_price=t.model_exit,caution='Observed noncross cannot prove no crossing. Date identity depends on requested date plus daily crosscheck; records have no date field.'))
 pd.DataFrame(quality).to_csv(R/'transaction_quality.csv',index=False);pd.DataFrame(witness).to_csv(R/'stop_observations.csv',index=False)

 need=pd.read_csv(base/'recovered_candidate_coverage.csv');remaining=need[~(need.entry_covered&need.exit_covered)];assert len(remaining)==52;remaining.to_csv(R/'remaining_52_trades.csv',index=False)
 (R/'audit.json').write_text(json.dumps(dict(input_hashes=inputs,remaining=52,data_end='2026-09-11',caution='Transactions may be aggregated; request count does not guarantee completeness. Probe only; no new return claims or automated trading.'),indent=2))
 (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in R.iterdir()if p.is_file()and p.name!='manifest.json'}),indent=2))
if __name__=='__main__':
 if '--serial' in sys.argv:asyncio.run(serial_probe(sys.argv[-1]))
 elif '--probe' in sys.argv:asyncio.run(probe(sys.argv[-1]))
 else:run()
