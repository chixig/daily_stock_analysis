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
 for pp in [R/'tdx_recovered_1m.csv',R/'tdx_requery.json',R/'vendor_requery.json']:
  if pp.exists():inputs[str(pp)]=hashlib.sha256(pp.read_bytes()).hexdigest()
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
 probes=json.loads((R/'vendor_requery.json').read_text()) if (R/'vendor_requery.json').exists() else []
 for day in ([] if probes else ['2025-12-05','2026-07-31']):
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
  cp=type('SavedProbe',(),dict(returncode=0,stdout=json.loads((R/'tdx_requery.json').read_text()).get('detail',''),stderr=''))() if (R/'tdx_recovered_1m.csv').exists() else subprocess.run([sys.executable,'-c',tdx_code,str(R)],capture_output=True,text=True,timeout=120)
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
 # Compare only dates with complete recovered 1m; do not infer the remaining 52 trades.
 if (R/'tdx_recovered_1m.csv').exists() and tr.get('both_covered',0)>0:
  import foxconn_overnight_b11 as b11
  import foxconn_overnight_b08 as b8
  b11.tests()
  k=pd.read_csv(R/'tdx_recovered_1m.csv',parse_dates=['date','datetime']);k['clock']=k.datetime.dt.strftime('%H:%M');k=k.sort_values(['date','clock'])
  bars={date:g.to_dict('records') for date,g in k.groupby('date')};days=ledger.reset_index().to_dict('records');loc={x['date']:i for i,x in enumerate(days)}
  covered=t[t.date.isin(good)&t.actual_exit.isin(good)];full=pd.read_csv('research/foxconn_overnight_20260916_b11/exit_trades.csv',parse_dates=['date','actual_exit','exit_date'])
  outputs=[];comparisons=[]
  for mode,stop,worst in [('1000_S0',None,False),('1000_S2',.02,False),('1000_S2_WORSTBAR',.02,True)]:
   g=full[full.entry.eq('C')&full.exit_model.eq(mode)&full.date.isin(covered.date)].copy().sort_values('date');assert len(g)==tr['both_covered']
   old=g.copy();prices=[];clocks=[];reasons=[]
   for _,r in g.iterrows():
    x=b11.morning_exit(r.close,days,bars,loc[r.actual_exit],'10:00',stop,worst)
    assert not x.get('delayed') and x['actual_exit']==r.actual_exit,'1m pending path needs separate timing support'
    prices.append(x['price']);clocks.append(x['clock']);reasons.append(x['reason'])
   g['model_exit']=prices;g['exit_clock']=clocks;g['reason']=reasons;g['cash'],g['net'],g['fee']=b8.pnl(g,exitcol='model_exit');g['gross']=100*((g.model_exit+g.dividend*.8)/g.close-1)
   for label,frame in [('original5m',old),('recovered1m',g)]:outputs.append(dict(mode=mode,source=label,**b11.metrics(frame)))
   for i,r in g.iterrows():
    o=old.loc[i];comparisons.append(dict(date=r.date,exit_date=r.actual_exit,mode=mode,price5m=o.model_exit,price1m=r.model_exit,clock5m=o.exit_clock,clock1m=r.exit_clock,reason5m=o.reason,reason1m=r.reason,net5m=o.net,net1m=r.net,delta_net=r.net-o.net,cash5m=o.cash,cash1m=r.cash))
  save('paired_1m_5m_results.csv',outputs);save('paired_1m_5m_trades.csv',comparisons)
  align=pd.read_csv(R/'recovered_price_alignment.csv',parse_dates=['date']);aa=align[align.date.isin(covered.actual_exit)]
  save('candidate_1m_alignment_summary.csv',[dict(n=len(aa),high1m_daily_max=float((aa.high_1m-aa.high_daily).abs().max()),low1m_daily_max=float((aa.low_1m-aa.low_daily).abs().max()),close1m_daily_max=float((aa.close_1m-aa.close_daily).abs().max()),high1m_5m_max=float((aa.high_1m-aa.high_5m).abs().max()),low1m_5m_max=float((aa.low_1m-aa.low_5m).abs().max()))])
 summary=dict(trades=61,unique_required_dates=len(unique),full48=int(a.bars.eq(48).sum()),high_gap_nonzero=int(a.high_gap.abs().gt(.005).sum()),low_gap_nonzero=int(a.low_gap.abs().gt(.005).sum()),max_high_gap=float(a.high_gap.abs().max()),max_low_gap=float(a.low_gap.abs().max()),ledger_daily_high_max=float(a.daily_ledger_high_delta.abs().max()),ledger_daily_low_max=float(a.daily_ledger_low_delta.abs().max()),possible_hidden_cross=int(a.possible_hidden_cross.sum()),whole_day_hidden_cross=int(a.whole_day_hidden_cross.sum()),adjustflags=sorted(a.adjustflags.unique()),raw_daily_adjustflags=sorted(a.daily_adjustflag.unique().tolist()),input_hashes=inputs,gate='Not certified: recovered coverage is partial; see tdx_requery and paired results. No tuning, account or monitoring.',provenance='BaoStock frequency5 adjustflag3; raw package versus ledger; downloader hard QC excludes extrema.')
 (R/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary))
 (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in R.iterdir() if p.is_file() and p.name!='manifest.json'}),indent=2))
if __name__=='__main__':run()
