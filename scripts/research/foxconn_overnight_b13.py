import os,json,hashlib,zipfile,subprocess,sys
from pathlib import Path
import numpy as np
import pandas as pd
R=Path('research/foxconn_overnight_20260917_b13')
def save(n,x):
 pd.DataFrame(x).to_csv(R/n,index=False)
def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True)
 src=Path('research/foxconn_t0_20260913/source/601138-full-5min-history.zip'); b12=Path('research/foxconn_overnight_20260917_b12')
 manifest=json.loads((b12/'manifest.json').read_text()); inputs={}
 for p,h in manifest['files'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;inputs[p]=h
 inputs[str(src)]=hashlib.sha256(src.read_bytes()).hexdigest()
 with zipfile.ZipFile(src) as z:
  names=z.namelist();(R/'archive_members.json').write_text(json.dumps(names))
  m=pd.read_csv(z.open(next(n for n in names if n.endswith('601138_5min_all.csv'))))
  daily=pd.read_csv(z.open(next(n for n in names if n.endswith('601138_daily_raw.csv'))))
 m['date']=pd.to_datetime(m.date);daily['date']=pd.to_datetime(daily.date);daily=daily.set_index('date')
 m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock'])
 ledger=pd.read_csv('research/foxconn_overnight_20260916_b08/daily_ledger.csv',parse_dates=['date']).set_index('date')
 t=pd.read_csv('research/foxconn_overnight_20260916_b11/exit_trades.csv',parse_dates=['date','actual_exit']);t=t[t.entry.eq('C')&t.exit_model.eq('1000_S2')];assert len(t)==61
 rows=[]
 for _,r in t.iterrows():
  b=m[m.date.eq(r.actual_exit)];d=daily.loc[r.actual_exit];l=ledger.loc[r.actual_exit];early=b[b.clock.le('10:00')]
  line=np.floor((r.close*1.0005*.98-r.dividend*.8)*100+1e-8)/100
  rows.append(dict(signal_date=r.date,exit_date=r.actual_exit,bars=len(b),adjustflags=','.join(sorted(b.adjustflag.astype(str).unique())),daily_adjustflag=d.adjustflag,high_gap=d.high-b.high.max(),low_gap=b.low.min()-d.low,daily_ledger_high_delta=l.high-d.high,daily_ledger_low_delta=l.low-d.low,stop_line=line,morning_low=early.low.min(),daily_low=d.low,original_reason=r.reason,original_exit_clock=r.exit_clock,possible_hidden_cross=bool(d.low<=line and early.low.min()>line and d.open>line),whole_day_hidden_cross=bool(d.low<=line and b.low.min()>line and d.open>line)))
 a=pd.DataFrame(rows);save('candidate_price_audit.csv',a)
 req=pd.read_csv(b12/'required_fine_data.csv');unique=req.groupby('date').purpose.agg(lambda x:','.join(sorted(set(x)))).reset_index();save('unique_required_dates.csv',unique)
 # Repeat two maximum-discrepancy dates using existing vendor. Failure is recorded, never replaced by stale rows.
 probes=[]
 for day in ['2025-12-05','2026-07-31']:
  code="""import baostock as bs,pandas as pd,sys
from pathlib import Path
p=Path(sys.argv[2]);lg=bs.login();assert lg.error_code=='0',lg.error_msg
try:
 for freq in ['5','d']:
  fields='date,time,code,open,high,low,close,volume,amount,adjustflag' if freq=='5' else 'date,code,open,high,low,close,volume,amount,adjustflag'
  rs=bs.query_history_k_data_plus('sh.601138',fields,start_date=sys.argv[1],end_date=sys.argv[1],frequency=freq,adjustflag='3');rows=[]
  while rs.error_code=='0' and rs.next():rows.append(rs.get_row_data())
  assert rs.error_code=='0',rs.error_msg
  pd.DataFrame(rows,columns=rs.fields).to_csv(p/(sys.argv[1]+'_'+freq+'.csv'),index=False)
finally:bs.logout()
"""
  try:
   cp=subprocess.run([sys.executable,'-c',code,day,str(R)],capture_output=True,text=True,timeout=45)
   rec=dict(date=day,returncode=cp.returncode,status='ok' if cp.returncode==0 else 'error',detail=(cp.stdout+cp.stderr)[-1500:])
   if cp.returncode==0:
    mm=pd.read_csv(R/(day+'_5.csv'));dd=pd.read_csv(R/(day+'_d.csv'))
    rec.update(rows5=len(mm),rowsdaily=len(dd))
    if len(mm) and len(dd):
     rec.update(high_gap=float(dd.iloc[0].high-mm.high.max()),low_gap=float(mm.low.min()-dd.iloc[0].low))
     old=m[m.date.eq(pd.Timestamp(day))].set_index('time');new=mm.set_index('time');rec['same_ohlc_as_archive']=bool(old.index.equals(new.index) and np.allclose(old[['open','high','low','close']],new[['open','high','low','close']]))
  except subprocess.TimeoutExpired:rec=dict(date=day,status='timeout45s')
  probes.append(rec)
 (R/'vendor_requery.json').write_text(json.dumps(probes,indent=2))
 # Archived probe found deeper data than the saved 20-day library. Retry the exact offset call.
 tdx_code="""import asyncio,sys,json,importlib.metadata
from pathlib import Path
sys.path.insert(0,'scripts')
from download_601138_pytdxdata_1min import TdxData,MARKET,CODE,KlinePeriod,normalize_kline
async def main():
 async with TdxData() as td:
  bars=await td.get_kline(MARKET,CODE,KlinePeriod.MIN_1,start=50000,count=200)
  d=normalize_kline(bars);d.to_csv(Path(sys.argv[1])/'tdx_recovered_1m.csv',index=False)
  print(json.dumps({'package':importlib.metadata.version('pytdxdata'),'rows':len(d)},default=str))
asyncio.run(main())
"""
 try:
  cp=subprocess.run([sys.executable,'-c',tdx_code,str(R)],capture_output=True,text=True,timeout=120)
  tr=dict(status='ok' if cp.returncode==0 else 'error',returncode=cp.returncode,detail=(cp.stdout+cp.stderr)[-1800:])
  if cp.returncode==0:
   k=pd.read_csv(R/'tdx_recovered_1m.csv',parse_dates=['date','datetime'])
   if len(k):
    k=k[k.date.le('2026-09-11')];k.to_csv(R/'tdx_recovered_1m.csv',index=False)
    qc=k.groupby('date').agg(bars=('datetime','size'),unique=('datetime','nunique'),first=('datetime','min'),last=('datetime','max'),high=('high','max'),low=('low','min'),close=('close','last'));qc.to_csv(R/'recovered_1m_qc.csv')
    expected=list(pd.date_range('2000-01-01 09:31','2000-01-01 11:30',freq='min').strftime('%H:%M'))+list(pd.date_range('2000-01-01 13:01','2000-01-01 15:00',freq='min').strftime('%H:%M'))
    valid=[];compare=[]
    for date,g in k.groupby('date'):
     g=g.sort_values('datetime');grid=g.datetime.dt.strftime('%H:%M').tolist()==expected
     sane=bool((g.high>=g[['open','close','low']].max(axis=1)-1e-7).all() and (g.low<=g[['open','close','high']].min(axis=1)+1e-7).all() and g.volume.ge(0).all())
     if grid and sane:valid.append(date)
     if date in daily.index:
      dd=daily.loc[date];bb=m[m.date.eq(date)];compare.append(dict(date=date,grid_ok=grid,ohlc_ok=sane,high_1m=g.high.max(),high_daily=dd.high,high_5m=bb.high.max(),low_1m=g.low.min(),low_daily=dd.low,low_5m=bb.low.min(),close_1m=g.iloc[-1].close,close_daily=dd.close))
    save('recovered_price_alignment.csv',compare)
    good=set(valid)
    tr.update(rows=len(k),first=str(k.datetime.min()),last=str(k.datetime.max()),days=len(qc),full240=len(good),entry_covered=int(t.date.isin(good).sum()),exit_covered=int(t.actual_exit.isin(good).sum()),both_covered=int((t.date.isin(good)&t.actual_exit.isin(good)).sum()))
    linked=t[['date','actual_exit']].copy();linked['entry_covered']=linked.date.isin(good);linked['exit_covered']=linked.actual_exit.isin(good);save('recovered_candidate_coverage.csv',linked)
 except subprocess.TimeoutExpired:tr=dict(status='timeout120s')
 (R/'tdx_requery.json').write_text(json.dumps(tr,indent=2))
 summary=dict(trades=61,unique_required_dates=len(unique),full48=int(a.bars.eq(48).sum()),high_gap_nonzero=int(a.high_gap.abs().gt(.005).sum()),low_gap_nonzero=int(a.low_gap.abs().gt(.005).sum()),max_high_gap=float(a.high_gap.abs().max()),max_low_gap=float(a.low_gap.abs().max()),ledger_daily_high_max=float(a.daily_ledger_high_delta.abs().max()),ledger_daily_low_max=float(a.daily_ledger_low_delta.abs().max()),possible_hidden_cross=int(a.possible_hidden_cross.sum()),whole_day_hidden_cross=int(a.whole_day_hidden_cross.sum()),adjustflags=sorted(a.adjustflags.unique()),raw_daily_adjustflags=sorted(a.daily_adjustflag.unique().tolist()),input_hashes=inputs,gate='Not certified: no candidate-date true 1m; daily extremes cannot locate crossing before 10:00; no tuning, account or monitoring.',provenance='BaoStock frequency5 adjustflag3; raw package versus ledger; downloader hard QC excludes extrema.')
 (R/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
 (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'}),indent=2))
if __name__=='__main__':run()
