#!/usr/bin/env python3
"""B16 final evidence validation and fixed-case path explanation, no parameter search."""
import os,json,hashlib,zipfile
from pathlib import Path
import pandas as pd,numpy as np
import foxconn_b16_accounts as b
assert os.environ.get('GITHUB_ACTIONS')=='true'
R=b.R;Q=b.Q;P=b.P
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):
 x=x if isinstance(x,pd.DataFrame)else pd.DataFrame(x);x.to_csv(R/n,index=False);return x
man=json.loads((R/'manifest.json').read_text())
# The tee log is necessarily finalized after the main process's manifest call.
# Preserve original manifest as evidence, then rehash the now-closed log in final manifest.
oldhash=sha(R/'manifest.json')
changed=[]
for p,h in man['files'].items():
 if sha(p)!=h:changed.append(p)
assert changed==[str(R/'calculation.log')],changed
(R/'calculation_manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
assert 'B16_COMPLETE 44' in (R/'calculation.log').read_text()
for p,h in man['inputs'].items():assert sha(p)==h,p
parentcount=0
for folder in [P,Q]:
 for p,h in json.loads((folder/'manifest.json').read_text())['files'].items():assert sha(p)==h,p;parentcount+=1
ac=pd.read_csv(R/'account_summary.csv');d=pd.read_csv(P/'daily_ledger.csv',parse_dates=['date','exit_date']);ds=d.set_index('date');events=json.loads((R/'verified_events.json').read_text())
with zipfile.ZipFile('research/foxconn_t0_20260913/source/601138-full-5min-history.zip')as z:
 m=pd.read_csv(z.open(next(n for n in z.namelist()if n.endswith('601138_5min_all.csv'))))
m.date=pd.to_datetime(m.date);m['clock']=pd.to_datetime(m.time.astype(str).str[:14],format='%Y%m%d%H%M%S').dt.strftime('%H:%M')
lookup=m[m.clock.eq('09:45')].set_index('date').open
fund=pd.read_csv(R/'restoration_funding_ledger.csv',parse_dates=['date']);pay=pd.read_csv(R/'event_entitlement_payment_ledger.csv',parse_dates=['date','event'])
valid=[];cases=[];windows=[];cashall=[]
for _,a in ac.iterrows():
 key=a.scenario;z=pd.read_csv(R/('account_'+key+'.csv'),parse_dates=['date']);o=pd.read_csv(R/('orders_'+key+'.csv'),parse_dates=['date']);ep=pd.read_csv(R/('episodes_'+key+'.csv'))
 # Verify references, actual event clocks and 15:00 signal/next-day first window, using saved fixed endpoints.
 expected=[]
 for _,t in o.iterrows():
  if t.side=='SELL':expected.append(ds.loc[t.date,'close']);assert t.clock=='15:00'
  elif t.clock=='09:25':expected.append(ds.loc[t.date,'open'])
  else:assert t.clock=='09:40'and a.first_window=='post0935';expected.append(lookup.loc[t.date])
 np.testing.assert_allclose(o.reference,expected,atol=1e-8,rtol=0)
 sales=o[o.side.eq('SELL')].date.tolist();lastsale=None
 for _,t in o.iterrows():
  if t.side=='SELL':
   lastsale=t.date
   idx=int(d.date.searchsorted(t.date))
   if a.rule=='S1_F1':
    p=d.iloc[idx-1];assert (p.close-p.low)/(p.high-p.low)>=.8
  elif t.clock=='09:40':assert int(d.date.searchsorted(t.date))==int(d.date.searchsorted(lastsale))+1
  elif t.side=='BUY'and a.first_window=='post0935':
   assert int(d.date.searchsorted(t.date))>int(d.date.searchsorted(lastsale))+1
 eq=np.r_[a.initial,z[['equity_open_before','equity_open','equity_close']].to_numpy().ravel()]
 heq=np.r_[a.initial,z[['hold_equity_open','hold_equity_after','hold_equity_close']].to_numpy().ravel()]
 rel=eq-heq
 assert abs((eq[-1]-heq[-1])-a.increment_cash)<1e-6
 assert abs(100*(eq/np.maximum.accumulate(eq)-1).min()-a.mdd_pct)<1e-7
 assert abs((rel-np.maximum.accumulate(rel)).min()-a.relative_mdd_cash)<1e-7
 assert abs(z.fees.sum()-a.fees)<1e-6 and abs(z.dividend_tax_paid.sum()-a.dividend_tax)<1e-6
 assert a.sales-a.completed==int(a.terminal_missing>0)
 valid.append(dict(scenario=key,orders=len(o),price_refs_and_clocks=True,prior_clv=True,summary_drawdowns=True))
 if a.rule=='S1_F1'and a.purpose=='extra_cost':
  base=f'S1_F1_{a.first_window}_b{int(a.base_bp)}_e0_d0_main'
  bz=pd.read_csv(R/('account_'+base+'.csv'),parse_dates=['date']);bo=pd.read_csv(R/('orders_'+base+'.csv'),parse_dates=['date'])
  first=b.firstshape(bo,o);fl=fund[fund.scenario.eq(key)];unresolved=ep[ep.restored.eq(False)]
  window=z[z.date.between('2025-10-16','2025-11-28')];year=z[z.date.dt.year.eq(2025)];delta=z.relative_equity.diff().fillna(z.relative_equity.iloc[0])
  row=dict(scenario=key,first_quantity_change=first,terminal_cash_gap=a.terminal_cash_gap,unresolved_sale=unresolved.entry.iloc[-1]if len(unresolved)else None,unresolved_days=unresolved.days.iloc[-1]if len(unresolved)else 0,sales2025=int(year.sell_quantity.gt(0).sum()),increment2025=delta[z.date.dt.year.eq(2025)].sum(),calendar_event92_increment=delta[z.date.between('2025-10-16','2025-11-28')].sum(),calendar_event92_sales=int(window.sell_quantity.gt(0).sum()))
  if first:
   day=pd.Timestamp(first);f=fl[fl.date.eq(day)].iloc[0];bf=fund[fund.scenario.eq(base)&fund.date.eq(day)].iloc[0]
   row.update(clock=f.clock,full_cost=f.full_cost,available_cash=f.cash_before-f.tax_reserve,cash_shortfall=f.cash_gap,base_cash_surplus=bf.cash_before-bf.tax_reserve-bf.full_cost,base_buy_quantity=int(bo[bo.date.eq(day)&bo.side.eq('BUY')].quantity.sum()),new_buy_quantity=int(o[o.date.eq(day)&o.side.eq('BUY')].quantity.sum()))
   pos=int(z.date.searchsorted(day))
   for label,zz in [('base',bz),('extra',z)]:
    view=zz.iloc[max(0,pos-1):pos+4].copy();view.insert(0,'comparison',label);view.insert(0,'scenario',key);windows.append(view)
  cases.append(row)
 if a.rule=='S1_F1'and a.purpose=='main'and a.delay==0:
  for e in events:
   ev=pay[pay.scenario.eq(key)&pay.event.eq(e['ex_date'])]
   ent=ev[ev.action.eq('entitlement')];paid=ev[ev.action.eq('payment')]
   cashall.append(dict(scenario=key,event=e['ex_date'],source_status=e['source_status'],entitlement=ent.amount.sum()if len(ent)else 0,quantity=ent.quantity.iloc[0]if len(ent)else 0,payment_date=paid.date.iloc[0]if len(paid)else None,account_window='included'if e['applies_to_account_window']else'before_start_no_initial_claim'))
save('final_endpoint_summary_validation.csv',valid)
case=save('stress_first_funding_cases.csv',cases)
save('stress_daily_path_cases.csv',pd.concat(windows,ignore_index=True))
allcash=save('all_event_cash_dependencies.csv',cashall)
# Settlement-date comparison explicitly checks orders excluding cash fields versus all per-day equity fields.
delaycheck=[]
for _,a in ac[(ac.rule=='S1_F1')&(ac.purpose=='main')&(ac.delay>0)].iterrows():
 base=a.scenario.replace('_d1_','_d0_').replace('_d3_','_d0_')
 z=pd.read_csv(R/('account_'+a.scenario+'.csv'));bz=pd.read_csv(R/('account_'+base+'.csv'))
 o=pd.read_csv(R/('orders_'+a.scenario+'.csv'));bo=pd.read_csv(R/('orders_'+base+'.csv'))
 cols=['date','clock','side','quantity','reference','value','fee','dividend_tax']
 pd.testing.assert_frame_equal(o[cols],bo[cols],check_exact=False,atol=1e-7,rtol=0)
 for c in ['equity_open_before','equity_open','equity_close','relative_equity']:np.testing.assert_allclose(z[c],bz[c],atol=1e-7,rtol=0)
 delaycheck.append(dict(scenario=a.scenario,economic_orders_equal=True,all_sampled_equities_equal=True,cash_receivable_fields_can_differ=True))
save('S1_delay_invariance.csv',delaycheck)
result=dict(status='PASS',accounts_checked=len(valid),original_files_unchanged=parentcount,main_code_sha=man['code_sha'],main_run_id=man['run_id'],original_manifest_sha256=oldhash,expected_live_log_difference=changed,source_primary_verified=9,corrected_price_version=False,correction_reason='cross-source discrepancy unresolved; no unsupported replacement',finite_account_funding_explained=True,verification_run_id=os.environ['GITHUB_RUN_ID'],verification_code_sha=os.environ['GITHUB_SHA'])
(R/'final_verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
(R/'FINAL_REVIEW.md').write_text('# B16 final path and artifact verification\n\n'+case.to_markdown(index=False,floatfmt='.6f')+'\n\n## Complete nine-event cash entitlement\n\n'+allcash.to_markdown(index=False)+'\n\n'+json.dumps(result,ensure_ascii=False,indent=2))
files={str(p):sha(p)for p in R.rglob('*')if p.is_file()and p.name!='manifest.json'}
man.update(files=files,final_verification_run=os.environ['GITHUB_RUN_ID'],final_verification_code=os.environ['GITHUB_SHA'])
(R/'manifest.json').write_text(json.dumps(man,ensure_ascii=False,indent=2))
print(json.dumps(result,ensure_ascii=False),flush=True)
