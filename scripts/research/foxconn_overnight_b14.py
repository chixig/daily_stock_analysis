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
def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True)
 from pytdxdata import TdxData
 (R/'provider_methods.txt').write_text(inspect.getsource(TdxData.get_transactions)+'\n'+inspect.getsource(TdxData.get_kline))
 base=Path('research/foxconn_overnight_20260917_b13');manifest=json.loads((base/'manifest.json').read_text());inputs={}
 for name in ['tdx_recovered_1m.csv','recovered_candidate_coverage.csv','unique_required_dates.csv']:
  p=base/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==manifest['files'][str(p)];inputs[str(p)]=h
 dates=['2023-05-16','2023-09-25','2024-08-01','2025-11-28','2026-07-30'];results=[]
 for date in dates:
  try:
   cp=subprocess.run([sys.executable,__file__,'--probe',date],capture_output=True,text=True,timeout=75)
   rec=dict(date=date,status='ok'if cp.returncode==0 else 'error',returncode=cp.returncode,detail=(cp.stdout+cp.stderr)[-2000:])
   if (R/(date+'_probe.json')).exists():rec.update(json.loads((R/(date+'_probe.json')).read_text()))
  except subprocess.TimeoutExpired:rec=dict(date=date,status='timeout75s')
  results.append(rec);print(json.dumps(rec,default=str),flush=True)
 (R/'probe_summary.json').write_text(json.dumps(results,default=str,indent=2))
 need=pd.read_csv(base/'recovered_candidate_coverage.csv');remaining=need[~(need.entry_covered&need.exit_covered)];assert len(remaining)==52;remaining.to_csv(R/'remaining_52_trades.csv',index=False)
 (R/'audit.json').write_text(json.dumps(dict(input_hashes=inputs,remaining=52,data_end='2026-09-11',caution='Transactions may be aggregated; request count does not guarantee completeness. Probe only; no new return claims or automated trading.'),indent=2))
 (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in R.iterdir()if p.is_file()and p.name!='manifest.json'}),indent=2))
if __name__=='__main__':
 if '--probe' in sys.argv:asyncio.run(probe(sys.argv[-1]))
 else:run()
