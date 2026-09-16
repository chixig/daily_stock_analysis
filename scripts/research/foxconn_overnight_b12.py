import os,json,hashlib,zipfile
from pathlib import Path
import numpy as np
import pandas as pd
import foxconn_overnight_b08 as b8
import foxconn_overnight_b09 as b9
import foxconn_overnight_b11 as b11
R=Path('research/foxconn_overnight_20260917_b12');P=Path('research/foxconn_overnight_20260916_b11');Q=Path('data/601138_intraday/pytdxdata_1min')
def save(n,x):
 z=x if isinstance(x,pd.DataFrame) else pd.DataFrame(x);z.to_csv(R/n,index=False);return z
def stats(g):return b11.metrics(g)
def events(ordinals,gap):return ordinals.diff().gt(gap).cumsum().astype(int)+1
def run():
 assert os.environ.get('GITHUB_ACTIONS')=='true';R.mkdir(parents=True,exist_ok=True);inputs={}
 pm=json.loads((P/'manifest.json').read_text())
 for name in ['exit_trades.csv','exit_results.csv']:
  p=P/name;h=hashlib.sha256(p.read_bytes()).hexdigest();assert h==pm['files'][str(p)];inputs[str(p)]=h
 for p,h in json.loads((P/'audit.json').read_text())['input_hashes'].items():assert hashlib.sha256(Path(p).read_bytes()).hexdigest()==h;inputs[p]=h
 d=pd.read_csv(b9.P8/'daily_ledger.csv',parse_dates=['date','exit_date']);f=pd.read_csv('research/foxconn_overnight_20260916_b10/features.csv');assert pd.to_datetime(f.date).equals(d.date)
 z=pd.read_csv(P/'exit_trades.csv',parse_dates=['date','exit_date','actual_exit']);z=z[z.entry.eq('C')&z.exit_model.isin(['OPEN','1000_S0','1000_S2','1000_S2_WORSTBAR'])].copy()
 assert all(len(x)==61 for _,x in z.groupby('exit_model'));assert not z.delayed.any()
 # Infer no OHLC information from historical minute snapshots.
 qc=pd.read_csv(Q/'qc_kline_daily.csv',parse_dates=['date']);cov=json.loads((Q/'coverage.json').read_text());fine_dates=set(qc.loc[qc.bars_240,'date'])
 for p in [Q/'qc_kline_daily.csv',Q/'coverage.json',*sorted((Q/'kline_yearly').glob('*.csv'))]:inputs[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
 coverage=[]
 for mode,g in z.groupby('exit_model'):
  coverage.append(dict(mode=mode,trades=len(g),entry_1m=int(g.date.isin(fine_dates).sum()),exit_1m=int(g.actual_exit.isin(fine_dates).sum()),both_1m=int((g.date.isin(fine_dates)&g.actual_exit.isin(fine_dates)).sum())))
 cover=save('fine_coverage.csv',coverage)
 with zipfile.ZipFile(b8.P/'source/601138-full-5min-history.zip') as a:m=pd.read_csv(a.open(next(n for n in a.namelist() if n.endswith('601138_5min_all.csv'))))
 m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M');m=m.sort_values(['date','clock']);assert not m.duplicated(['date','clock']).any()
 bars={date:g.set_index('clock') for date,g in m.groupby('date')}
 # Candidate event boundaries are based on raw C signal days, before buyability exclusion.
 raw=d.date.ge('2022-01-01')&f.drop(columns='date').notna().all(axis=1)&d.next_open.notna()&f.prev_r20.le(-16.1565018)
 rawd=d[raw].copy();summaries=[];ep_rows=[];loo=[];firsts=[];members=[]
 for gap in [3,5,10]:
  tags=events(rawd.ordinal,gap);mapping=pd.Series(tags.to_numpy(),index=rawd.date)
  for cut in [max(1,len(rawd)//2),len(rawd)-1]:pd.testing.assert_series_equal(events(rawd.ordinal.iloc[:cut],gap),tags.iloc[:cut])
  for mode,g in z.groupby('exit_model'):
   g=g.sort_values('date').copy();g['event']=g.date.map(mapping);assert g.event.notna().all()
   for wn,sel in [('all',pd.Series(True,index=g.index)),('recent2024',g.date.dt.year.ge(2024))]:
    x=g[sel];summaries.append(dict(gap=gap,mode=mode,window=wn,variant='all_signals',**stats(x)))
    # Select the first buyable signal online; the current event begins after a >gap interval.
    first=g.groupby('event',sort=False).head(1);first=first[first.index.isin(x.index)];summaries.append(dict(gap=gap,mode=mode,window=wn,variant='first_buyable_signal',**stats(first)))
   first=g.groupby('event',sort=False).head(1).copy();first['gap']=gap;firsts.append(first)
   es=[]
   for eid,x in g.groupby('event'):
    row=dict(gap=gap,mode=mode,event=int(eid),start=x.date.min(),end=x.date.max(),sum_net=float(x.net.sum()),**stats(x));es.append(row);ep_rows.append(row)
   et=pd.DataFrame(es)
   for ranking in ['cash','sum_net']:
    order=et.sort_values([ranking,'event'],ascending=[False,True]);best=int(order.iloc[0].event);worst=int(order.iloc[-1].event)
    for variant,ids in [('remove_best_event',[best]),('remove_worst_event',[worst]),('remove_both_events',[best,worst])]:summaries.append(dict(gap=gap,mode=mode,window='all',variant=variant,ranking=ranking,removed_events=','.join(map(str,ids)),**stats(g[~g.event.isin(ids)])))
   for eid in et.event:loo.append(dict(gap=gap,mode=mode,removed_event=int(eid),**stats(g[g.event.ne(eid)])))
   g['gap']=gap;members.append(g)
 summ=save('event_summary.csv',summaries);save('events.csv',ep_rows);save('leave_one_event_out.csv',loo);save('first_event_trades.csv',pd.concat(firsts));save('event_members.csv',pd.concat(members))
 # Execute after observing completed trigger bar; next bar open versus close delimit latency stress.
 results=[];latency_trades=[];alignment=[]
 for mode,g in z.groupby('exit_model'):
  g=g.sort_values('date').copy()
  for kind in ['original','next_bar_open','next_bar_close']:
   x=g.copy();prices=[];clocks=[]
   for _,r in x.iterrows():
    b=bars[r.actual_exit];future=b[b.index>r.exit_clock]
    if kind=='original':price=r.model_exit;clock=r.exit_clock
    else:
     assert len(future)>0;bar=future.iloc[0];assert bar.volume>0;price=bar['open' if kind=='next_bar_open' else 'close'];clock=future.index[0]
     day=d[d.date.eq(r.actual_exit)].iloc[0];assert price>round(day.preclose*.9,2)+.005
    prices.append(price);clocks.append(clock)
   x['model_exit']=prices;x['latency_clock']=clocks
   for slip in [.0005,.001,.002]:
    y=b9.changes(x,slip=slip,exitcol='model_exit')
    if kind=='original' and slip==.0005:np.testing.assert_allclose(y.net,g.net,atol=1e-10)
    for wn,wm in [('all',pd.Series(True,index=y.index)),('recent2024',y.date.dt.year.ge(2024))]:results.append(dict(mode=mode,latency=kind,slip=slip,window=wn,delta_mean=float((y.loc[wm,'net']-g.loc[wm,'net']).mean()),**stats(y[wm])))
    if slip==.0005:y['latency']=kind;latency_trades.append(y)
  for _,r in g.iterrows():
   day=d[d.date.eq(r.actual_exit)].iloc[0];bb=bars[r.actual_exit];alignment.append(dict(mode=mode,date=r.date,exit_date=r.actual_exit,entry_bar_close=float(bars[r.date].loc['15:00','close']),daily_entry_close=r.close,exit_minute_high=float(bb.high.max()),daily_high=day.high,exit_minute_low=float(bb.low.min()),daily_low=day.low))
 res=save('execution_pressure.csv',results);save('latency_trades.csv',pd.concat(latency_trades));save('daily_minute_alignment.csv',alignment)
 # An adverse signal universe still receives separately costed opposite-direction evidence.
 mirrors=[]
 for mode,g in z.groupby('exit_model'):
  for gap in [3,5,10]:
   x=pd.concat(firsts);x=x[x.exit_model.eq(mode)&x.gap.eq(gap)]
   if len(x) and x.net.mean()<0:mirrors.append(dict(mode=mode,gap=gap,**stats(b9.changes(x,reverse=True,exitcol='model_exit'))))
 save('mirror_registry.csv',mirrors)
 audit=dict(data_end='2026-09-11',fixed_candidate='prev_r20<=-16.1565018;close buy;10:00 deadline;none/2% stop unchanged',raw_signal_days=int(raw.sum()),tradable_signals=61,fine_coverage=cov,input_hashes=inputs,checks='B11 hashes/61 trades,causal event-prefix,partition by events,latency liquidity/range,original pnl reproduction',gate='Execution cannot be certified without candidate-date 1m/auction coverage;account and prospective automation not started pending execution gate. 5m stress is diagnostic,not evidence of actual orders.',limitations='Historical C discovered in full sample;event sensitivity3/5/10 sessions fixed before run;first buyable can be computed online;future event-end used only reporting;bar-confirmation latency is 0-5min then next close adds5min,not actual tick simulation.')
 for mode,g in z.groupby('exit_model'):
  e=pd.DataFrame(ep_rows);x=e[e.gap.eq(5)&e['mode'].eq(mode)];assert x.n.sum()==61;assert abs(x.cash.sum()-g.cash.sum())<1e-7
 (R/'audit.json').write_text(json.dumps(audit,indent=2))
 (R/'REPORT.md').write_text('\n\n'.join(['# B12 Execution and event verification','## Fine coverage',cover.to_markdown(index=False),'## Event summary, gap5',summ[summ.gap.eq(5)].to_markdown(index=False,floatfmt='.4f'),'## Execution pressure',res.to_markdown(index=False,floatfmt='.4f'),'## Audit',json.dumps(audit,indent=2)]))
 (R/'manifest.json').write_text(json.dumps(dict(code_sha=os.environ['GITHUB_SHA'],run_id=os.environ['GITHUB_RUN_ID'],files={str(p):hashlib.sha256(p.read_bytes()).hexdigest()for p in R.iterdir()if p.is_file() and p.name!='manifest.json'}),indent=2));print(json.dumps(audit))
if __name__=='__main__':run()
